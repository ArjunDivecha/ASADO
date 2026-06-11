#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/calibration_report.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    thesis_ledger      (folded thesis state, from ledgers.py --rebuild)
    thesis_marks       (per-thesis daily marks)
    dislocation_daily  (joined on source_dislocation_id -> detector/archetype)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime/results/regime_tags.parquet
    Monthly regime tag, matched to each thesis's open month (context only).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/calibration/calibration_YYYY_MM.md
    The monthly calibration report (markdown; current month, regenerated
    nightly so it is always live; previous months freeze naturally).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/calibration/calibration_YYYY_MM.xlsx
    Per-thesis detail behind the report (one row per closed/open thesis).

VERSION: 1.0
LAST UPDATED: 2026-06-11
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 4)

DESCRIPTION:
PRD section 6.3: the monthly calibration report. Every thesis was opened with
a stated probability; every mechanical close produced an outcome (hit=1,
miss/invalidated=0) and a Brier contribution (probability - outcome)^2.
This script aggregates them: overall Brier score and hit rate, then sliced
by archetype, by horizon bucket, by direction, by regime-at-open, plus a
calibration curve (stated-probability buckets vs realized hit rate).
A 10th grader's version: if you said "58% sure" on a bunch of trades, did
58% of them actually work? The Brier score is the penalty for being wrong
AND for being over/under-confident.

PARTIAL-DATA BEHAVIOR (by design, not a fallback): the PRD gates Phase 4
acceptance on >= 10 closed theses. Until then this report still runs and
prints everything it can, clearly stamped "PARTIAL (n closed < 10)". It
never fabricates and never blocks the nightly job.

DEPENDENCIES:
- duckdb, pandas, openpyxl (project venv)

USAGE:
 python scripts/loop/calibration_report.py            # write current-month report
 python scripts/loop/calibration_report.py --check    # print summary to stdout

NOTES:
- Overrides of optimizer output are logged as theses too (author field) and
  are therefore automatically calibration data - PRD's override-feedback fix.
- regime-at-open uses the regime tag of the open month (monthly tags).
=============================================================================
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.loop.loopdb import BASE_DIR, LOOP_DIR, loop_connection  # noqa: E402

OUT_DIR = LOOP_DIR / "calibration"
REGIME_TAGS = BASE_DIR / "regime" / "results" / "regime_tags.parquet"
MIN_CLOSED_FULL = 10          # PRD Phase 4 acceptance threshold
PROB_BUCKETS = [(0.5, 0.55), (0.55, 0.6), (0.6, 0.7), (0.7, 1.0)]


def log(msg: str) -> None:
    print(f"[calibration] {msg}", flush=True)


def load_theses() -> pd.DataFrame:
    """All theses joined with detector/archetype and regime-at-open."""
    con = loop_connection(read_only=True)
    try:
        df = con.execute("""
            SELECT t.*, d.detector, d.archetype AS dislocation_archetype
            FROM thesis_ledger t
            LEFT JOIN (SELECT DISTINCT dislocation_id, detector, archetype
                       FROM dislocation_daily) d
              ON t.source_dislocation_id = d.dislocation_id
        """).fetchdf()
        marks = con.execute("""
            SELECT thesis_id, MAX(cum_return) AS best_mark, MIN(cum_return) AS worst_mark,
                   MAX(days_open) AS days_marked
            FROM thesis_marks GROUP BY 1
        """).fetchdf()
    finally:
        con.close()
    df = df.merge(marks, on="thesis_id", how="left")

    df["archetype"] = df["dislocation_archetype"].fillna("manual")
    df["horizon_bucket"] = pd.cut(df["horizon_days"], bins=[0, 21, 42, 10_000],
                                  labels=["<=21d", "22-42d", ">42d"])
    # Regime at open: monthly tag of the open month (context only).
    df["regime_at_open"] = None
    if REGIME_TAGS.exists():
        tags = pd.read_parquet(REGIME_TAGS)[["date", "regime"]]
        tags["month"] = pd.to_datetime(tags["date"]).dt.to_period("M")
        tag_map = tags.set_index("month")["regime"]
        open_month = pd.to_datetime(df["open_date"]).dt.to_period("M")
        df["regime_at_open"] = open_month.map(tag_map)
    return df


def _slice_table(closed: pd.DataFrame, by: str) -> pd.DataFrame:
    g = closed.groupby(by, observed=True)
    out = pd.DataFrame({
        "n": g.size(),
        "hit_rate": g["outcome"].mean(),
        "brier": g["brier_contribution"].mean(),
        "avg_return": g["realized_return"].mean(),
    })
    return out.round(3)


def build_report(df: pd.DataFrame) -> tuple[list[str], dict[str, pd.DataFrame]]:
    now = datetime.now()
    closed = df[df["status"].isin(["hit", "miss", "invalidated"])].copy()
    open_t = df[df["status"] == "open"]
    n_closed = len(closed)
    partial = n_closed < MIN_CLOSED_FULL

    lines = [
        f"# Calibration report — {now.strftime('%B %Y')}",
        "",
        f"Generated {now.strftime('%Y-%m-%d %H:%M')} (regenerated nightly; PRD section 6.3).",
        "",
        f"**Status: {'PARTIAL — ' + str(n_closed) + ' closed theses < ' + str(MIN_CLOSED_FULL) + ' (Phase 4 gate)' if partial else 'FULL'}**",
        "",
        "## Headline",
        "",
        f"- Theses: {len(df)} total — {len(open_t)} open, {n_closed} closed"
        f" ({int((df['status'] == 'killed_review').sum())} killed in review)",
    ]
    tables: dict[str, pd.DataFrame] = {}

    if n_closed:
        brier = closed["brier_contribution"].mean()
        hit = closed["outcome"].mean()
        lines += [
            f"- Hit rate: {hit:.0%} ({int(closed['outcome'].sum())}/{n_closed})",
            f"- Brier score: {brier:.3f} (0 = clairvoyant, 0.25 = coin-flip at p=0.5)",
            f"- Avg realized return (signed): {closed['realized_return'].mean():+.2%}",
            f"- Invalidation stops hit: {int((closed['status'] == 'invalidated').sum())}",
        ]
        for title, col in [("By archetype", "archetype"), ("By horizon", "horizon_bucket"),
                           ("By direction", "direction"), ("By regime at open", "regime_at_open"),
                           ("By author (overrides are calibration data too)", "author")]:
            t = _slice_table(closed, col)
            if t.empty:
                continue
            tables[col] = t
            lines += ["", f"## {title}", "", t.to_markdown()]

        # Calibration curve: stated probability vs realized frequency
        rows = []
        for lo, hi in PROB_BUCKETS:
            b = closed[(closed["probability"] >= lo) & (closed["probability"] < hi)]
            if len(b):
                rows.append({"stated_p": f"[{lo:.2f}, {hi:.2f})", "n": len(b),
                             "realized_hit_rate": round(b["outcome"].mean(), 3),
                             "avg_stated_p": round(b["probability"].mean(), 3)})
        if rows:
            curve = pd.DataFrame(rows).set_index("stated_p")
            tables["calibration_curve"] = curve
            lines += ["", "## Calibration curve", "",
                      "Well-calibrated = realized_hit_rate tracks avg_stated_p.", "",
                      curve.to_markdown()]
    else:
        lines += ["- No closed theses yet — calibration math starts at the first mechanical close."]

    if len(open_t):
        lines += ["", "## Open theses", ""]
        for r in open_t.itertuples():
            mark = f"{r.best_mark:+.1%}/{r.worst_mark:+.1%} best/worst" if pd.notna(r.best_mark) else "no marks yet"
            lines += [f"- **{r.thesis_id}** {r.direction} {r.entity} h={r.horizon_days}d "
                      f"p={r.probability:.2f} ({mark})"]

    if partial:
        lines += ["", "---", "",
                  f"*Phase 4 acceptance needs >= {MIN_CLOSED_FULL} closed theses; "
                  f"currently {n_closed}. This scaffold reports whatever exists and never extrapolates.*"]
    return lines, tables


def run(check_only: bool = False) -> int:
    df = load_theses()
    if df.empty:
        log("thesis_ledger is empty — nothing to report (run ledgers.py --rebuild first)")
        return 1
    lines, tables = build_report(df)

    if check_only:
        print("\n".join(lines))
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y_%m")
    md_path = OUT_DIR / f"calibration_{stamp}.md"
    md_path.write_text("\n".join(lines) + "\n")

    xlsx_path = OUT_DIR / f"calibration_{stamp}.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as xw:
        df.drop(columns=["entry_thesis_text"]).to_excel(xw, sheet_name="theses", index=False)
        df[["thesis_id", "entry_thesis_text"]].to_excel(xw, sheet_name="thesis_texts", index=False)
        for name, t in tables.items():
            t.to_excel(xw, sheet_name=name[:31])
    log(f"report: {md_path}")
    log(f"detail: {xlsx_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Monthly thesis calibration report (PRD 6.3).")
    parser.add_argument("--check", action="store_true", help="print to stdout, write nothing")
    args = parser.parse_args()
    return run(check_only=args.check)


if __name__ == "__main__":
    sys.exit(main())
