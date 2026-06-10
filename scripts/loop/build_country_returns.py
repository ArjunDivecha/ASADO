#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: build_country_returns.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
  Main warehouse (read-only). Source rows: feature_panel where source='t2'
  and variable='1MRet' (monthly) - the canonical T2 country return series.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/country_mapping.json
  The 34-country T2 universe filter (feature_panel leaks 9 extra countries
  from multi-country sources; they are excluded here).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
  Table `country_returns_monthly(date, country, return_1m)`.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/country_returns_monthly.parquet
  Same data as parquet (survives any DB mishap; diffable; vintage-able).

VERSION: 1.0
LAST UPDATED: 2026-06-10
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 0c)

DESCRIPTION:
Materializes the canonical monthly country-return table the whole loop marks
against (theses, harness backtests, calibration). One row per (month,
country) for the 34 T2 countries.

DATE-LABEL SEMANTICS (verified empirically 2026-06-10 by compounding daily
1DRet within calendar months and matching against 1MRet):
  - `date` is the FIRST OF THE MONTH the return was earned IN.
    e.g. date=2026-04-01, return_1m=0.1049 means "April 2026 returned +10.49%".
  - `return_1m` is a DECIMAL fraction (0.05 = +5%), not percent.
  - The current (incomplete) month is NaN in the source and is EXCLUDED here,
    so the table never contains a partial month.
  - PIT rule for consumers: at a decision date inside month M, the last
    knowable row is month M-1. The harness enforces this; do not rely on
    caller discipline.

DEPENDENCIES:
- duckdb, pandas (project venv)

USAGE:
 python scripts/loop/build_country_returns.py          # rebuild table + parquet
 python scripts/loop/build_country_returns.py --check  # verify existing table

NOTES:
- Idempotent full rebuild each run (source of truth is the warehouse; this
  is a derived cache, cheap to recompute).
- Data quality gates (hard failures): >= 28 countries per month from 2000-03
  onward, no duplicate (date, country), all values in [-0.95, +3.0].
=============================================================================
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.loop.loopdb import LOOP_DIR, loop_connection, t2_countries

PARQUET_OUT = LOOP_DIR / "country_returns_monthly.parquet"


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} [country_returns] {msg}", flush=True)


def build() -> int:
    countries = t2_countries()
    con = loop_connection()
    try:
        placeholders = ",".join("?" for _ in countries)
        df = con.execute(
            f"""
            SELECT date, country, value AS return_1m
            FROM asado.feature_panel
            WHERE source = 't2'
              AND variable = '1MRet'
              AND value IS NOT NULL
              AND country IN ({placeholders})
            ORDER BY date, country
            """,
            countries,
        ).fetchdf()

        # ── Quality gates (FAIL-IS-FAIL) ────────────────────────────────
        dupes = df.duplicated(subset=["date", "country"]).sum()
        if dupes:
            raise ValueError(f"{dupes} duplicate (date, country) rows - aborting")

        bad = df[(df["return_1m"] < -0.95) | (df["return_1m"] > 3.0)]
        if len(bad):
            raise ValueError(f"{len(bad)} rows outside [-0.95, +3.0] - units broken? {bad.head()}")

        cov = df[df["date"] >= "2000-03-01"].groupby("date")["country"].nunique()
        thin = cov[cov < 28]
        if len(thin):
            raise ValueError(f"{len(thin)} months with < 28 countries: {thin.tail()}")

        con.execute("DROP TABLE IF EXISTS country_returns_monthly")
        con.execute("CREATE TABLE country_returns_monthly AS SELECT * FROM df")
        con.execute(f"COPY country_returns_monthly TO '{PARQUET_OUT}' (FORMAT PARQUET)")

        n, dmin, dmax, nc = con.execute(
            "SELECT count(*), min(date), max(date), count(DISTINCT country) FROM country_returns_monthly"
        ).fetchone()
        log(f"country_returns_monthly: {n} rows, {dmin} -> {dmax}, {nc} countries")
        log(f"parquet: {PARQUET_OUT}")
        return 0
    finally:
        con.close()


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        n, dmin, dmax, nc = con.execute(
            "SELECT count(*), min(date), max(date), count(DISTINCT country) FROM country_returns_monthly"
        ).fetchone()
        print(f"country_returns_monthly: {n} rows, {dmin} -> {dmax}, {nc} countries")
        recent = con.execute(
            """
            SELECT date, count(*) AS n, round(avg(return_1m) * 100, 2) AS avg_ret_pct
            FROM country_returns_monthly GROUP BY date ORDER BY date DESC LIMIT 4
            """
        ).fetchdf()
        print(recent.to_string(index=False))
        return 0
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize country_returns_monthly in the loop DB.")
    parser.add_argument("--check", action="store_true", help="Verify existing table only.")
    args = parser.parse_args()
    return check() if args.check else build()


if __name__ == "__main__":
    sys.exit(main())
