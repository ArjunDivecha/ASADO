#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/load_market_implied.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/market_implied_daily.parquet
    Tidy daily panel written by scripts/loop/collect_market_implied_bbg.py:
    FX_IMPVOL_1M/1W/3M_PCT + FX_RR25_1M_PCT + FX_BF25_1M_PCT (29 countries,
    2006+), RISK_* global dashboard (VIX/VIX3M/MOVE/HY OAS/IG OAS/DXY/BBDXY),
    CMD_* generic 1st/2nd commodity contracts (CL/CO/HG/GC/NG).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `market_implied_daily`  — idempotent rebuild from the parquet.
    Table `market_implied_signals` — derived daily signal surface:
      FX_IMPVOL_Z252 / FX_RR25_Z252   per-country z vs own trailing 252d
      FX_BF25_Z252                    z of 25D butterfly (tail premium) (v1.1)
      FX_CARRY_Z252                   z of 3M forward-implied carry (v1.2) —
                                      a carry SPIKE without a rate hike is
                                      devaluation expectation in the forwards
      FX_VOL_TERM_PCT                 1W vol - 3M vol, vol points (v1.1);
                                      > 0 = inverted term structure = the
                                      market prices stress NOW, not later
      FX_VOL_TERM_Z252                z of the term slope vs trailing 252d
      RISK_VIX_TERM_RATIO             VIX3M / VIX (< 1 = inverted = acute stress)
      RISK_*_Z252                     z of each dashboard series vs trailing 252d
      CMD_<ROOT>_CURVE_PCT            (front/second - 1) * 100; > 0 = backwardation
      CMD_<ROOT>_CURVE_Z252           z of curve shape vs trailing 252d
    Lives in the LOOP DB because setup_duckdb.py deletes the main warehouse
    monthly.

VERSION: 1.1
LAST UPDATED: 2026-06-12
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop)

DESCRIPTION:
Loads the Bloomberg market-implied stress parquet into the loop DuckDB and
derives the signal surface the brief and detectors read. Split from the
collector because the OpusBloomberg conda env (where blpapi lives) has no
duckdb, and the project venv has no blpapi — same split as
collect_sovereign_daily_bbg.py / load_sovereign_daily.py.

Z-scores need >= 60 trailing observations and a positive std; otherwise the
signal row is omitted (never silently zero-filled).

DEPENDENCIES:
- duckdb, pandas, numpy (project venv)

USAGE:
  python scripts/loop/load_market_implied.py            # rebuild tables
  python scripts/loop/load_market_implied.py --check    # verify only

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
PANEL_PATH = BASE_DIR / "Data" / "work" / "loop" / "market_implied_daily.parquet"

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
    frames: list[pd.DataFrame] = []

    def emit(s: pd.Series, country: str, variable: str) -> None:
        s = s.dropna()
        if s.empty:
            return
        frames.append(pd.DataFrame(
            {"date": s.index, "country": country, "value": s.values, "variable": variable}))

    # ---- FX per-country z-scores -------------------------------------------
    for raw_var, z_var in [("FX_IMPVOL_1M_PCT", "FX_IMPVOL_Z252"),
                           ("FX_RR25_1M_PCT", "FX_RR25_Z252"),
                           ("FX_BF25_1M_PCT", "FX_BF25_Z252"),
                           ("FX_CARRY_3M_PCT", "FX_CARRY_Z252")]:
        sub = panel[panel["variable"] == raw_var]
        for country, g in sub.groupby("country"):
            s = g.set_index("date")["value"].sort_index()
            emit(rolling_z(s), country, z_var)

    # ---- FX vol term slope (1W - 3M, vol points) -----------------------------
    # Normally negative (term premium); a POSITIVE slope means the options
    # market prices more vol in the next week than over the next quarter —
    # the classic signature of an imminent event (election, peg break, crisis).
    fx_tenors = panel[panel["variable"].isin(["FX_IMPVOL_1W_PCT", "FX_IMPVOL_3M_PCT"])]
    for country, g in fx_tenors.groupby("country"):
        piv = g.pivot_table(index="date", columns="variable", values="value").sort_index()
        if {"FX_IMPVOL_1W_PCT", "FX_IMPVOL_3M_PCT"} <= set(piv.columns):
            both = piv[["FX_IMPVOL_1W_PCT", "FX_IMPVOL_3M_PCT"]].dropna()
            slope = both["FX_IMPVOL_1W_PCT"] - both["FX_IMPVOL_3M_PCT"]
            emit(slope, country, "FX_VOL_TERM_PCT")
            emit(rolling_z(slope), country, "FX_VOL_TERM_Z252")

    # ---- Global risk dashboard ---------------------------------------------
    glob = panel[panel["country"] == "GLOBAL"]
    gpiv = glob.pivot_table(index="date", columns="variable", values="value").sort_index()

    if {"RISK_VIX", "RISK_VIX3M"} <= set(gpiv.columns):
        emit(gpiv["RISK_VIX3M"] / gpiv["RISK_VIX"], "GLOBAL", "RISK_VIX_TERM_RATIO")

    for col in [c for c in gpiv.columns if c.startswith("RISK_")]:
        emit(rolling_z(gpiv[col].dropna()), "GLOBAL", f"{col}_Z252")

    # ---- Commodity curve shape ---------------------------------------------
    for root in ["CL", "CO", "HG", "GC", "NG"]:
        f1, f2 = f"CMD_{root}1", f"CMD_{root}2"
        if f1 in gpiv.columns and f2 in gpiv.columns:
            both = gpiv[[f1, f2]].dropna()
            # guard: curve % is meaningless across a zero/negative front print
            both = both[(both[f1] > 0) & (both[f2] > 0)]
            curve = (both[f1] / both[f2] - 1.0) * 100.0
            emit(curve, "GLOBAL", f"CMD_{root}_CURVE_PCT")
            emit(rolling_z(curve), "GLOBAL", f"CMD_{root}_CURVE_Z252")

    if not frames:
        raise RuntimeError("signal derivation produced nothing — refusing to write")
    out = pd.concat(frames, ignore_index=True)
    out["source"] = "derived"
    return out[["date", "country", "value", "variable", "source"]]


def rebuild() -> None:
    if not PANEL_PATH.exists():
        raise FileNotFoundError(f"missing {PANEL_PATH} — run collect_market_implied_bbg.py first")
    panel = pd.read_parquet(PANEL_PATH)
    if panel.empty:
        raise RuntimeError(f"{PANEL_PATH} is empty — refusing to continue")
    panel["date"] = pd.to_datetime(panel["date"])

    signals = build_signals(panel)

    con = loop_connection()
    try:
        con.execute("DROP TABLE IF EXISTS market_implied_daily")
        con.execute(f"""
            CREATE TABLE market_implied_daily AS
            SELECT CAST(date AS DATE) AS date, country, value, variable, source
            FROM read_parquet('{PANEL_PATH}')
        """)
        con.execute("DROP TABLE IF EXISTS market_implied_signals")
        con.register("signals_df", signals)
        con.execute("""
            CREATE TABLE market_implied_signals AS
            SELECT CAST(date AS DATE) AS date, country, value, variable, source
            FROM signals_df
        """)
        for table in ("market_implied_daily", "market_implied_signals"):
            n, lo, hi = con.execute(f"SELECT COUNT(*), MIN(date), MAX(date) FROM {table}").fetchone()
            if not n:
                raise RuntimeError(f"{table} rebuilt empty — refusing to continue")
            print(f"{table}: {n:,} rows, {lo} -> {hi}")
        for var, nc, last in con.execute("""
            SELECT variable, COUNT(DISTINCT country), MAX(date)
            FROM market_implied_signals GROUP BY 1 ORDER BY 1
        """).fetchall():
            print(f"  {var}: {nc} entities, last {last}")
    finally:
        con.close()


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        rows = con.execute("""
            SELECT variable, COUNT(DISTINCT country) AS nc, MAX(date) AS last
            FROM market_implied_daily GROUP BY 1 ORDER BY 1
        """).fetchall()
        n_sig = con.execute("SELECT COUNT(*) FROM market_implied_signals").fetchone()[0]
    finally:
        con.close()
    ok = bool(rows) and n_sig > 0
    for var, nc, last in rows:
        print(f"{var}: {nc} countries, last {last}")
        if var in ("FX_IMPVOL_1M_PCT", "FX_RR25_1M_PCT") and nc < 25:
            ok = False
    print(f"market_implied_signals: {n_sig:,} rows")
    print("CHECK", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Load market-implied parquet into loop DuckDB + derive signals.")
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
