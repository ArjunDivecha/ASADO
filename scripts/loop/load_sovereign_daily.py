#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/load_sovereign_daily.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/sovereign_daily.parquet
    Tidy daily panel written by scripts/loop/collect_sovereign_daily_bbg.py:
    SOV_CDS_5Y_BP (20 countries, 2005+) and SOV_10Y_YIELD_PCT (32 countries).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `sovereign_daily` (idempotent rebuild from the parquet). Lives in
    the LOOP DB because setup_duckdb.py deletes the main warehouse monthly.

VERSION: 1.0
LAST UPDATED: 2026-06-11
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 3)

DESCRIPTION:
Loads the Bloomberg sovereign CDS/10Y parquet into the loop DuckDB. Split
from the collector because the OpusBloomberg conda env (where blpapi lives)
has no duckdb, and the project venv has no blpapi. Same split as
collect_foreign_flows_bbg.py / collect_foreign_flows.py.

DEPENDENCIES:
- duckdb, pandas (project venv)

USAGE:
  python scripts/loop/load_sovereign_daily.py            # rebuild table
  python scripts/loop/load_sovereign_daily.py --check    # verify only

NOTES:
- Fails loudly if the parquet is missing or empty (FAIL-IS-FAIL).
=============================================================================
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.loop.loopdb import loop_connection  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PANEL_PATH = BASE_DIR / "Data" / "work" / "loop" / "sovereign_daily.parquet"


def rebuild() -> None:
    if not PANEL_PATH.exists():
        raise FileNotFoundError(f"missing {PANEL_PATH} — run collect_sovereign_daily_bbg.py first")
    con = loop_connection()
    try:
        con.execute("DROP TABLE IF EXISTS sovereign_daily")
        con.execute(
            f"""
            CREATE TABLE sovereign_daily AS
            SELECT CAST(date AS DATE) AS date, country, value, variable, source
            FROM read_parquet('{PANEL_PATH}')
            """
        )
        n, lo, hi = con.execute(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM sovereign_daily").fetchone()
        if not n:
            raise RuntimeError("sovereign_daily rebuilt empty — refusing to continue")
        print(f"sovereign_daily: {n:,} rows, {lo} -> {hi}")
        for var, nc, last in con.execute(
            "SELECT variable, COUNT(DISTINCT country), MAX(date) FROM sovereign_daily GROUP BY 1 ORDER BY 1"
        ).fetchall():
            print(f"  {var}: {nc} countries, last {last}")
    finally:
        con.close()


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        rows = con.execute(
            """
            SELECT variable, COUNT(DISTINCT country) AS nc, MAX(date) AS last
            FROM sovereign_daily GROUP BY 1 ORDER BY 1
            """
        ).fetchall()
    finally:
        con.close()
    ok = True
    for var, nc, last in rows:
        print(f"{var}: {nc} countries, last {last}")
        if var == "SOV_CDS_5Y_BP" and nc < 18:
            ok = False
        if var == "SOV_10Y_YIELD_PCT" and nc < 28:
            ok = False
    if not rows:
        ok = False
    print("CHECK", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Load sovereign CDS/10Y parquet into loop DuckDB.")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        return check()
    rebuild()
    return 0


if __name__ == "__main__":
    sys.exit(main())
