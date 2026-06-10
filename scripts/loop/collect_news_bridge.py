#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: collect_news_bridge.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/News/data/report.db
  SQLite DB maintained by the separate News repo. Tables read (read-only):
    portfolio_snapshots  - live Schwab/IBKR holdings, ONE date only (the repo
                           overwrites it daily - that is exactly why this
                           bridge must accumulate history on our side)
    portfolio_summary    - one-row daily account summary
    prices               - ~800 ETF daily closes, rolling 1-year window
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/etf_t2_map.json
  Canonical country ETF per T2 country (curated).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
  Tables (loop DB - NEVER the main warehouse, holdings stay out of
  explanatory panels per PRD section 12 non-goals):
    portfolio_holdings_daily  - accumulated daily position snapshots
    portfolio_summary_daily   - accumulated daily account summaries
    etf_prices_daily          - accumulated ETF closes (union over time, so
                                history grows past the source's 1y window)
    etf_t2_map                - country -> primary/alternate ETF mapping
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/news_bridge_archive/*.parquet
  Full-table parquet exports after each successful run (belt and braces).

VERSION: 1.0
LAST UPDATED: 2026-06-10
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop / News bridge)

DESCRIPTION:
Pulls live portfolio holdings and ETF prices from the News repo into the
Alpha-Hunting Loop's own database, accumulating history that the source
overwrites. Why it matters: (1) the daily brief must show open positions
next to new setups - stewardship needs holdings; (2) detector D8 (holdings
vs deteriorating thesis) and D9 (country index vs US-listed ETF gap) need
these surfaces; (3) the News repo keeps only ONE day of holdings and a
rolling year of prices, so every day we don't accumulate is data lost.
A 10th grader's version: the other program wipes its whiteboard every
morning; this script photographs the whiteboard daily and files the photos.

DEPENDENCIES:
- duckdb, pandas (project venv); sqlite3 (stdlib)

USAGE:
 python scripts/loop/collect_news_bridge.py          # accumulate today's data
 python scripts/loop/collect_news_bridge.py --check  # report stored state

NOTES:
- Idempotent per day: re-running replaces the same source dates, never
  duplicates them.
- FAIL-IS-FAIL: missing source DB or empty pulls abort loudly. A stale
  holdings snapshot (holdings_stale=1) is stored but flagged in the log.
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.loop.loopdb import BASE_DIR, LOOP_DIR, loop_connection, t2_countries

NEWS_DB = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/News/data/report.db")
ETF_MAP_PATH = BASE_DIR / "config" / "etf_t2_map.json"
ARCHIVE_DIR = LOOP_DIR / "news_bridge_archive"

TABLES = {
    "portfolio_holdings_daily": "date",
    "portfolio_summary_daily": "date",
    "etf_prices_daily": "date",
}


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} [news_bridge] {msg}", flush=True)


def upsert_by_date(con, table: str, df: pd.DataFrame) -> tuple[int, int]:
    """Replace rows for the dates present in df; keep all other history."""
    if df.empty:
        raise ValueError(f"Refusing to upsert empty frame into {table} (FAIL-IS-FAIL)")
    exists = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [table]
    ).fetchone()[0]
    if not exists:
        con.execute(f"CREATE TABLE {table} AS SELECT * FROM df")
        return len(df), 0
    dates = sorted(df["date"].unique().tolist())
    placeholders = ",".join("?" for _ in dates)
    deleted = con.execute(
        f"DELETE FROM {table} WHERE date IN ({placeholders})", dates
    ).fetchone()
    con.execute(f"INSERT INTO {table} SELECT * FROM df")
    del deleted
    return len(df), len(dates)


def collect() -> int:
    if not NEWS_DB.exists():
        raise FileNotFoundError(f"News repo DB not found: {NEWS_DB}")

    src = sqlite3.connect(f"file:{NEWS_DB}?mode=ro", uri=True)
    try:
        holdings = pd.read_sql("SELECT * FROM portfolio_snapshots", src)
        summary = pd.read_sql("SELECT * FROM portfolio_summary", src)
        prices = pd.read_sql("SELECT date, yf_ticker, close, volume FROM prices", src)
    finally:
        src.close()

    if holdings.empty or prices.empty:
        raise ValueError(
            f"Empty pull from News DB (holdings={len(holdings)}, prices={len(prices)}) - aborting"
        )

    for df in (holdings, summary, prices):
        df["date"] = pd.to_datetime(df["date"]).dt.date.astype(str)

    stale = holdings["holdings_stale"].max() if "holdings_stale" in holdings else 0
    if stale:
        log("WARNING: source marks holdings_stale=1 (positions not refreshed from broker today)")

    etf_map = json.loads(ETF_MAP_PATH.read_text())["map"]
    missing = [c for c in t2_countries() if c not in etf_map]
    if missing:
        raise ValueError(f"etf_t2_map.json missing countries: {missing}")
    map_rows = pd.DataFrame(
        [
            {"country": c, "etf_primary": v["primary"], "etf_alternates": ",".join(v["alternates"])}
            for c, v in etf_map.items()
        ]
    )

    con = loop_connection()
    try:
        n, d = upsert_by_date(con, "portfolio_holdings_daily", holdings)
        log(f"portfolio_holdings_daily: +{n} rows ({d} date(s) replaced)")
        n, d = upsert_by_date(con, "portfolio_summary_daily", summary)
        log(f"portfolio_summary_daily: +{n} rows ({d} date(s) replaced)")
        n, d = upsert_by_date(con, "etf_prices_daily", prices)
        log(f"etf_prices_daily: +{n} rows ({d} date(s) replaced)")

        con.execute("DROP TABLE IF EXISTS etf_t2_map")
        con.execute("CREATE TABLE etf_t2_map AS SELECT * FROM map_rows")
        log(f"etf_t2_map: {len(map_rows)} countries")

        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        for table in list(TABLES) + ["etf_t2_map"]:
            pq = ARCHIVE_DIR / f"{table}.parquet"
            con.execute(f"COPY (SELECT * FROM {table}) TO '{pq}' (FORMAT PARQUET)")

        for table in TABLES:
            cnt, d0, d1 = con.execute(
                f"SELECT count(*), min(date), max(date) FROM {table}"
            ).fetchone()
            log(f"  {table}: {cnt} rows, {d0} -> {d1}")
    finally:
        con.close()
    return 0


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        for table in list(TABLES) + ["etf_t2_map"]:
            exists = con.execute(
                "SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [table]
            ).fetchone()[0]
            if not exists:
                print(f"  {table}: MISSING")
                continue
            if table == "etf_t2_map":
                cnt = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                print(f"  {table}: {cnt} countries")
            else:
                cnt, d0, d1, nd = con.execute(
                    f"SELECT count(*), min(date), max(date), count(DISTINCT date) FROM {table}"
                ).fetchone()
                print(f"  {table}: {cnt} rows, {d0} -> {d1} ({nd} distinct dates)")
    finally:
        con.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Accumulate News-repo holdings + ETF prices into the loop DB.")
    parser.add_argument("--check", action="store_true", help="Report stored state only.")
    args = parser.parse_args()
    return check() if args.check else collect()


if __name__ == "__main__":
    sys.exit(main())
