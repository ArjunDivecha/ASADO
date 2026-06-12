#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/load_consensus.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/consensus_daily.parquet
    Tidy panel from scripts/loop/collect_consensus_bbg.py: daily Bloomberg
    ECFC consensus GDP/CPI forecasts per (country, target_year), 2007+.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `consensus_daily`     — raw tidy panel (idempotent rebuild).
    Table `consensus_revisions` — month-end revision deltas per
        (country, target_year, variable): value vs 1m and 3m earlier.
    Table `consensus_signals`   — harness-ready tidy signals
        (date, country, value, variable, source):
        CONS_GDP_REV3M_12M / CONS_CPI_REV3M_12M — fixed-12-month-horizon
        blend of the 3m consensus revision (weight current target year by
        months remaining in the year, next year by months elapsed), the
        classic "consensus revision momentum" construction that removes
        the January target-year rollover discontinuity.
    Lives in the LOOP DB because setup_duckdb.py deletes the main warehouse
    monthly.

VERSION: 1.1
LAST UPDATED: 2026-06-12
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 3)

DESCRIPTION:
Loads the ECFC consensus parquet into the loop DuckDB and derives a
month-end revision surface (PRD P9 stretch): for each country, target year
and metric, how much has the consensus moved over the last 1 and 3 months?
This densifies the surprise surface between semi-annual WEO vintages —
weo_revisions tells you what changed between April and October; here you
see the drift month by month. Split from the collector because the
OpusBloomberg conda env has no duckdb.

DEPENDENCIES:
- duckdb, pandas (project venv)

USAGE:
  python scripts/loop/load_consensus.py            # rebuild both tables
  python scripts/loop/load_consensus.py --check    # verify only

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
PANEL_PATH = BASE_DIR / "Data" / "work" / "loop" / "consensus_daily.parquet"


def derive_revisions(raw: pd.DataFrame) -> pd.DataFrame:
    """Month-end consensus levels + 1m/3m revision deltas per series."""
    frames: list[pd.DataFrame] = []
    for (country, yr, var), grp in raw.groupby(["country", "target_year", "variable"]):
        s = grp.set_index("date")["value"].sort_index()
        me = s.resample("ME").last().dropna()
        if len(me) < 2:
            continue
        df = pd.DataFrame({
            "date": me.index, "country": country, "target_year": yr,
            "variable": var, "consensus": me.values,
            "rev_1m": me.diff(1).values, "rev_3m": me.diff(3).values,
        })
        frames.append(df)
    if not frames:
        raise RuntimeError("no consensus revisions derived — refusing to continue")
    return pd.concat(frames, ignore_index=True)


def derive_signals(revisions: pd.DataFrame) -> pd.DataFrame:
    """Fixed-12-month-horizon blend of 3m revisions (rollover-free signal).

    At month m (1..12) of year Y the 12-month-ahead forecast horizon spans
    (12-m)/12 of target year Y and m/12 of target year Y+1, so the blended
    revision is w*rev(Y) + (1-w)*rev(Y+1) with w = (12-m)/12. Rows where
    either leg is missing are dropped (no silent single-leg fallback).
    """
    rev = revisions.dropna(subset=["rev_3m"]).copy()
    rev["year"] = rev["date"].dt.year
    cur = rev[rev["target_year"] == rev["year"]][["date", "country", "variable", "rev_3m"]]
    nxt = rev[rev["target_year"] == rev["year"] + 1][["date", "country", "variable", "rev_3m"]]
    merged = cur.merge(nxt, on=["date", "country", "variable"], suffixes=("_cur", "_nxt"))
    if merged.empty:
        raise RuntimeError("no blended consensus signals derived — refusing to continue")
    w = (12 - merged["date"].dt.month) / 12.0
    merged["value"] = w * merged["rev_3m_cur"] + (1 - w) * merged["rev_3m_nxt"]
    merged["variable"] = merged["variable"].map(
        {"CONS_GDP_PCT": "CONS_GDP_REV3M_12M", "CONS_CPI_PCT": "CONS_CPI_REV3M_12M"})
    merged["source"] = "consensus_ecfc"
    return merged[["date", "country", "value", "variable", "source"]]


def rebuild() -> None:
    if not PANEL_PATH.exists():
        raise FileNotFoundError(f"missing {PANEL_PATH} — run collect_consensus_bbg.py first")
    raw = pd.read_parquet(PANEL_PATH)
    if raw.empty:
        raise RuntimeError(f"{PANEL_PATH} is empty — refusing to continue")
    raw["date"] = pd.to_datetime(raw["date"])
    revisions = derive_revisions(raw)

    con = loop_connection()
    try:
        con.execute("DROP TABLE IF EXISTS consensus_daily")
        con.execute(f"""
            CREATE TABLE consensus_daily AS
            SELECT CAST(date AS DATE) AS date, country, target_year, value, variable, source
            FROM read_parquet('{PANEL_PATH}')
        """)
        con.execute("DROP TABLE IF EXISTS consensus_revisions")
        con.register("rev_df", revisions)
        con.execute("""
            CREATE TABLE consensus_revisions AS
            SELECT CAST(date AS DATE) AS date, country, target_year, variable,
                   consensus, rev_1m, rev_3m
            FROM rev_df
        """)
        signals = derive_signals(revisions)
        con.execute("DROP TABLE IF EXISTS consensus_signals")
        con.register("sig_df", signals)
        con.execute("""
            CREATE TABLE consensus_signals AS
            SELECT CAST(date AS DATE) AS date, country, value, variable, source
            FROM sig_df
        """)
        for tbl in ("consensus_daily", "consensus_revisions", "consensus_signals"):
            n, lo, hi, nc = con.execute(
                f"SELECT COUNT(*), MIN(date), MAX(date), COUNT(DISTINCT country) FROM {tbl}").fetchone()
            if not n:
                raise RuntimeError(f"{tbl} rebuilt empty — refusing to continue")
            print(f"{tbl}: {n:,} rows, {nc} countries, {lo} -> {hi}")
    finally:
        con.close()


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        rows = con.execute("""
            SELECT variable, COUNT(DISTINCT country) AS nc, MAX(date) AS last
            FROM consensus_daily GROUP BY 1 ORDER BY 1
        """).fetchall()
    finally:
        con.close()
    ok = bool(rows)
    for var, nc, last in rows:
        print(f"{var}: {nc} countries, last {last}")
        if nc < 30:
            ok = False
    print("CHECK", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Load ECFC consensus parquet + derive revision surface.")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        return check()
    rebuild()
    return 0


if __name__ == "__main__":
    sys.exit(main())
