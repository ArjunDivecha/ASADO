#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: predmkt_daily_job.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
  Live warehouse holding the predmkt_* tables written by build_predmkt_panel.py.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/predmkt_archive/*.parquet
  Prior full-history parquet exports of every predmkt table (written by this
  script on earlier runs). Used to RESTORE history after a warehouse rebuild.
- (indirect) config/predmkt_curated.yaml + Kalshi/Polymarket public APIs,
  via scripts/build_predmkt_panel.py which this job invokes.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
  predmkt_* tables updated with today's snapshot (and restored history when
  a rebuild wiped it).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/predmkt_archive/{table}.parquet
  Full-table parquet export of each predmkt table after every successful run:
  predmkt_daily, predmkt_market_meta, predmkt_outcome_meta,
  predmkt_country_spillover, predmkt_resolutions, predmkt_signals_daily.

VERSION: 1.0
LAST UPDATED: 2026-06-10
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 0a)

DESCRIPTION:
Daily prediction-market job that makes the predmkt time series REBUILD-PROOF.
The problem: scripts/setup_duckdb.py deletes the whole asado.duckdb file on
each monthly rebuild, which silently destroys accumulated predmkt history
(this already happened once - the 2026-05-19 snapshot is gone). The fix, in
three steps every morning:
  1. RESTORE - if the warehouse's predmkt_daily is missing dates that exist
     in the parquet archive, insert the missing history back (never
     overwrites rows that already exist in the DB).
  2. COLLECT - run build_predmkt_panel.py to pull today's snapshot.
  3. ARCHIVE - export every predmkt table back to parquet, so the archive
     always holds the complete history.
FAIL-IS-FAIL: if the collector exits non-zero the job exits non-zero and the
archive step still runs only for restore-consistency checks, never to mask
the failure.

DEPENDENCIES:
- duckdb, pandas (project venv)

USAGE:
 python scripts/predmkt_daily_job.py          # restore -> collect -> archive
 python scripts/predmkt_daily_job.py --check  # report DB vs archive state only

NOTES:
- Scheduled by launchd: ~/Library/LaunchAgents/com.arjundivecha.asado-predmkt-daily.plist
  (daily 06:30, logs to Data/logs/predmkt_launchd.log).
- Idempotent: safe to run multiple times per day (collector rewrites today's
  snapshot; restore inserts only missing snapshot_dates; archive overwrites
  parquets with the superset).
=============================================================================
"""

from __future__ import annotations

import argparse
import os
import subprocess  # noqa: F401  (kept for compatibility; collector now runs via run_bounded)
import sys
import time
from datetime import datetime
from pathlib import Path

import duckdb

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "Data" / "asado.duckdb"
ARCHIVE_DIR = BASE_DIR / "Data" / "loop" / "predmkt_archive"
COLLECTOR = BASE_DIR / "scripts" / "build_predmkt_panel.py"

sys.path.insert(0, str(BASE_DIR))
from scripts.loop.procutil import run_bounded  # noqa: E402  bounded subprocess helper
from scripts.duckdb_lock_guard import guarded_connect  # noqa: E402


def _connect_retry(read_only: bool = False):
    """Open the main warehouse via the lock guard: kills idle sandbox-kernel
    lock squatters (e.g. ~/.claude-science kernels — these blocked the job on
    2026-07-02/03), waits out legitimate holders (the 07:30 loop's read-only
    ATTACH, a monthly setup_duckdb.py rebuild), and fails loudly only after
    the wait budget is exhausted."""
    return guarded_connect(DB_PATH, read_only=read_only)

# Tables with a snapshot_date column get date-aware restore; meta tables are
# restored whole only when entirely missing from the DB.
DATED_TABLES = ["predmkt_daily", "predmkt_signals_daily"]
META_TABLES = [
    "predmkt_market_meta",
    "predmkt_outcome_meta",
    "predmkt_country_spillover",
    "predmkt_resolutions",
]
ALL_TABLES = DATED_TABLES + META_TABLES


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [predmkt_daily_job] {msg}", flush=True)


def table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    row = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [name]
    ).fetchone()
    return bool(row and row[0])


def restore_missing_history(con: duckdb.DuckDBPyConnection) -> None:
    """Insert archived rows whose snapshot_date is absent from the live DB."""
    for t in DATED_TABLES:
        pq = ARCHIVE_DIR / f"{t}.parquet"
        if not pq.exists():
            continue
        if not table_exists(con, t):
            log(f"RESTORE: {t} missing entirely - recreating from archive")
            con.execute(f"CREATE TABLE {t} AS SELECT * FROM read_parquet(?)", [str(pq)])
            continue
        before = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        con.execute(
            f"""
            INSERT INTO {t} BY NAME
            SELECT * FROM read_parquet(?) a
            WHERE a.snapshot_date NOT IN (SELECT DISTINCT snapshot_date FROM {t})
            """,
            [str(pq)],
        )
        after = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        if after > before:
            log(f"RESTORE: {t} +{after - before} rows recovered from archive")

    # Recount loudly so restores are visible in the log
    for t in DATED_TABLES:
        if table_exists(con, t):
            cnt, dmin, dmax = con.execute(
                f"SELECT count(*), min(snapshot_date), max(snapshot_date) FROM {t}"
            ).fetchone()
            log(f"  {t}: {cnt} rows, {dmin} -> {dmax}")

    for t in META_TABLES:
        pq = ARCHIVE_DIR / f"{t}.parquet"
        if pq.exists() and not table_exists(con, t):
            log(f"RESTORE: {t} missing entirely - recreating from archive")
            con.execute(f"CREATE TABLE {t} AS SELECT * FROM read_parquet(?)", [str(pq)])


def archive_tables(con: duckdb.DuckDBPyConnection) -> None:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    for t in ALL_TABLES:
        if not table_exists(con, t):
            log(f"ARCHIVE: {t} does not exist in DB - skipped")
            continue
        pq = ARCHIVE_DIR / f"{t}.parquet"
        tmp = ARCHIVE_DIR / f"{t}.parquet.tmp"
        if tmp.exists():
            tmp.unlink()
        # Atomic: COPY to a temp file in the same dir, then rename. A kill mid-COPY
        # can no longer truncate the ONLY rebuild-proof predmkt history store.
        con.execute(f"COPY (SELECT * FROM {t}) TO '{tmp}' (FORMAT PARQUET)")
        os.replace(tmp, pq)
        cnt = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        log(f"ARCHIVE: {t} -> {pq.name} ({cnt} rows)")


def check() -> int:
    con = _connect_retry(read_only=True)
    try:
        for t in ALL_TABLES:
            db_n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] if table_exists(con, t) else "MISSING"
            pq = ARCHIVE_DIR / f"{t}.parquet"
            if pq.exists():
                ar_n = duckdb.sql(f"SELECT count(*) FROM read_parquet('{pq}')").fetchone()[0]
            else:
                ar_n = "MISSING"
            print(f"  {t}: db={db_n} archive={ar_n}")
    finally:
        con.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild-proof daily prediction-market job.")
    parser.add_argument("--check", action="store_true", help="Report DB vs archive state only.")
    args = parser.parse_args()

    if args.check:
        return check()

    # 1. RESTORE
    log("Step 1/3: restore missing history from archive (if any)")
    con = _connect_retry()
    try:
        restore_missing_history(con)
    finally:
        con.close()

    # 2. COLLECT (subprocess so the collector's own backup/restore logic runs intact)
    log("Step 2/3: run build_predmkt_panel.py")
    result = run_bounded(
        [sys.executable, str(COLLECTOR), "--stats"],
        timeout=1800, cwd=str(BASE_DIR),
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        to = " (TIMEOUT)" if getattr(result, "timed_out", False) else ""
        log(f"FAIL: collector exited {result.returncode}{to} - archive NOT updated, job failing loudly")
        return result.returncode

    # 3. ARCHIVE
    log("Step 3/3: export predmkt tables to parquet archive")
    con = _connect_retry()
    try:
        archive_tables(con)
    finally:
        con.close()

    log("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
