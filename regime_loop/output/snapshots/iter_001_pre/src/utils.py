"""
=============================================================================
SCRIPT NAME: utils.py
=============================================================================
Shared paths, logging, and helpers for the regime conditioning test.
=============================================================================
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd

REGIME_ROOT = Path(__file__).resolve().parent.parent
ASADO_ROOT = REGIME_ROOT.parent
DATA_DIR = REGIME_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
RESULTS_DIR = REGIME_ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
DUCKDB_PATH = ASADO_ROOT / "Data" / "asado.duckdb"
T2_CSV = Path(
    "/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/Normalized_T2_MasterCSV.csv"
)
ENV_FILE = Path("/Users/arjundivecha/Dropbox/AAA Backup/.env.txt")

IN_SAMPLE_END = pd.Timestamp("2018-12-01")
OOS_START = pd.Timestamp("2019-01-01")
FULL_START = pd.Timestamp("1995-01-01")

T2_COUNTRIES = [
    "Australia", "Brazil", "Canada", "Chile", "ChinaA", "ChinaH", "Denmark",
    "France", "Germany", "Hong Kong", "India", "Indonesia", "Italy", "Japan",
    "Korea", "Malaysia", "Mexico", "NASDAQ", "Netherlands", "Philippines",
    "Poland", "Saudi Arabia", "Singapore", "South Africa", "Spain", "Sweden",
    "Switzerland", "Taiwan", "Thailand", "Turkey", "U.K.", "U.S.",
    "US SmallCap", "Vietnam",
]

REGIME_LABELS = [
    "Crisis",
    "Late-cycle",
    "Recession",
    "Recovery",
    "Expansion",
    "Stagflation",
    "Transition",
]


def setup_logging(name: str = "regime_test") -> logging.Logger:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = RESULTS_DIR / "regime_test.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path, mode="a"),
        ],
        force=True,
    )
    return logging.getLogger(name)


def load_api_key(key_name: str) -> str | None:
    val = os.environ.get(key_name)
    if val:
        return val
    if ENV_FILE.exists():
        for line in ENV_FILE.open():
            line = line.strip()
            if line.startswith(f"{key_name}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    repo_env = ASADO_ROOT / ".env"
    if repo_env.exists():
        for line in repo_env.open():
            line = line.strip()
            if line.startswith(f"{key_name}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def month_start(s: pd.Series | pd.DatetimeIndex) -> pd.DatetimeIndex:
    return pd.to_datetime(s).dt.to_period("M").dt.to_timestamp()


def annualized_sharpe(returns: pd.Series, periods_per_year: int = 12) -> float:
    r = returns.dropna()
    if len(r) < 2 or r.std() == 0:
        return np.nan
    return float(r.mean() / r.std() * np.sqrt(periods_per_year))


def sortino_ratio(returns: pd.Series, periods_per_year: int = 12) -> float:
    r = returns.dropna()
    downside = r[r < 0]
    if len(r) < 2 or len(downside) == 0 or downside.std() == 0:
        return np.nan
    return float(r.mean() / downside.std() * np.sqrt(periods_per_year))


def max_drawdown(cum: pd.Series) -> float:
    wealth = (1 + cum).cumprod()
    peak = wealth.cummax()
    dd = wealth / peak - 1
    return float(dd.min())


def ensure_dirs() -> None:
    for d in (RAW_DIR, PROCESSED_DIR, RESULTS_DIR, FIGURES_DIR):
        d.mkdir(parents=True, exist_ok=True)
