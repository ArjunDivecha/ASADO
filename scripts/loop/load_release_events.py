#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/load_release_events.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/release_events.parquet
    41,349 release-date-stamped economic events across 213 Bloomberg ECO tickers
    covering 31 countries and 10 macro concepts (1996-2026), originally built &
    verified in Economic Surprise Lab (ESL Phase R2).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `release_events_daily` — full point-in-time release-date stamped event panel
    with expanding-window winsorized surprise z-scores, broadcast to the 34-country T2 universe.
    Table `release_events_signals` — daily tidy signal panel for point-in-time joining
    and event study execution.

VERSION: 1.0
LAST UPDATED: 2026-08-13
AUTHOR: Arjun Divecha (Alpha-Hunting Loop)

DESCRIPTION:
Ingests release-date-stamped economic surprises into the ASADO loop database.
Unlike the reference-period monthly surprise table (eco_surprise_monthly), this layer
preserves the exact announcement date (release_date) and tradeable date (signal_date),
enabling true anchor=next_day daily event studies, short-horizon dislocation detection,
and composite growth/inflation/sentiment surprise tracking across 10 concepts:
  cpi, core_cpi, ppi, gdp, unemp, employment, pmi, ip, retail_sales, consumer_confidence.

DEPENDENCIES:
- duckdb, pandas, numpy (project venv)

USAGE:
  python scripts/loop/load_release_events.py            # rebuild tables
  python scripts/loop/load_release_events.py --check    # verify only
=============================================================================
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.loop.loopdb import loop_connection  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PANEL_PATH = BASE_DIR / "Data" / "work" / "loop" / "release_events.parquet"

BROADCAST = {
    "United States": ["U.S.", "NASDAQ", "US SmallCap"],
    "China": ["ChinaA", "ChinaH"],
}

CONCEPT_VAR_MAP = {
    "cpi": "RELEASE_CPI_SURPRISE_Z",
    "core_cpi": "RELEASE_CORE_CPI_SURPRISE_Z",
    "ppi": "RELEASE_PPI_SURPRISE_Z",
    "gdp": "RELEASE_GDP_SURPRISE_Z",
    "unemp": "RELEASE_UNEMP_SURPRISE_Z",
    "employment": "RELEASE_EMPLOYMENT_SURPRISE_Z",
    "pmi": "RELEASE_PMI_SURPRISE_Z",
    "ip": "RELEASE_IP_SURPRISE_Z",
    "retail_sales": "RELEASE_RETAIL_SURPRISE_Z",
    "consumer_confidence": "RELEASE_SENTIMENT_SURPRISE_Z",
}


def calc_expanding_z(df: pd.DataFrame, min_obs: int = 12, max_z: float = 3.0) -> pd.Series:
    """Compute point-in-time expanding-window surprise z-score.
    Surprise is scaled by historical std of past surprises (shifted by 1 so the
    current observation never inflates its own denominator). Mean is not subtracted
    because consensus surprises are zero-mean by construction.
    """
    s = df["surprise"]
    sd = s.shift(1).expanding(min_periods=min_obs).std()
    z = s / sd
    z = z.replace([np.inf, -np.inf], np.nan)
    return z.clip(-max_z, max_z)


def prepare_release_events(raw_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Process raw parquet into broadcasted daily events table and tidy daily signals."""
    df = raw_df.copy()
    df["release_date"] = pd.to_datetime(df["release_date"]).dt.date
    df["signal_date"] = pd.to_datetime(df["signal_date"]).dt.date
    df["reference_period"] = pd.to_datetime(df["reference_period"]).dt.date

    df["surprise"] = df["actual_first_print"] - df["bn_survey_median"]
    df = df.sort_values("release_date")

    # Compute expanding z-score per macro country + concept
    df["surprise_z"] = df.groupby(["country", "concept"], group_keys=False).apply(calc_expanding_z)

    # Broadcast to T2 equity universe
    event_rows: list[dict] = []
    for _, row in df.iterrows():
        macro_c = row["country"]
        t2_targets = BROADCAST.get(macro_c, [macro_c])
        for target_c in t2_targets:
            event_rows.append({
                "release_date": row["release_date"],
                "signal_date": row["signal_date"],
                "reference_period": row["reference_period"],
                "country": target_c,
                "macro_country": macro_c,
                "concept": row["concept"],
                "ticker": row["ticker"],
                "actual_first_print": row["actual_first_print"],
                "bn_survey_median": row["bn_survey_median"],
                "surprise": row["surprise"],
                "surprise_z": row["surprise_z"],
                "release_date_source": row["release_date_source"],
            })

    events_daily = pd.DataFrame(event_rows)

    # Build tidy daily signals from valid surprise_z rows
    valid_z = events_daily[events_daily["surprise_z"].notnull()].copy()
    signal_frames: list[pd.DataFrame] = []

    # 1. Per-concept signals
    for concept, var_name in CONCEPT_VAR_MAP.items():
        sub = valid_z[valid_z["concept"] == concept]
        if sub.empty:
            continue
        # Deduplicate multiple prints on same signal_date for same country by taking the mean z
        agg = sub.groupby(["signal_date", "country"])["surprise_z"].mean().reset_index()
        agg.rename(columns={"signal_date": "date", "surprise_z": "value"}, inplace=True)
        agg["variable"] = var_name
        agg["source"] = "derived"
        signal_frames.append(agg[["date", "country", "value", "variable", "source"]])

    # 2. Composite growth surprise signal (GDP, PMI, IP, Retail Sales, Employment, -Unemp)
    growth_concepts_pos = ["gdp", "pmi", "ip", "retail_sales", "employment"]
    growth_sub = valid_z[valid_z["concept"].isin(growth_concepts_pos + ["unemp"])].copy()
    growth_sub["dir_z"] = np.where(growth_sub["concept"] == "unemp", -growth_sub["surprise_z"], growth_sub["surprise_z"])
    growth_agg = growth_sub.groupby(["signal_date", "country"])["dir_z"].mean().reset_index()
    growth_agg.rename(columns={"signal_date": "date", "dir_z": "value"}, inplace=True)
    growth_agg["variable"] = "RELEASE_GROWTH_SURPRISE_Z"
    growth_agg["source"] = "derived"
    signal_frames.append(growth_agg[["date", "country", "value", "variable", "source"]])

    # 3. Composite inflation surprise signal (CPI, Core CPI, PPI)
    infl_concepts = ["cpi", "core_cpi", "ppi"]
    infl_sub = valid_z[valid_z["concept"].isin(infl_concepts)]
    infl_agg = infl_sub.groupby(["signal_date", "country"])["surprise_z"].mean().reset_index()
    infl_agg.rename(columns={"signal_date": "date", "surprise_z": "value"}, inplace=True)
    infl_agg["variable"] = "RELEASE_INFL_SURPRISE_Z"
    infl_agg["source"] = "derived"
    signal_frames.append(infl_agg[["date", "country", "value", "variable", "source"]])

    signals_daily = pd.concat(signal_frames, ignore_index=True)
    return events_daily, signals_daily


def rebuild() -> None:
    if not PANEL_PATH.exists():
        raise FileNotFoundError(f"missing {PANEL_PATH}")
    raw = pd.read_parquet(PANEL_PATH)
    if raw.empty:
        raise RuntimeError(f"{PANEL_PATH} is empty — refusing to continue")

    events_daily, signals_daily = prepare_release_events(raw)

    con = loop_connection()
    try:
        con.execute("DROP TABLE IF EXISTS release_events_daily")
        con.register("events_df", events_daily)
        con.execute("""
            CREATE TABLE release_events_daily AS
            SELECT CAST(release_date AS DATE) AS release_date,
                   CAST(signal_date AS DATE) AS signal_date,
                   CAST(reference_period AS DATE) AS reference_period,
                   country,
                   macro_country,
                   concept,
                   ticker,
                   actual_first_print,
                   bn_survey_median,
                   surprise,
                   surprise_z,
                   release_date_source
            FROM events_df
        """)

        con.execute("DROP TABLE IF EXISTS release_events_signals")
        con.register("signals_df", signals_daily)
        con.execute("""
            CREATE TABLE release_events_signals AS
            SELECT CAST(date AS DATE) AS date,
                   country,
                   value,
                   variable,
                   source
            FROM signals_df
        """)

        for table, date_col in [("release_events_daily", "release_date"), ("release_events_signals", "date")]:
            n, lo, hi = con.execute(f"SELECT COUNT(*), MIN({date_col}), MAX({date_col}) FROM {table}").fetchone()
            if not n:
                raise RuntimeError(f"{table} rebuilt empty — refusing to continue")
            print(f"{table}: {n:,} rows, {lo} -> {hi}")

        for var, nc, last in con.execute("""
            SELECT variable, COUNT(DISTINCT country), MAX(date)
            FROM release_events_signals GROUP BY 1 ORDER BY 1
        """).fetchall():
            print(f"  {var}: {nc} countries, last {last}")
    finally:
        con.close()


def check() -> int:
    con = loop_connection()
    try:
        tables = [t[0] for t in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()]
        if "release_events_daily" not in tables or "release_events_signals" not in tables:
            print("FAIL: release_events tables missing from asado_loop.duckdb")
            return 1
        n_ev = con.execute("SELECT COUNT(*) FROM release_events_daily").fetchone()[0]
        n_sig = con.execute("SELECT COUNT(*) FROM release_events_signals").fetchone()[0]
        print(f"release_events_daily: {n_ev:,} rows")
        print(f"release_events_signals: {n_sig:,} rows")
        if n_ev == 0 or n_sig == 0:
            print("FAIL: empty tables")
            return 1
        print("OK: release_events tables healthy")
        return 0
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify tables without rebuild")
    args = parser.parse_args()

    if args.check:
        return check()
    rebuild()
    return 0


if __name__ == "__main__":
    sys.exit(main())
