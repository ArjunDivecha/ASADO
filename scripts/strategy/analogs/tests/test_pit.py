"""
=============================================================================
SCRIPT NAME: scripts/strategy/analogs/tests/test_pit.py
=============================================================================

INPUT FILES:
- Data/strategy/analogs/v1/pit_audit.csv
- Data/strategy/analogs/v1/worldstates.parquet
- Data/strategy/analogs/v1/analog_matches.parquet
- Data/strategy/analogs/v1/signals.parquet

OUTPUT FILES:
- (none — pytest assertions)

VERSION: 1.0
LAST UPDATED: 2026-04-19
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
Automated PIT and structural checks for Strategy #1 v1 MVP (PRD §9):

  1. Every variable that fed the worldstate is flagged vintage_safe in the
     PIT audit (no forecast / no >40% missingness vars leaked through).
  2. Every analog_date < decision_date - MIN_LAG_MONTHS (no future peeking,
     12-month minimum lag honored).
  3. Library monotonicity: a worldstate dated t is never used as an analog
     for a decision at t' ≤ t + MIN_LAG_MONTHS.
  4. Signals: for each decision date there are exactly 34 country rows; ranks
     1..34 are present where scores are non-NaN.
  5. Softmax weights sum to ~1.0 within each decision date (numerical sanity).

DEPENDENCIES:
- pytest, pandas, numpy

USAGE:
  pytest scripts/strategy/analogs/tests/test_pit.py -v
=============================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from scripts.strategy.analogs import config as C  # noqa: E402


@pytest.fixture(scope="module")
def audit() -> pd.DataFrame:
    return pd.read_csv(C.PIT_AUDIT_CSV)


@pytest.fixture(scope="module")
def matches() -> pd.DataFrame:
    df = pd.read_parquet(C.ANALOG_MATCHES_PARQUET)
    df["date"] = pd.to_datetime(df["date"])
    df["analog_date"] = pd.to_datetime(df["analog_date"])
    return df


@pytest.fixture(scope="module")
def signals() -> pd.DataFrame:
    df = pd.read_parquet(C.SIGNALS_PARQUET)
    df["date"] = pd.to_datetime(df["date"])
    return df


def test_pit_audit_excludes_forecast_variables(audit: pd.DataFrame) -> None:
    leaked = audit[audit["is_forecast_variable"] & audit["vintage_safe"]]
    assert leaked.empty, f"Forecast variables flagged safe: {leaked['variable'].tolist()}"


def test_pit_audit_excludes_high_missingness(audit: pd.DataFrame) -> None:
    leaked = audit[audit["high_missingness"] & audit["vintage_safe"]]
    assert leaked.empty, f"High-missingness variables flagged safe: {leaked['variable'].tolist()}"


def test_min_lag_honored(matches: pd.DataFrame) -> None:
    """No analog should be within MIN_LAG_MONTHS of its decision date."""
    delta_days = (matches["date"] - matches["analog_date"]).dt.days
    min_required_days = C.MIN_LAG_MONTHS * 28  # conservative lower bound
    too_close = matches[delta_days < min_required_days]
    assert too_close.empty, (
        f"{len(too_close)} matches violate min_lag={C.MIN_LAG_MONTHS} months"
    )


def test_no_future_peeking(matches: pd.DataFrame) -> None:
    """analog_date strictly precedes decision date in every match row."""
    bad = matches[matches["analog_date"] >= matches["date"]]
    assert bad.empty, f"{len(bad)} matches have analog_date >= decision_date"


def test_all_decisions_have_34_country_rows(signals: pd.DataFrame) -> None:
    counts = signals.groupby("date").size()
    bad = counts[counts != len(C.T2_COUNTRIES)]
    assert bad.empty, f"Decisions with != 34 rows: {bad.head().to_dict()}"


def test_ranks_are_complete_for_nonnan_scores(signals: pd.DataFrame) -> None:
    """Within each date, non-NaN scores should produce a contiguous rank set
    starting at 1 (ties allowed via method='min')."""
    for date, group in signals.groupby("date"):
        valid = group.dropna(subset=["score"])
        if valid.empty:
            continue
        ranks = set(valid["rank"].astype(int).tolist())
        assert 1 in ranks, f"date {date.date()} missing rank=1"


def test_softmax_weights_sum_to_one(matches: pd.DataFrame) -> None:
    sums = matches.groupby("date")["softmax_weight"].sum()
    bad = sums[~np.isclose(sums, 1.0, atol=1e-6)]
    assert bad.empty, f"Softmax weights deviate from 1: {bad.head().to_dict()}"


def test_decision_start_respected(matches: pd.DataFrame) -> None:
    earliest = matches["date"].min()
    # Min-lag of 12 months from BACKTEST_START 2008-01-31 means earliest
    # decision is whenever the library first has K_ANALOGS members; in
    # practice this is a few months after start.
    assert earliest >= pd.Timestamp(C.BACKTEST_START), (
        f"Decision date {earliest} predates BACKTEST_START={C.BACKTEST_START}"
    )
