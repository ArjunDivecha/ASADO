#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/load_sovereign_daily.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/sovereign_daily.parquet
    Tidy daily panel written by scripts/loop/collect_sovereign_daily_bbg.py:
    SOV_CDS_5Y_BP (20 countries, 2005+), SOV_CDS_1Y_BP (18, v1.1),
    SOV_10Y_YIELD_PCT (32 countries), SOV_2Y_YIELD_PCT (27, v1.1).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `sovereign_daily` (idempotent rebuild from the parquet).
    Table `sovereign_signals` (v1.1) — derived daily curve signals:
      SOV_CDS_SLOPE_BP    5Y CDS - 1Y CDS, bp. Normally POSITIVE (upward
                          credit curve). NEGATIVE = inverted = the market
                          prices near-term default risk above long-term —
                          the classic imminent-distress signature
                          (Greece '11, Turkey '18, Russia '22).
      SOV_CDS_SLOPE_Z252  z of the slope vs own trailing 252d
      SOV_2S10S_PCT       10Y yield - 2Y yield, pct pts. NEGATIVE = inverted
                          government curve (recession/regime signal).
      SOV_2S10S_Z252      z of 2s10s vs own trailing 252d
    Lives in the LOOP DB because setup_duckdb.py deletes the main warehouse
    monthly.

VERSION: 1.1
LAST UPDATED: 2026-06-12
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 3)

DESCRIPTION:
Loads the Bloomberg sovereign CDS/yield parquet into the loop DuckDB and
derives per-country curve-shape signals. Split from the collector because
the OpusBloomberg conda env (where blpapi lives) has no duckdb, and the
project venv has no blpapi. Same split as collect_foreign_flows_bbg.py /
collect_foreign_flows.py.

Z-scores need >= 60 trailing observations and a positive std; otherwise the
signal row is omitted (never silently zero-filled).

DEPENDENCIES:
- duckdb, pandas, numpy (project venv)

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

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.loop.loopdb import loop_connection  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PANEL_PATH = BASE_DIR / "Data" / "work" / "loop" / "sovereign_daily.parquet"

Z_WINDOW = 252
Z_MIN_OBS = 60


def rolling_z(s: pd.Series) -> pd.Series:
    """z of each point vs its own TRAILING window (point excluded via shift
    so today's spike doesn't inflate its own baseline)."""
    base = s.shift(1)
    mu = base.rolling(Z_WINDOW, min_periods=Z_MIN_OBS).mean()
    sd = base.rolling(Z_WINDOW, min_periods=Z_MIN_OBS).std()
    z = (s - mu) / sd
    return z.replace([np.inf, -np.inf], np.nan)


def build_signals(panel: pd.DataFrame) -> pd.DataFrame:
    """Per-country curve-shape signals: CDS slope (5Y-1Y) and 2s10s."""
    frames: list[pd.DataFrame] = []

    def emit(s: pd.Series, country: str, variable: str) -> None:
        s = s.dropna()
        if s.empty:
            return
        frames.append(pd.DataFrame(
            {"date": s.index, "country": country, "value": s.values, "variable": variable}))

    pairs = [
        ("SOV_CDS_5Y_BP", "SOV_CDS_1Y_BP", "SOV_CDS_SLOPE_BP", "SOV_CDS_SLOPE_Z252"),
        ("SOV_10Y_YIELD_PCT", "SOV_2Y_YIELD_PCT", "SOV_2S10S_PCT", "SOV_2S10S_Z252"),
    ]
    for long_var, short_var, slope_var, z_var in pairs:
        sub = panel[panel["variable"].isin([long_var, short_var])]
        for country, g in sub.groupby("country"):
            piv = g.pivot_table(index="date", columns="variable", values="value").sort_index()
            if {long_var, short_var} <= set(piv.columns):
                both = piv[[long_var, short_var]].dropna()
                slope = both[long_var] - both[short_var]
                emit(slope, country, slope_var)
                emit(rolling_z(slope), country, z_var)

    if not frames:
        raise RuntimeError("sovereign signal derivation produced nothing — refusing to write")
    out = pd.concat(frames, ignore_index=True)
    out["source"] = "derived"
    return out[["date", "country", "value", "variable", "source"]]


def rebuild() -> None:
    if not PANEL_PATH.exists():
        raise FileNotFoundError(f"missing {PANEL_PATH} — run collect_sovereign_daily_bbg.py first")
    panel = pd.read_parquet(PANEL_PATH)
    if panel.empty:
        raise RuntimeError(f"{PANEL_PATH} is empty — refusing to continue")
    panel["date"] = pd.to_datetime(panel["date"])
    signals = build_signals(panel)

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
        con.execute("DROP TABLE IF EXISTS sovereign_signals")
        con.register("signals_df", signals)
        con.execute("""
            CREATE TABLE sovereign_signals AS
            SELECT CAST(date AS DATE) AS date, country, value, variable, source
            FROM signals_df
        """)
        for table in ("sovereign_daily", "sovereign_signals"):
            n, lo, hi = con.execute(
                f"SELECT COUNT(*), MIN(date), MAX(date) FROM {table}").fetchone()
            if not n:
                raise RuntimeError(f"{table} rebuilt empty — refusing to continue")
            print(f"{table}: {n:,} rows, {lo} -> {hi}")
            for var, nc, last in con.execute(
                f"SELECT variable, COUNT(DISTINCT country), MAX(date) FROM {table} GROUP BY 1 ORDER BY 1"
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
        n_sig = con.execute("SELECT COUNT(*) FROM sovereign_signals").fetchone()[0]
    finally:
        con.close()
    ok = True
    for var, nc, last in rows:
        print(f"{var}: {nc} countries, last {last}")
        if var == "SOV_CDS_5Y_BP" and nc < 18:
            ok = False
        if var == "SOV_10Y_YIELD_PCT" and nc < 28:
            ok = False
    if not rows or n_sig == 0:
        ok = False
    print(f"sovereign_signals: {n_sig:,} rows")
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
