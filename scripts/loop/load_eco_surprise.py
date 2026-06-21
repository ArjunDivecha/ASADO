#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/load_eco_surprise.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/eco_surprise_monthly.parquet
    Tidy monthly panel written by scripts/loop/collect_eco_surprise_bbg.py:
    ECO_{CPI,UNEMP,GDP,PMI}_ACTUAL + ECO_{...}_SURPRISE per T2 country
    (CPI 33, UNEMP 24, GDP 19, PMI 22 mapped names; 2000+, surveys ~2015+).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `eco_surprise_monthly` — idempotent rebuild from the parquet.
    Table `eco_surprise_signals` — derived monthly signal surface:
      ECO_<IND>_SURPRISE_Z     surprise scaled by the trailing 60-month
                               std of that country's own surprises (min 12
                               obs) — the Citi-surprise-style normalization
                               that makes a 0.3pt Swiss CPI miss comparable
                               to a 3pt Turkish one
      ECO_GROWTH_SURPRISE_Z    mean of available (GDP_Z, PMI_Z, -UNEMP_Z):
                               positive = growth data beating consensus
      ECO_INFL_SURPRISE_Z      = CPI_Z: positive = inflation printing HOT
                               (above consensus)
    Lives in the LOOP DB because setup_duckdb.py deletes the main warehouse
    monthly.

VERSION: 1.0
LAST UPDATED: 2026-06-12
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop)

DESCRIPTION:
Loads the economic surprise parquet into the loop DuckDB and derives
normalized per-country surprise signals. Same collector/loader split as
the other loop layers (blpapi env has no duckdb and vice versa).

DEPENDENCIES:
- duckdb, pandas, numpy (project venv)

USAGE:
  python scripts/loop/load_eco_surprise.py            # rebuild tables
  python scripts/loop/load_eco_surprise.py --check    # verify only

NOTES:
- Fails loudly if the parquet is missing or empty (FAIL-IS-FAIL).
- Z rows need >= 12 trailing surprise observations; otherwise omitted
  (never silently zero-filled).
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
PANEL_PATH = BASE_DIR / "Data" / "work" / "loop" / "eco_surprise_monthly.parquet"

INDICATORS = ["CPI", "UNEMP", "GDP", "PMI"]
Z_WINDOW = 60   # months
Z_MIN_OBS = 12


def surprise_z(s: pd.Series) -> pd.Series:
    """Surprise scaled by the trailing std of own surprises (shifted so the
    current print does not inflate its own baseline). No mean subtraction —
    surveyed surprises are mean-zero by construction."""
    sd = s.shift(1).rolling(Z_WINDOW, min_periods=Z_MIN_OBS).std()
    z = s / sd
    return z.replace([np.inf, -np.inf], np.nan)


def build_signals(panel: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []

    def emit(s: pd.Series, country: str, variable: str) -> None:
        s = s.dropna()
        if s.empty:
            return
        frames.append(pd.DataFrame(
            {"date": s.index, "country": country, "value": s.values, "variable": variable}))

    z_store: dict[tuple[str, str], pd.Series] = {}   # (country, IND) -> z series
    for ind in INDICATORS:
        sub = panel[panel["variable"] == f"ECO_{ind}_SURPRISE"]
        for country, g in sub.groupby("country"):
            s = g.set_index("date")["value"].sort_index()
            z = surprise_z(s)
            z_store[(country, ind)] = z
            emit(z, country, f"ECO_{ind}_SURPRISE_Z")

    countries = sorted({c for c, _ in z_store})
    for country in countries:
        legs = []
        if (country, "GDP") in z_store:
            legs.append(z_store[(country, "GDP")])
        if (country, "PMI") in z_store:
            legs.append(z_store[(country, "PMI")])
        if (country, "UNEMP") in z_store:
            legs.append(-z_store[(country, "UNEMP")])
        if legs:
            growth = pd.concat(legs, axis=1, sort=True).mean(axis=1, skipna=True)
            emit(growth, country, "ECO_GROWTH_SURPRISE_Z")
        if (country, "CPI") in z_store:
            emit(z_store[(country, "CPI")], country, "ECO_INFL_SURPRISE_Z")

    if not frames:
        raise RuntimeError("surprise signal derivation produced nothing — refusing to write")
    out = pd.concat(frames, ignore_index=True)
    out["source"] = "derived"
    return out[["date", "country", "value", "variable", "source"]]


def rebuild() -> None:
    if not PANEL_PATH.exists():
        raise FileNotFoundError(f"missing {PANEL_PATH} — run collect_eco_surprise_bbg.py first")
    panel = pd.read_parquet(PANEL_PATH)
    if panel.empty:
        raise RuntimeError(f"{PANEL_PATH} is empty — refusing to continue")
    panel["date"] = pd.to_datetime(panel["date"])
    signals = build_signals(panel)

    con = loop_connection()
    try:
        con.execute("DROP TABLE IF EXISTS eco_surprise_monthly")
        con.execute(f"""
            CREATE TABLE eco_surprise_monthly AS
            SELECT CAST(date AS DATE) AS date, country, value, variable, source
            FROM read_parquet('{PANEL_PATH}')
        """)
        con.execute("DROP TABLE IF EXISTS eco_surprise_signals")
        con.register("signals_df", signals)
        con.execute("""
            CREATE TABLE eco_surprise_signals AS
            SELECT CAST(date AS DATE) AS date, country, value, variable, source
            FROM signals_df
        """)
        for table in ("eco_surprise_monthly", "eco_surprise_signals"):
            n, lo, hi = con.execute(f"SELECT COUNT(*), MIN(date), MAX(date) FROM {table}").fetchone()
            if not n:
                raise RuntimeError(f"{table} rebuilt empty — refusing to continue")
            print(f"{table}: {n:,} rows, {lo} -> {hi}")
        for var, nc, last in con.execute("""
            SELECT variable, COUNT(DISTINCT country), MAX(date)
            FROM eco_surprise_signals GROUP BY 1 ORDER BY 1
        """).fetchall():
            print(f"  {var}: {nc} countries, last {last}")
    finally:
        con.close()


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        rows = con.execute("""
            SELECT variable, COUNT(DISTINCT country) AS nc, MAX(date) AS last
            FROM eco_surprise_signals GROUP BY 1 ORDER BY 1
        """).fetchall()
    finally:
        con.close()
    ok = bool(rows)
    for var, nc, last in rows:
        print(f"{var}: {nc} countries, last {last}")
        if var == "ECO_INFL_SURPRISE_Z" and nc < 28:
            ok = False
    print("CHECK", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Load economic surprise parquet into loop DuckDB + derive signals.")
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
