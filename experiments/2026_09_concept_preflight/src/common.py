"""
=============================================================================
SCRIPT NAME: common.py
=============================================================================
Shared data loaders for the concept-layer pre-flight checks (Check A spectral,
Check B G2-by-relation). Reads only the frozen experiment snapshot; never opens
a DuckDB database.

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/concept_preflight/snapshot_2026_09_23/t2_factors_daily.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/concept_preflight/snapshot_2026_09_23/t2_master.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/concept_preflight/snapshot_2026_09_23/graph_edge_vintages.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/ff_region_map.json

OUTPUT FILES:
- none (library module)

VERSION: 1.0
LAST UPDATED: 2026-09-23
AUTHOR: Claude (Opus 5.5) for Arjun Divecha

DESCRIPTION:
- daily_returns(): backward-labelled trading-day returns, same definition as
  scripts/loop/loopdb.daily_country_returns (1DRet shifted one calendar row per
  country, exact zeros dropped).
- monthly_returns(): calendar-month compounded returns (>=10 non-zero trading
  days required, per PREREG amendment A1), the first-trading-day return of each
  month, and the last complete month.
- regions(): sovereign-token region map per PREREG amendment A1.

DEPENDENCIES: pandas, numpy, pyarrow (ASADO venv)
USAGE: imported by check_a_spectral.py and check_b_g2.py
NOTES: forward-return variables are used only as a date-alignment check and
never as predictors.
=============================================================================
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ASADO = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
SNAP = ASADO / "Data/work/experiments/concept_preflight/snapshot_2026_09_23"
EXP = ASADO / "experiments/2026_09_concept_preflight"
RESULTS = EXP / "results"

T2_UNIVERSE = [
    "Australia", "Brazil", "Canada", "Chile", "ChinaA", "ChinaH", "Denmark", "France",
    "Germany", "Hong Kong", "India", "Indonesia", "Italy", "Japan", "Korea", "Malaysia",
    "Mexico", "NASDAQ", "Netherlands", "Philippines", "Poland", "Saudi Arabia", "Singapore",
    "South Africa", "Spain", "Sweden", "Switzerland", "Taiwan", "Thailand", "Turkey", "U.K.",
    "U.S.", "US SmallCap", "Vietnam",
]
SLEEVES = {"NASDAQ", "US SmallCap", "ChinaH"}
SOVEREIGNS = [c for c in T2_UNIVERSE if c not in SLEEVES]
MIN_DAYS = 10


def daily_returns() -> pd.DataFrame:
    """(dates x 34 countries) backward-labelled trading-day returns."""
    raw = pd.read_parquet(SNAP / "t2_factors_daily.parquet",
                          columns=["date", "country", "value", "variable"],
                          filters=[("variable", "==", "1DRet")])
    raw = raw[raw["country"].isin(T2_UNIVERSE)].copy()
    raw["date"] = pd.to_datetime(raw["date"])
    raw = raw.sort_values(["country", "date"])
    raw["ret"] = raw.groupby("country")["value"].shift(1)
    raw = raw[raw["ret"].notna() & (raw["ret"] != 0.0)]
    return raw.pivot_table(index="date", columns="country", values="ret").reindex(columns=T2_UNIVERSE)


def monthly_returns(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.Period]:
    """Returns (monthly compounded returns, first-trading-day returns, last complete month).
    Index: pandas monthly Period."""
    per = daily.index.to_period("M")
    logr = np.log1p(daily)
    mret = np.expm1(logr.groupby(per).sum(min_count=1))
    ndays = daily.notna().groupby(per).sum()
    mret = mret.where(ndays >= MIN_DAYS)
    first = daily.groupby(per).apply(lambda g: g.apply(lambda s: s.dropna().iloc[0] if s.notna().any() else np.nan))
    first = first.where(ndays >= MIN_DAYS)
    last_date = daily.index.max()
    last_month = last_date.to_period("M")
    if last_date < last_month.end_time.normalize():
        last_month = last_month - 1
    mret = mret.loc[:last_month]
    first = first.loc[:last_month]
    return mret, first, last_month


def regions() -> dict[str, str]:
    """Sovereign token -> region, per PREREG amendment A1."""
    m = json.loads((ASADO / "config/ff_region_map.json").read_text())["country_to_region"]
    out = {}
    for c in SOVEREIGNS:
        r = m[c]["region"] if isinstance(m[c], dict) else m[c]
        if r in ("US", "North_America"):
            r = "North_America"
        if r == "Japan":
            r = "Asia_Pacific_ex_Japan"
        out[c] = r
    return out
