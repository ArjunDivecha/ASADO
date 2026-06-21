#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/load_sov_ratings.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/sov_ratings_monthly.parquet
    Tidy monthly panel written by scripts/loop/collect_sov_ratings_bql.py:
    SOV_RATING_SP / SOV_RATING_MOODY / SOV_RATING_FITCH on the 21-point
    numeric scale (33 countries, 2015+).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `sov_ratings_monthly` — idempotent rebuild from the parquet.
    Table `sov_rating_changes`  — derived dated rating-change EVENTS:
      (date, country, agency, old_score, new_score, delta)
      delta < 0 = downgrade, > 0 = upgrade, in 21-point scale notches.
      The first observation of each series is NOT a change (no event row).
    Lives in the LOOP DB because setup_duckdb.py deletes the main warehouse
    monthly.

VERSION: 1.0
LAST UPDATED: 2026-06-12
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop)

DESCRIPTION:
Loads the BQL sovereign rating history into the loop DuckDB and derives the
rating-change event table. A rating change is a dated, tradeable event —
the event table is what event studies and the dislocation brief join on
(e.g. "CDS was already 2 sigma wide three weeks before the S&P downgrade").

DEPENDENCIES:
- duckdb, pandas (project venv)

USAGE:
  python scripts/loop/load_sov_ratings.py            # rebuild tables
  python scripts/loop/load_sov_ratings.py --check    # verify only

NOTES:
- Fails loudly if the parquet is missing or empty (FAIL-IS-FAIL).
=============================================================================
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.loop.loopdb import loop_connection  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PANEL_PATH = BASE_DIR / "Data" / "work" / "loop" / "sov_ratings_monthly.parquet"

AGENCY = {"SOV_RATING_SP": "SP", "SOV_RATING_MOODY": "MOODY", "SOV_RATING_FITCH": "FITCH"}


def build_changes(panel: pd.DataFrame) -> pd.DataFrame:
    """Dated rating-change events: one row per (country, agency) month where
    the numeric score moved vs the prior observation."""
    rows = []
    for (country, variable), g in panel.groupby(["country", "variable"]):
        s = g.set_index("date")["value"].sort_index()
        prev = s.shift(1)
        chg = s[(s != prev) & prev.notna()]
        for d, new in chg.items():
            old = float(prev.loc[d])
            rows.append({"date": d, "country": country, "agency": AGENCY[variable],
                         "old_score": old, "new_score": float(new),
                         "delta": float(new) - old})
    if not rows:
        raise RuntimeError("no rating changes derived — input looks degenerate, refusing to write")
    return pd.DataFrame(rows).sort_values(["date", "country", "agency"]).reset_index(drop=True)


def rebuild() -> None:
    if not PANEL_PATH.exists():
        raise FileNotFoundError(f"missing {PANEL_PATH} — run collect_sov_ratings_bql.py first")
    panel = pd.read_parquet(PANEL_PATH)
    if panel.empty:
        raise RuntimeError(f"{PANEL_PATH} is empty — refusing to continue")
    panel["date"] = pd.to_datetime(panel["date"])
    changes = build_changes(panel)

    con = loop_connection()
    try:
        con.execute("DROP TABLE IF EXISTS sov_ratings_monthly")
        con.execute(f"""
            CREATE TABLE sov_ratings_monthly AS
            SELECT CAST(date AS DATE) AS date, country, value, variable, source
            FROM read_parquet('{PANEL_PATH}')
        """)
        con.execute("DROP TABLE IF EXISTS sov_rating_changes")
        con.register("changes_df", changes)
        con.execute("""
            CREATE TABLE sov_rating_changes AS
            SELECT CAST(date AS DATE) AS date, country, agency,
                   old_score, new_score, delta
            FROM changes_df
        """)
        n, lo, hi = con.execute(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM sov_ratings_monthly").fetchone()
        if not n:
            raise RuntimeError("sov_ratings_monthly rebuilt empty — refusing to continue")
        print(f"sov_ratings_monthly: {n:,} rows, {lo} -> {hi}")
        nch, ndn, nup = con.execute("""
            SELECT COUNT(*), SUM(CASE WHEN delta < 0 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN delta > 0 THEN 1 ELSE 0 END)
            FROM sov_rating_changes""").fetchone()
        print(f"sov_rating_changes: {nch} events ({ndn} downgrades, {nup} upgrades)")
    finally:
        con.close()


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        rows = con.execute("""
            SELECT variable, COUNT(DISTINCT country) AS nc, MAX(date) AS last
            FROM sov_ratings_monthly GROUP BY 1 ORDER BY 1
        """).fetchall()
        n_chg = con.execute("SELECT COUNT(*) FROM sov_rating_changes").fetchone()[0]
    finally:
        con.close()
    ok = bool(rows) and n_chg > 0
    for var, nc, last in rows:
        print(f"{var}: {nc} countries, last {last}")
        if nc < 28:
            ok = False
    print(f"sov_rating_changes: {n_chg} events")
    print("CHECK", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Load BQL sovereign ratings into loop DuckDB + derive change events.")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        return check()
    try:
        rebuild()
    except FileNotFoundError as exc:
        print(f"PARTIAL: {exc} — BBG collector may not have run yet", flush=True)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
