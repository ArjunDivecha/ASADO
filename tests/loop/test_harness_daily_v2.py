#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: test_harness_daily_v2.py
=============================================================================

INPUT FILES:
- None on disk. All tests run on synthetic in-memory DataFrames.

OUTPUT FILES:
- None. Pure pytest assertions.

VERSION: 1.0
LAST UPDATED: 2026-06-10
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 2)

DESCRIPTION:
Honesty proofs for the v2 DAILY portfolio backtest (overlapping tranches):

 1. EXECUTION-TIMING CANARY: a cheating signal equal to the SAME day's
    return must earn ~nothing (holdings only take effect the NEXT trading
    day), while a perfect-foresight signal equal to the NEXT day's return
    must earn hugely. Together these pin the execution lag to exactly one
    trading day.
 2. TURNOVER: a frozen (constant) signal must produce ~zero turnover after
    the initial build, so net ~= gross - borrow.
 3. COSTS: higher cost cases must never improve net performance.
 4. DEFLATED SHARPE: periods_per_year is honored (daily annualization).

DEPENDENCIES:
- pytest, pandas, numpy (project venv)

USAGE:
 ./venv/bin/python -m pytest tests/loop/test_harness_daily_v2.py -v
=============================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.harness.evaluate_signal import backtest_daily, deflated_sharpe_block

N_COUNTRIES = 20
COUNTRIES = [f"C{i:02d}" for i in range(N_COUNTRIES)]


def make_panels(n_days: int = 400, seed: int = 11):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2022-01-03", periods=n_days)
    rets = pd.DataFrame(rng.normal(0.0, 0.02, size=(n_days, N_COUNTRIES)),
                        index=dates, columns=COUNTRIES)
    return dates, rets


class TestExecutionTiming:
    def test_contemporaneous_cheat_earns_nothing(self):
        """Signal = TODAY's return. Holdings activate tomorrow, so this
        information is already dead - LS Sharpe must be noise-level."""
        _, rets = make_panels()
        res = backtest_daily(rets.copy(), rets, "higher_is_better", hold_days=1)
        assert "error" not in res, res
        assert abs(res["gross"]["ls_sharpe"]) < 1.5

    def test_perfect_foresight_earns_hugely(self):
        """Signal = TOMORROW's return. Next-day execution harvests exactly
        that day - LS Sharpe must be enormous. Pins the lag to ONE day."""
        _, rets = make_panels()
        foresight = rets.shift(-1)
        res = backtest_daily(foresight, rets, "higher_is_better", hold_days=1)
        assert "error" not in res, res
        assert res["gross"]["ls_sharpe"] > 5.0

    def test_two_day_foresight_is_dead_again(self):
        """Signal = return two days ahead, hold 1 day: window covers only
        t+1, so the t+2 information must NOT be harvested."""
        _, rets = make_panels()
        res = backtest_daily(rets.shift(-2), rets, "higher_is_better", hold_days=1)
        assert "error" not in res, res
        assert abs(res["gross"]["ls_sharpe"]) < 1.5


class TestTurnoverAndCosts:
    def test_frozen_signal_zero_turnover(self):
        _, rets = make_panels()
        const = pd.DataFrame(
            np.tile(np.arange(N_COUNTRIES, dtype=float), (len(rets), 1)),
            index=rets.index, columns=COUNTRIES,
        )
        res = backtest_daily(const, rets, "higher_is_better", hold_days=5)
        assert "error" not in res, res
        # initial builds aside, daily turnover must be ~zero
        assert res["avg_daily_turnover_top_oneway"] < 0.01

    def test_costs_monotonic(self):
        _, rets = make_panels(seed=3)
        rng = np.random.default_rng(5)
        sig = pd.DataFrame(rng.normal(size=rets.shape), index=rets.index, columns=COUNTRIES)
        res = backtest_daily(sig, rets, "higher_is_better", hold_days=5)
        assert "error" not in res, res
        ls = [res["net"][f"{b}bps"]["ls_ann_return"] for b in (10, 25, 50)]
        assert ls[0] >= ls[1] >= ls[2]

    def test_tranche_count_matches_hold_days(self):
        _, rets = make_panels()
        rng = np.random.default_rng(9)
        sig = pd.DataFrame(rng.normal(size=rets.shape), index=rets.index, columns=COUNTRIES)
        res = backtest_daily(sig, rets, "higher_is_better", hold_days=21)
        assert "error" not in res, res
        assert res["construction"].startswith("21 overlapping tranches")


class TestDeflatedSharpeDaily:
    def test_periods_per_year_honored(self):
        rng = np.random.default_rng(2)
        r = pd.Series(rng.normal(0.001, 0.01, 600))
        blk = deflated_sharpe_block(r, n_trials=3, periods_per_year=252)
        assert blk["periods_per_year"] == 252
        assert abs(blk["sharpe_annualized"] - blk["sharpe_per_period"] * np.sqrt(252)) < 0.01

    def test_too_short_daily_series_refused(self):
        r = pd.Series(np.random.default_rng(1).normal(0, 0.01, 300))
        blk = deflated_sharpe_block(r, n_trials=3, periods_per_year=252)
        assert np.isnan(blk["deflated_sharpe"])
