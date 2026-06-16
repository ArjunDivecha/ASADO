#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/build_jst_risk_report.py
=============================================================================

DESCRIPTION:
Builds the JST long-cycle TAIL-RISK report — the "use it where it's free"
application of the Jordà-Schularick-Taylor calibration corpus (1870-2020,
13 in-universe developed markets).

The Alpha-Hunting Loop's cost model showed the tradable edges are thin
(8-14 bps breakeven), but tail CONTEXT carries no transaction cost: being
right about the once-in-a-century downside is pure information. This report
takes each T2 country's CURRENT cyclical equity drawdown, buckets it into the
JST drawdown states, and attaches the 150-year-calibrated forward 1/3/5-year
REAL equity return distribution for that bucket — most importantly the p10
"once-in-a-century downside" the modern (~2000+, 3-crisis) sample cannot see.

Design discipline (inherited from the JST corpus rules):
  - READ-ONLY. Touches no warehouse tables for writing; reads the loop returns
    panel + the distilled JST calibration JSON only (never the raw 150y panel).
  - JST directly calibrates 13 developed markets. Every other T2 country (the
    EMs, plus the NASDAQ / US SmallCap sleeves) is labeled DM-ANALOGY: the
    distribution is a developed-market reference, NOT a same-market estimate.
  - Live drawdown is NOMINAL (no live CPI deflation); the JST distribution is
    REAL. In the low-inflation modern regime nominal/real coincide closely for
    DMs; for EM-analogy rows this is one more reason to read directionally.
  - Conditioning is point-in-time clean: drawdown measured at the as-of date,
    forward returns are the historical distribution — no lookahead.
  - Tail cells use overlapping annual windows, so n_obs overstates independent
    sample size; the clean count is the 65 banking-crisis onsets. Treat the
    cells as a PRIOR (a distribution shape), not as carrying a real t-stat.

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Loop DB (read-only); the main warehouse is attached read-only as `asado`.
    Source of the daily T2 country returns used to compute current drawdowns.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime/calib/jst_bearbottom_conditional_returns.json
    Distilled JST conditional forward-return distributions (state x asset x
    horizon), produced by scripts/calibrate_jst_bearbottom.py.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/risk_reports/jst_tail_risk_YYYY_MM_DD.xlsx
    Three sheets: "Country Tail Risk" (all 34, deepest drawdown first, with the
    forward 1/3/5y real-equity distribution for each country's current bucket),
    "JST Conditional Tables" (the full state x asset x horizon calibration grid),
    "Notes & Methodology" (source, scope, caveats, banking-crisis reference).
    YYYY_MM_DD = the data AS-OF date (the latest returns date), not wall-clock.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/risk_reports/jst_tail_risk_YYYY_MM_DD.pdf
    Light-mode tail-fan chart: forward-3y real-equity p10 / median / p90 per
    country for its current drawdown bucket, DMs vs EM-analogy color-coded.

VERSION: 1.0
LAST UPDATED: 2026-06-16
AUTHOR: Claude (Fable 5) for Arjun Divecha

DEPENDENCIES: pandas, duckdb, openpyxl, matplotlib (ASADO venv). No seaborn
(house rule). PDF, not PNG (house rule). Light mode only (house rule).

USAGE:
  venv/bin/python scripts/loop/build_jst_risk_report.py
  venv/bin/python scripts/loop/build_jst_risk_report.py --date 2026-06-12
  venv/bin/python scripts/loop/build_jst_risk_report.py --outdir /tmp/jst

NOTES:
- Runs as a final read-only step of the nightly loop job (loop_daily_job.py).
- Atomic writes (temp file + os.replace) so a crashed run never leaves a
  half-written report.
- matplotlib is a listed dependency; if it is genuinely absent the xlsx (the
  primary deliverable) is still written and the script warns. Any error DURING
  plotting is a real bug and fails the step (FAIL-IS-FAIL).
=============================================================================
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from regime.calib import jst_calib  # noqa: E402
from scripts.loop.loopdb import BASE_DIR, T2_UNIVERSE, loop_connection, returns_panel  # noqa: E402

REPORT_DIR = BASE_DIR / "Data" / "loop" / "risk_reports"
HORIZONS = (1, 3, 5)
PCT = 100.0  # store stats as readable percentages (8.8 == 8.8%), not fractions


def _atomic_replace(tmp: Path, final: Path) -> None:
    os.replace(tmp, final)


def build_country_table(con, asof: pd.Timestamp | None) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Per-country current drawdown -> JST bucket -> forward real-equity tail.

    Returns (table, data_as_of_date). Covers all 34 T2 countries that have a
    computable trailing drawdown; sorted deepest drawdown first.
    """
    piv = returns_panel(con)
    if asof is not None:
        piv = piv.loc[:asof]
    if piv.empty:
        raise RuntimeError("returns_panel is empty for the requested as-of date.")
    data_asof = pd.Timestamp(piv.index.max())

    dds = jst_calib.country_drawdowns(piv)  # {country: trailing drawdown (<=0)}
    rows = []
    for country in T2_UNIVERSE:
        dd = dds.get(country)
        if dd is None:
            continue
        bucket = jst_calib.bucket_for_drawdown(dd)
        scope = "DM" if jst_calib.is_jst_dm(country) else "EM-analogy"
        row = {
            "country": country,
            "scope": scope,
            "trailing_drawdown_pct": round(dd * PCT, 1),
            "jst_bucket": bucket,
        }
        for h in HORIZONS:
            dist = jst_calib.forward_distribution("equity", bucket, h)
            if dist:
                row[f"fwd{h}y_median_pct"] = round(dist["median"] * PCT, 1)
                row[f"fwd{h}y_p10_pct"] = round(dist["p10"] * PCT, 1)
                row[f"fwd{h}y_p90_pct"] = round(dist["p90"] * PCT, 1)
                row[f"fwd{h}y_prob_neg_pct"] = round(dist["prob_neg"] * PCT, 0)
                if h == 3:
                    row["fwd3y_n_obs"] = int(dist["n_obs"])
            else:
                row[f"fwd{h}y_median_pct"] = None
                row[f"fwd{h}y_p10_pct"] = None
                row[f"fwd{h}y_p90_pct"] = None
                row[f"fwd{h}y_prob_neg_pct"] = None
        rows.append(row)

    table = pd.DataFrame(rows).sort_values("trailing_drawdown_pct").reset_index(drop=True)
    # Column order: identity, then the three horizons grouped.
    cols = ["country", "scope", "trailing_drawdown_pct", "jst_bucket"]
    for h in HORIZONS:
        cols += [f"fwd{h}y_median_pct", f"fwd{h}y_p10_pct", f"fwd{h}y_p90_pct",
                 f"fwd{h}y_prob_neg_pct"]
    cols += ["fwd3y_n_obs"]
    return table[cols], data_asof


def build_conditional_grid() -> pd.DataFrame:
    """Flatten the full JST calibration JSON into one tidy grid (self-contained)."""
    tables = jst_calib._tables()
    if not tables:
        raise RuntimeError(
            "JST calibration tables unavailable — run scripts/calibrate_jst_bearbottom.py first."
        )
    rows = []
    for state, assets in tables.items():
        for asset, horizons in assets.items():
            for h, stat in horizons.items():
                rows.append({
                    "state": state,
                    "asset": asset,
                    "horizon_y": int(h),
                    "n_obs": int(stat["n_obs"]),
                    "mean_pct": round(stat["mean"] * PCT, 1),
                    "median_pct": round(stat["median"] * PCT, 1),
                    "std_pct": round(stat["std"] * PCT, 1),
                    "p10_pct": round(stat["p10"] * PCT, 1),
                    "p25_pct": round(stat["p25"] * PCT, 1),
                    "p75_pct": round(stat["p75"] * PCT, 1),
                    "p90_pct": round(stat["p90"] * PCT, 1),
                    "prob_neg_pct": round(stat["prob_neg"] * PCT, 0),
                })
    order = {"dd_35_plus": 0, "dd_20_35": 1, "dd_10_20": 2, "dd_0_10": 3,
             "banking_crisis": 4, "pocrisis_1_3y": 5, "normal": 6}
    grid = pd.DataFrame(rows)
    grid["_o"] = grid["state"].map(lambda s: order.get(s, 99))
    asset_o = {"equity": 0, "bond": 1, "bill": 2}
    grid["_a"] = grid["asset"].map(lambda a: asset_o.get(a, 9))
    grid = grid.sort_values(["_o", "_a", "horizon_y"]).drop(columns=["_o", "_a"])
    return grid.reset_index(drop=True)


def build_notes(data_asof: pd.Timestamp) -> pd.DataFrame:
    """Methodology / caveats as a key-value sheet."""
    bc = jst_calib.forward_distribution("equity", "banking_crisis", 3) or {}
    bc_line = (
        f"median {bc.get('median', float('nan')) * PCT:.1f}%, "
        f"p10 {bc.get('p10', float('nan')) * PCT:.1f}%, "
        f"P(neg) {bc.get('prob_neg', float('nan')) * PCT:.0f}% (n={int(bc.get('n_obs', 0))})"
    ) if bc else "unavailable"
    items = [
        ("Report", "JST long-cycle tail-risk report"),
        ("Data as-of (latest returns date)", data_asof.strftime("%Y-%m-%d")),
        ("Generated (wall clock)", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("Source", "Jordà-Schularick-Taylor Macrohistory Database R6 (1870-2020)"),
        ("Scope (directly calibrated)", "13 in-universe developed markets: "
         + ", ".join(sorted(jst_calib.JST_DM_COUNTRIES))),
        ("Returns basis", "real (CPI-deflated) annualized total returns"),
        ("Banking-crisis onsets in sample", "65"),
        ("Banking-crisis state — fwd3y real equity (reference)", bc_line),
        ("EM-analogy rows", "Countries outside the 13 DMs receive the DM-calibrated "
         "distribution as an ANALOGY — read directionally, not as a same-market estimate."),
        ("Drawdown basis", "NOMINAL trailing ~5y peak (1260 trading days); the JST "
         "distribution is REAL — coincide closely for DMs in the modern low-inflation regime."),
        ("Statistical caveat", "Tail cells use overlapping annual windows; n_obs overstates "
         "independent sample size. Treat cells as a PRIOR (distribution shape), not a t-stat."),
        ("Point-in-time", "Drawdown at as-of date; forward distribution is historical — no lookahead."),
        ("Use discipline", "Context / risk-reporting only. Anything that changes a trade or a "
         "detector severity is a signal and must clear the evaluate_signal harness first."),
    ]
    return pd.DataFrame(items, columns=["field", "value"])


def write_xlsx(country_tbl: pd.DataFrame, grid: pd.DataFrame, notes: pd.DataFrame,
               final: Path) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = final.with_suffix(".xlsx.tmp")
    with pd.ExcelWriter(tmp, engine="openpyxl") as xw:
        country_tbl.to_excel(xw, sheet_name="Country Tail Risk", index=False)
        grid.to_excel(xw, sheet_name="JST Conditional Tables", index=False)
        notes.to_excel(xw, sheet_name="Notes & Methodology", index=False)
    _atomic_replace(tmp, final)


def write_pdf(country_tbl: pd.DataFrame, data_asof: pd.Timestamp, final: Path) -> bool:
    """Light-mode forward-3y real-equity tail fan per country. Returns True on success."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # genuinely missing optional viz dep
        print(f"  [warn] matplotlib unavailable ({exc}); skipping PDF (xlsx still written).")
        return False

    df = country_tbl.dropna(subset=["fwd3y_p10_pct", "fwd3y_median_pct", "fwd3y_p90_pct"]).copy()
    df = df.sort_values("trailing_drawdown_pct", ascending=True)  # deepest first
    y = range(len(df))
    fig, ax = plt.subplots(figsize=(10, max(6, 0.34 * len(df))), facecolor="white")
    ax.set_facecolor("white")
    dm_color, em_color = "#1f5fa8", "#d9822b"
    for i, (_, r) in zip(y, df.iterrows()):
        c = dm_color if r["scope"] == "DM" else em_color
        ax.plot([r["fwd3y_p10_pct"], r["fwd3y_p90_pct"]], [i, i], color=c, lw=2.4,
                alpha=0.85, solid_capstyle="round")
        ax.plot(r["fwd3y_median_pct"], i, "o", color=c, ms=6, zorder=3)
        ax.annotate(f"{r['fwd3y_p10_pct']:.0f}", (r["fwd3y_p10_pct"], i),
                    textcoords="offset points", xytext=(-6, 0), ha="right", va="center",
                    fontsize=7, color="#444")
    ax.axvline(0, color="#888", lw=0.9, ls="--")
    ax.set_yticks(list(y))
    ax.set_yticklabels([f"{r['country']}  ({r['trailing_drawdown_pct']:.0f}% dd)"
                        for _, r in df.iterrows()], fontsize=8)
    ax.set_xlabel("Forward-3y REAL equity return — JST-calibrated p10 — median — p90 (%)",
                  fontsize=9)
    ax.set_title("JST long-cycle tail context by current drawdown bucket\n"
                 f"as-of {data_asof.strftime('%Y-%m-%d')}  ·  blue = DM (in-scope)  ·  "
                 "orange = EM-analogy  ·  context only, not a trade signal", fontsize=10)
    ax.grid(axis="x", color="#e6e6e6", lw=0.7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    tmp = final.with_suffix(".pdf.tmp")
    fig.savefig(tmp, format="pdf", facecolor="white", bbox_inches="tight")
    plt.close(fig)
    _atomic_replace(tmp, final)
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="JST long-cycle tail-risk report (read-only).")
    ap.add_argument("--date", default=None, help="As-of date YYYY-MM-DD (default: latest returns date).")
    ap.add_argument("--outdir", default=None, help="Override output directory (default: Data/loop/risk_reports).")
    args = ap.parse_args()

    asof = pd.Timestamp(args.date) if args.date else None
    out_dir = Path(args.outdir) if args.outdir else REPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    con = loop_connection(read_only=True)
    try:
        country_tbl, data_asof = build_country_table(con, asof)
        grid = build_conditional_grid()
        notes = build_notes(data_asof)
    finally:
        con.close()

    stamp = data_asof.strftime("%Y_%m_%d")
    xlsx_path = out_dir / f"jst_tail_risk_{stamp}.xlsx"
    pdf_path = out_dir / f"jst_tail_risk_{stamp}.pdf"

    write_xlsx(country_tbl, grid, notes, xlsx_path)
    pdf_ok = write_pdf(country_tbl, data_asof, pdf_path)

    deep = country_tbl[country_tbl["trailing_drawdown_pct"] <= -20.0]
    print(f"{'='*64}\n  JST TAIL-RISK REPORT  (as-of {data_asof.strftime('%Y-%m-%d')})\n{'='*64}")
    print(f"  countries covered: {len(country_tbl)}  |  in >=20% drawdown: {len(deep)}")
    print(f"  xlsx: {xlsx_path}")
    if pdf_ok:
        print(f"  pdf:  {pdf_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
