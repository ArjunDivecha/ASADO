#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: tests/loop/test_pit_lag.py
=============================================================================

INPUT FILES: none (fixtures built in-test; pit_proof registry passed as a dict).
OUTPUT FILES: none.

VERSION: 1.0
LAST UPDATED: 2026-06-17
AUTHOR: Arjun Divecha (built by agent session, Governance Layer PRD v1.2, item A6)

DESCRIPTION:
A6 acceptance: the daily publication lag is per-variable and FAILS CLOSED.
  - source in ZERO_LAG_SOURCES -> 0
  - unproven daily variable -> CONSERVATIVE_DAILY_LAG_DAYS (not 0)
  - passing pit_proof -> its entitled lag (e.g. 0)
  - stale/failing proof -> conservative (fail-closed)
  - align_daily(lag_days) actually embargoes the prediction window (a leaky
    fixture loses the move it was illegally peeking at).

USAGE:
  venv/bin/python -m pytest tests/loop/test_pit_lag.py -q
=============================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
from scripts.harness import evaluate_signal as ev  # noqa: E402

CONS = ev.CONSERVATIVE_DAILY_LAG_DAYS


def test_zero_lag_source_is_zero():
    assert ev.daily_publication_lag_days("ANYTHING", "graph", registry={}) == 0
    assert ev.daily_publication_lag_days("ANYTHING", "gdelt", registry={}) == 0


def test_unproven_variable_fails_closed_to_conservative():
    assert ev.daily_publication_lag_days("FX_RR25_Z252", "market_implied", registry={"proofs": {}}) == CONS
    assert CONS >= 1  # never the old blanket 0


def test_passing_proof_grants_entitled_lag():
    reg = {"proofs": {"COMBINER_RIDGE_DAILY_V1": {"status": "passing", "entitled_lag_days": 0}}}
    assert ev.daily_publication_lag_days("COMBINER_RIDGE_DAILY_V1", "combiner", registry=reg) == 0


def test_stale_proof_fails_closed():
    reg = {"proofs": {"X": {"status": "stale", "entitled_lag_days": 0}}}
    assert ev.daily_publication_lag_days("X", "market_implied", registry=reg) == CONS
    reg2 = {"proofs": {"X": {"status": "unproven", "entitled_lag_days": 0}}}
    assert ev.daily_publication_lag_days("X", "market_implied", registry=reg2) == CONS


def test_signal_spec_override_wins():
    assert ev.daily_publication_lag_days("X", "market_implied",
                                         signal_spec={"publication_lag_days": 3}, registry={}) == 3


def test_align_daily_embargo_shifts_the_window():
    """A signal on day t with a +10% move on t+1 and flat t+2: lag 0 captures
    the move (illegally if not PIT); lag 1 embargoes it away."""
    dates = pd.date_range("2020-01-01", periods=12, freq="B")
    rets = np.zeros(12)
    rets[6] = 0.10  # the move lands on index 6
    returns = pd.DataFrame({"date": dates, "country": "Brazil", "return_1m": rets})
    signal = pd.DataFrame({"date": [dates[5]], "country": ["Brazil"], "value": [1.0]})  # t = index 5

    lag0 = ev.align_daily(signal, returns, horizon_days=1, lag_days=0)
    lag1 = ev.align_daily(signal, returns, horizon_days=1, lag_days=1)
    # lag 0: window = t+1 (index 6) -> sees the +10% move
    assert abs(float(lag0["fwd_return"].iloc[0]) - 0.10) < 1e-9
    # lag 1: window = t+2 (index 7) -> flat, the move is embargoed away
    assert abs(float(lag1["fwd_return"].iloc[0]) - 0.0) < 1e-9


def test_shipped_registry_has_no_unbacked_zero_lag_claims():
    """The shipped pit_proof_registry ships with no 'passing' lag-0 proofs."""
    reg = ev._load_pit_registry()
    proofs = reg.get("proofs") or {}
    passing_zero = [v for v, p in proofs.items()
                    if p.get("status") == "passing" and int(p.get("entitled_lag_days", 0)) == 0]
    assert passing_zero == [], f"unbacked lag-0 proofs present: {passing_zero}"
