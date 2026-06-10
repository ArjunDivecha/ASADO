#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: loopdb.py (shared module, not run directly)
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
  Main ASADO warehouse, always attached READ-ONLY as schema alias `asado`.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/country_mapping.json
  Canonical 34-country T2 universe.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
  The Alpha-Hunting Loop's own DuckDB. Created on first use. Holds every
  loop surface (country_returns_monthly, ledgers, graph features,
  dislocations, harness results).

VERSION: 1.0
LAST UPDATED: 2026-06-10
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop)

DESCRIPTION:
Shared database plumbing for every Alpha-Hunting Loop component. The single
most important design fact: scripts/setup_duckdb.py DELETES asado.duckdb on
every monthly rebuild, so nothing the loop owns may live there. All loop
state lives in Data/loop/asado_loop.duckdb; the main warehouse is attached
read-only under the alias `asado` so queries can join both worlds:

    con = loop_connection()
    con.execute("SELECT * FROM asado.feature_panel LIMIT 5")   # warehouse
    con.execute("SELECT * FROM country_returns_monthly")       # loop-owned

DEPENDENCIES:
- duckdb (project venv)

USAGE:
 from scripts.loop.loopdb import loop_connection, t2_countries, LOOP_DIR
=============================================================================
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MAIN_DB = BASE_DIR / "Data" / "asado.duckdb"
LOOP_DIR = BASE_DIR / "Data" / "loop"
LOOP_DB = LOOP_DIR / "asado_loop.duckdb"
LEDGER_DIR = BASE_DIR / "ledgers"
BRIEF_DIR = BASE_DIR / "Data" / "dislocations"
COUNTRY_MAPPING = BASE_DIR / "config" / "country_mapping.json"


def loop_connection(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open the loop DB with the main warehouse attached read-only as `asado`.

    FAIL-IS-FAIL: if the main warehouse is missing we raise instead of
    returning a half-usable connection.
    """
    LOOP_DIR.mkdir(parents=True, exist_ok=True)
    if not MAIN_DB.exists():
        raise FileNotFoundError(f"Main ASADO warehouse not found: {MAIN_DB}")
    con = duckdb.connect(str(LOOP_DB), read_only=read_only)
    con.execute(f"ATTACH '{MAIN_DB}' AS asado (READ_ONLY)")
    return con


# The canonical 34-country T2 universe (CLAUDE.md). Hardcoded deliberately:
# this IS the universe definition. config/country_mapping.json holds 43 names
# (9 non-T2 extras leak in from multi-country sources) and country_reference
# holds 40, so neither is authoritative for membership.
T2_UNIVERSE = [
    "Australia", "Brazil", "Canada", "Chile", "ChinaA", "ChinaH", "Denmark",
    "France", "Germany", "Hong Kong", "India", "Indonesia", "Italy", "Japan",
    "Korea", "Malaysia", "Mexico", "NASDAQ", "Netherlands", "Philippines",
    "Poland", "Saudi Arabia", "Singapore", "South Africa", "Spain", "Sweden",
    "Switzerland", "Taiwan", "Thailand", "Turkey", "U.K.", "U.S.",
    "US SmallCap", "Vietnam",
]


def t2_countries() -> list[str]:
    """The canonical 34 T2 country names."""
    return list(T2_UNIVERSE)


def daily_country_returns(con) -> "pd.DataFrame":
    """Tidy (date, country, ret) of REAL trading-day returns, BACKWARD-labeled.

    Why this exists (v1.1, 2026-06-10): `t2_factors_daily.1DRet` is a FORWARD
    return on a CALENDAR-day grid - the value at date t is the move from t's
    close to the next calendar day's close, and weekends/holidays carry 0.0
    placeholder rows. Naive rolling windows over that grid span the wrong
    economic days (the D9 v1 window-misalignment bug) and are label-shifted
    one day into the future. This helper:

      1. shifts each country's series one calendar row so the return lands
         on the date whose CLOSE it describes (backward convention), and
      2. drops exact-0.0 rows (non-trading placeholders). A genuinely flat
         trading day (TRI unchanged to 6dp) is dropped too - rare on a total
         return index and an accepted, documented cost.

    Every loop consumer (graph features, dislocations, daily harness) uses
    this one definition so windows and labels agree everywhere.
    """
    import pandas as pd

    raw = con.execute(
        """
        SELECT date, country, value FROM asado.t2_factors_daily
        WHERE variable = '1DRet' AND value IS NOT NULL
        ORDER BY country, date
        """
    ).fetchdf()
    raw = raw[raw["country"].isin(T2_UNIVERSE)]
    raw["date"] = pd.to_datetime(raw["date"])
    # forward -> backward label: the calendar grid is contiguous per country,
    # so shifting by one row moves each return onto its close date.
    raw["ret"] = raw.groupby("country")["value"].shift(1)
    out = raw[(raw["ret"].notna()) & (raw["ret"] != 0.0)][["date", "country", "ret"]]
    return out.reset_index(drop=True)


def returns_panel(con, min_countries: int = 10) -> "pd.DataFrame":
    """(dates x countries) panel of backward-labeled trading-day returns.

    The index is the union of per-country trading dates, restricted to dates
    where at least `min_countries` countries actually traded (drops weekends
    and Saudi-only Sundays so cross-sections aren't stale ghost copies).
    """
    tidy = daily_country_returns(con)
    piv = tidy.pivot_table(index="date", columns="country", values="ret")
    piv = piv[piv.notna().sum(axis=1) >= min_countries]
    return piv.reindex(columns=T2_UNIVERSE)
