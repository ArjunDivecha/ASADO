#!/usr/bin/env python3
"""
Rank current Triptych scan rows into ASADO opportunity candidates.

The input workbook is Triptych's exhaustive slope/R2 scan across
country/factor/normalization/return-mode/horizon combinations. This script is
the ASADO-side front door: it reads that workbook, filters out lookahead target
variables, ranks rows whose current decile is on the attractive side of a
monotonic bucket relationship, and writes review artifacts under Data/loop.

Full-sample scan rows are discovery clues, not predictive evidence. Strong
rows still need PIT recomputation and ASADO harness/event-study validation
before promotion.
"""

from __future__ import annotations

import argparse
import html
import math
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
import duckdb

try:
    from scripts.loop.loopdb import LOOP_DB, LOOP_DIR
except ModuleNotFoundError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
    from scripts.loop.loopdb import LOOP_DB, LOOP_DIR


BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_SCAN_XLSX = Path(
    "/Users/arjundivecha/Dropbox/AAA Backup/A Working/Triptych/app/data/slope_r2_scan.xlsx"
)
DEFAULT_BASE_URL = "https://triptych-one.vercel.app/triptych.html"
OUTPUT_PARQUET = LOOP_DIR / "triptych_opportunity_scan.parquet"
OUTPUT_HTML = LOOP_DIR / "reports" / "triptych_opportunity_scan_latest.html"
OUTPUT_MD = LOOP_DIR / "reports" / "triptych_opportunity_scan_latest.md"

FORWARD_RETURN_FACTOR_RE = re.compile(r"^(?:\d+MRet|\d+DRet|1MRet|3MRet|6MRet|9MRet|12MRet)$", re.I)
VALID_NORMALIZATIONS = {"raw", "history_z", "cross_var_pct"}
VALID_RETURN_MODES = {"absolute", "relative"}
VALID_HORIZONS = {1, 3, 6, 12, 24, 36}
REQUIRED_COLUMNS = {
    "Factor",
    "Country",
    "Normalization",
    "Return Mode",
    "Horizon (M)",
    "Slope (/bucket)",
    "R-squared",
    "Current Decile",
    "Sample Size",
    "Bucket 1 Avg",
    "Bucket 10 Avg",
}


@dataclass(frozen=True)
class ScanConfig:
    scan_xlsx: Path = DEFAULT_SCAN_XLSX
    top: int = 40
    min_r2: float = 0.55
    min_abs_slope: float = 0.0075
    min_sample_size: int = 60
    current_low_decile: int = 2
    current_high_decile: int = 9
    prefer_return_mode: str = "relative"
    prefer_normalization: str = "history_z"
    base_url: str = DEFAULT_BASE_URL
    write_db: bool = True


def is_forbidden_factor(factor: str) -> bool:
    """Return True for target/forward-return sheets that must never be signals."""
    factor = str(factor).strip()
    return bool(FORWARD_RETURN_FACTOR_RE.match(factor))


def build_triptych_url(
    country: str,
    factor: str,
    normalization: str,
    return_mode: str,
    horizon: int,
    *,
    base_url: str = DEFAULT_BASE_URL,
    threshold_mode: str = "full",
    history_range: str = "all",
    buckets: int = 10,
) -> str:
    params = {
        "tab": "triptych",
        "tf": factor,
        "tc": country,
        "tn": normalization,
        "tm": return_mode,
        "th": str(int(horizon)),
        "tr": history_range,
        "td": threshold_mode,
        "tb": str(int(buckets)),
    }
    return f"{base_url}?{urlencode(params)}"


def load_scan(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Triptych scan workbook not found: {path}")
    df = pd.read_excel(path, sheet_name="Slope R2 Scan")
    missing = sorted(REQUIRED_COLUMNS - set(df.columns))
    if missing:
        raise ValueError(f"Triptych scan workbook missing columns: {missing}")
    return df


def rank_opportunities(df: pd.DataFrame, cfg: ScanConfig) -> pd.DataFrame:
    work = df.copy()
    for col in [
        "Horizon (M)",
        "Slope (/bucket)",
        "R-squared",
        "Current Decile",
        "Sample Size",
        "Bucket 1 Avg",
        "Bucket 10 Avg",
    ]:
        work[col] = pd.to_numeric(work[col], errors="coerce")

    work["Factor"] = work["Factor"].astype(str).str.strip()
    work["Country"] = work["Country"].astype(str).str.strip()
    work["Normalization"] = work["Normalization"].astype(str).str.strip()
    work["Return Mode"] = work["Return Mode"].astype(str).str.strip()

    work = work[
        (~work["Factor"].map(is_forbidden_factor))
        & (work["Normalization"].isin(VALID_NORMALIZATIONS))
        & (work["Return Mode"].isin(VALID_RETURN_MODES))
        & (work["Horizon (M)"].isin(VALID_HORIZONS))
        & (work["R-squared"] >= cfg.min_r2)
        & (work["Slope (/bucket)"].abs() >= cfg.min_abs_slope)
        & (work["Sample Size"] >= cfg.min_sample_size)
        & (work["Current Decile"].notna())
    ].copy()

    low_is_good = (work["Slope (/bucket)"] < 0) & (work["Current Decile"] <= cfg.current_low_decile)
    high_is_good = (work["Slope (/bucket)"] > 0) & (work["Current Decile"] >= cfg.current_high_decile)
    work = work[low_is_good | high_is_good].copy()

    work["implied_direction"] = "long"
    work["attractive_side"] = work["Slope (/bucket)"].map(lambda x: "low decile" if x < 0 else "high decile")
    work["current_bucket_avg"] = work.apply(
        lambda r: r["Bucket 1 Avg"] if r["Slope (/bucket)"] < 0 else r["Bucket 10 Avg"],
        axis=1,
    )
    work["opposite_bucket_avg"] = work.apply(
        lambda r: r["Bucket 10 Avg"] if r["Slope (/bucket)"] < 0 else r["Bucket 1 Avg"],
        axis=1,
    )
    work["bucket_edge_spread"] = work["current_bucket_avg"] - work["opposite_bucket_avg"]
    work["endpoint_return"] = work["current_bucket_avg"]
    work["score"] = (
        work["Slope (/bucket)"].abs()
        * work["R-squared"].clip(lower=0.0)
        * work["Sample Size"].clip(upper=240).div(240).pow(0.35)
    )
    work["preferred_view_bonus"] = 0.0
    work.loc[work["Return Mode"] == cfg.prefer_return_mode, "preferred_view_bonus"] += 0.10
    work.loc[work["Normalization"] == cfg.prefer_normalization, "preferred_view_bonus"] += 0.10
    work["rank_score"] = work["score"] * (1.0 + work["preferred_view_bonus"])
    work["run_date"] = date.today().isoformat()
    work["threshold_mode"] = "full"
    work["evidence_status"] = "discovery_full_sample_requires_pit"
    work["triptych_url"] = work.apply(
        lambda r: build_triptych_url(
            r["Country"],
            r["Factor"],
            r["Normalization"],
            r["Return Mode"],
            int(r["Horizon (M)"]),
            base_url=cfg.base_url,
        ),
        axis=1,
    )

    out = work.sort_values(["rank_score", "R-squared", "bucket_edge_spread"], ascending=False).head(cfg.top)
    rename = {
        "Factor": "factor",
        "Country": "country",
        "Normalization": "normalization",
        "Return Mode": "return_mode",
        "Horizon (M)": "horizon_months",
        "Slope (/bucket)": "slope_per_bucket",
        "R-squared": "r_squared",
        "Current Decile": "current_decile",
        "Sample Size": "sample_size",
        "Bucket 1 Avg": "bucket_1_avg",
        "Bucket 10 Avg": "bucket_10_avg",
    }
    return out.rename(columns=rename).reset_index(drop=True)


def pct(x: float | int | None) -> str:
    if x is None or not math.isfinite(float(x)):
        return "n/a"
    return f"{float(x) * 100:.1f}%"


def render_bar(row: pd.Series) -> str:
    b1 = row["bucket_1_avg"]
    b10 = row["bucket_10_avg"]
    vals = [v for v in [b1, b10, 0.0] if math.isfinite(float(v))]
    lim = max(abs(float(v)) for v in vals) or 0.01

    def one(label: str, value: float, active: bool) -> str:
        width = min(100.0, abs(float(value)) / lim * 100.0)
        cls = "pos" if value >= 0 else "neg"
        active_cls = " active" if active else ""
        return (
            f'<div class="bar-row{active_cls}"><div class="bar-label">{label}</div>'
            f'<div class="bar-track"><div class="bar {cls}" style="width:{width:.1f}%"></div></div>'
            f'<div class="bar-value">{pct(value)}</div></div>'
        )

    current_low = row["current_decile"] <= 2
    current_high = row["current_decile"] >= 9
    return one("Bucket 1", b1, current_low) + one("Bucket 10", b10, current_high)


def render_html(rows: pd.DataFrame, output_path: Path, scan_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cards = []
    for idx, row in rows.iterrows():
        cards.append(
            f"""
            <article class="card">
              <div class="rank">#{idx + 1}</div>
              <h2>{html.escape(row['country'])} / {html.escape(row['factor'])}</h2>
              <div class="meta">
                {int(row['horizon_months'])}M {html.escape(row['return_mode'])} returns ·
                {html.escape(row['normalization'])} · current decile {int(row['current_decile'])}
              </div>
              <div class="thesis">
                Current setup is on the <b>{html.escape(row['attractive_side'])}</b> side of a monotonic scan:
                slope {pct(row['slope_per_bucket'])}/bucket, R² {row['r_squared']:.2f}.
              </div>
              <div class="bars">{render_bar(row)}</div>
              <div class="stats">
                <span>Endpoint edge {pct(row['bucket_edge_spread'])}</span>
                <span>Current endpoint {pct(row['endpoint_return'])}</span>
                <span>n={int(row['sample_size'])}</span>
                <span>score={row['rank_score']:.4f}</span>
              </div>
              <a class="button" href="{html.escape(row['triptych_url'])}">Open Visual In Triptych</a>
            </article>
            """
        )

    body = "\n".join(cards) if cards else "<p>No opportunities passed the filters.</p>"
    output_path.write_text(
        f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Triptych Opportunity Scan</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; margin: 0; background: #f5f7f6; color: #17211d; }}
    header {{ padding: 28px 34px 18px; background: #ffffff; border-bottom: 1px solid #d9e0dc; }}
    h1 {{ margin: 0 0 8px; font-size: 26px; }}
    .note {{ max-width: 980px; color: #53615a; line-height: 1.45; }}
    main {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px; padding: 22px 34px 34px; }}
    .card {{ position: relative; background: #fff; border: 1px solid #dce4df; border-radius: 8px; padding: 18px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }}
    .rank {{ position: absolute; right: 16px; top: 14px; color: #6c7771; font-weight: 700; }}
    h2 {{ margin: 0 48px 6px 0; font-size: 19px; }}
    .meta {{ color: #607069; font-size: 13px; margin-bottom: 14px; }}
    .thesis {{ font-size: 14px; line-height: 1.45; margin-bottom: 14px; }}
    .bars {{ display: grid; gap: 8px; margin: 12px 0; }}
    .bar-row {{ display: grid; grid-template-columns: 70px 1fr 70px; gap: 10px; align-items: center; font-size: 13px; }}
    .bar-row.active .bar-label {{ font-weight: 800; }}
    .bar-track {{ height: 16px; background: #eef2ef; border-radius: 4px; overflow: hidden; }}
    .bar {{ height: 100%; border-radius: 4px; }}
    .pos {{ background: #5fa27c; }}
    .neg {{ background: #bd756e; }}
    .bar-value {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .stats {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 13px 0 16px; }}
    .stats span {{ background: #eef4f0; color: #33443b; border-radius: 4px; padding: 5px 7px; font-size: 12px; }}
    .button {{ display: inline-block; color: #ffffff; background: #224f3a; text-decoration: none; border-radius: 5px; padding: 8px 11px; font-weight: 700; font-size: 13px; }}
  </style>
</head>
<body>
  <header>
    <h1>Triptych Opportunity Scan</h1>
    <div class="note">
      Ranked from {html.escape(str(scan_path))}. This is a full-sample descriptive discovery report:
      use it to find interesting current country/factor setups and open the visual in Triptych.
      PIT recomputation and ASADO harness/event-study validation are still required before treating any row as evidence.
    </div>
  </header>
  <main>{body}</main>
</body>
</html>
""",
        encoding="utf-8",
    )


def render_markdown(rows: pd.DataFrame, output_path: Path, scan_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Triptych Opportunity Scan",
        "",
        f"Source workbook: `{scan_path}`",
        "",
        "Full-sample descriptive discovery surface. PIT recomputation and ASADO validation are required before evidence/promotion.",
        "",
        "| Rank | Country | Factor | Horizon | Current decile | Slope/bucket | R2 | Endpoint edge | Visual |",
        "|---:|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for idx, row in rows.iterrows():
        lines.append(
            "| {rank} | {country} | {factor} | {horizon} | {decile} | {slope} | {r2:.2f} | {edge} | [Open]({url}) |".format(
                rank=idx + 1,
                country=row["country"],
                factor=row["factor"],
                horizon=int(row["horizon_months"]),
                decile=int(row["current_decile"]),
                slope=pct(row["slope_per_bucket"]),
                r2=row["r_squared"],
                edge=pct(row["bucket_edge_spread"]),
                url=row["triptych_url"],
            )
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_loop_db(rows: pd.DataFrame) -> None:
    LOOP_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(LOOP_DB))
    try:
        con.execute("DROP TABLE IF EXISTS triptych_opportunity_scan")
        con.register("triptych_rows", rows)
        con.execute("CREATE TABLE triptych_opportunity_scan AS SELECT * FROM triptych_rows")
    finally:
        con.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ASADO's Triptych opportunity scan report.")
    parser.add_argument("--scan-xlsx", default=str(DEFAULT_SCAN_XLSX), help="Triptych slope_r2_scan.xlsx path")
    parser.add_argument("--top", default=40, type=int, help="Number of opportunities to keep")
    parser.add_argument("--min-r2", default=0.55, type=float)
    parser.add_argument("--min-abs-slope", default=0.0075, type=float)
    parser.add_argument("--min-sample-size", default=60, type=int)
    parser.add_argument("--no-db", action="store_true", help="Skip loop DB table write")
    parser.add_argument("--check", action="store_true", help="Print top rows after writing artifacts")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = ScanConfig(
        scan_xlsx=Path(args.scan_xlsx),
        top=args.top,
        min_r2=args.min_r2,
        min_abs_slope=args.min_abs_slope,
        min_sample_size=args.min_sample_size,
        write_db=not args.no_db,
    )
    LOOP_DIR.mkdir(parents=True, exist_ok=True)
    df = load_scan(cfg.scan_xlsx)
    ranked = rank_opportunities(df, cfg)
    ranked.to_parquet(OUTPUT_PARQUET, index=False)
    render_html(ranked, OUTPUT_HTML, cfg.scan_xlsx)
    render_markdown(ranked, OUTPUT_MD, cfg.scan_xlsx)
    if cfg.write_db:
        write_loop_db(ranked)

    print(f"Rows selected: {len(ranked)}")
    print(f"Parquet: {OUTPUT_PARQUET}")
    print(f"HTML: {OUTPUT_HTML}")
    print(f"Markdown: {OUTPUT_MD}")
    if cfg.write_db:
        print(f"Loop DB table: triptych_opportunity_scan ({LOOP_DB})")
    if args.check and not ranked.empty:
        cols = [
            "country",
            "factor",
            "normalization",
            "return_mode",
            "horizon_months",
            "current_decile",
            "slope_per_bucket",
            "r_squared",
            "bucket_edge_spread",
        ]
        print(ranked[cols].head(15).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
