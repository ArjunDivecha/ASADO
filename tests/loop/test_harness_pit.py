#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: test_harness_pit.py
=============================================================================

INPUT FILES:
- None on disk. All tests run on synthetic in-memory DataFrames.

OUTPUT FILES:
- None. Pure pytest assertions.

VERSION: 1.0
LAST UPDATED: 2026-06-10
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 1)

DESCRIPTION:
Point-in-time (PIT) and correctness tests for the evaluation harness's pure
computational core. These tests are the harness's honesty proof:

 1. ALIGNMENT: signal month M with lag 0 must be matched to the return of
    month M+1 exactly - never M (contemporaneous) and never M-1 (backward).
 2. EMBARGO: with lag 1 the same signal must be matched to M+2.
 3. LOOKAHEAD CANARY: a cheating signal equal to the SAME month's return
    must show ZERO correlation with the harness's forward returns at lag 0
    horizon 1 (if the harness ever leaked contemporaneous returns this test
    screams).
 4. PERFECT-FORESIGHT CANARY: a signal equal to NEXT month's return must
    show IC = 1.0 - proving the alignment window is exactly month M+1.
 5. Horizon compounding, rank-IC math, NW t-stat sanity, deflated Sharpe
    monotonicity in trial count, and verdict gates.

DEPENDENCIES:
- pytest, pandas, numpy, scipy (project venv)

USAGE:
 ./venv/bin/python -m pytest tests/loop/test_harness_pit.py -v
=============================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.harness.evaluate_signal import (
    align_daily,
    align_monthly,
    decide_verdict,
    deflated_sharpe_block,
    expected_max_sharpe,
    nw_tstat,
    rank_ic_series,
)

COUNTRIES = ["Brazil", "Chile", "Japan", "Korea", "Turkey"]


def make_returns(months: int = 36, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=months, freq="MS")
    rows = [
        {"date": d, "country": c, "return_1m": float(rng.normal(0.005, 0.05))}
        for d in dates for c in COUNTRIES
    ]
    return pd.DataFrame(rows)


def returns_lookup(returns: pd.DataFrame) -> dict:
    return {(r.country, pd.Timestamp(r.date)): r.return_1m for r in returns.itertuples()}


class TestMonthlyAlignment:
    def test_lag0_h1_matches_next_month_exactly(self):
        returns = make_returns()
        signal = returns.rename(columns={"return_1m": "value"}).copy()
        aligned = align_monthly(signal, returns, lag_months=0, horizon_months=1)
        lut = returns_lookup(returns)
        assert len(aligned) > 0
        for row in aligned.itertuples():
            expected = lut[(row.country, pd.Timestamp(row.date) + pd.DateOffset(months=1))]
            assert abs(row.fwd_return - expected) < 1e-12, (
                f"{row.country} {row.date}: fwd {row.fwd_return} != next-month {expected}"
            )

    def test_lag1_h1_matches_month_after_next(self):
        returns = make_returns()
        signal = returns.rename(columns={"return_1m": "value"}).copy()
        aligned = align_monthly(signal, returns, lag_months=1, horizon_months=1)
        lut = returns_lookup(returns)
        for row in aligned.itertuples():
            expected = lut[(row.country, pd.Timestamp(row.date) + pd.DateOffset(months=2))]
            assert abs(row.fwd_return - expected) < 1e-12

    def test_horizon3_compounds_exactly(self):
        returns = make_returns()
        signal = returns.rename(columns={"return_1m": "value"}).copy()
        aligned = align_monthly(signal, returns, lag_months=0, horizon_months=3)
        lut = returns_lookup(returns)
        for row in aligned.itertuples():
            base = pd.Timestamp(row.date)
            rs = [lut[(row.country, base + pd.DateOffset(months=k))] for k in (1, 2, 3)]
            expected = (1 + rs[0]) * (1 + rs[1]) * (1 + rs[2]) - 1
            assert abs(row.fwd_return - expected) < 1e-10

    def test_lookahead_canary_contemporaneous_signal_uncorrelated(self):
        """A signal equal to the SAME month's return must NOT predict the
        harness's forward return (IC ~ 0). If this fails, returns leak."""
        returns = make_returns(months=120)
        cheat = returns.rename(columns={"return_1m": "value"}).copy()
        aligned = align_monthly(cheat, returns, lag_months=0, horizon_months=1)
        ic = rank_ic_series(aligned, min_countries=5)
        assert abs(ic.mean()) < 0.10, f"contemporaneous leak! mean IC = {ic.mean():.3f}"

    def test_perfect_foresight_canary_ic_is_one(self):
        """A signal equal to NEXT month's return must give IC == 1.0 exactly,
        proving the alignment window is exactly month M+1."""
        returns = make_returns()
        sig_rows = []
        lut = returns_lookup(returns)
        for (c, d), r in lut.items():
            prev = d - pd.DateOffset(months=1)
            if (c, prev) in lut:
                sig_rows.append({"date": prev, "country": c, "value": r})
        foresight = pd.DataFrame(sig_rows)
        aligned = align_monthly(foresight, returns, lag_months=0, horizon_months=1)
        ic = rank_ic_series(aligned, min_countries=5)
        assert len(ic) > 20
        assert ic.min() > 0.999, f"foresight IC should be 1.0, got min {ic.min()}"

    def test_no_backward_matching(self):
        """Signal in the LAST month has no forward return -> dropped."""
        returns = make_returns(months=12)
        last = returns["date"].max()
        signal = pd.DataFrame(
            [{"date": last, "country": c, "value": 1.0} for c in COUNTRIES]
        )
        aligned = align_monthly(signal, returns, lag_months=0, horizon_months=1)
        assert aligned.empty


class TestDailyAlignment:
    def test_daily_h1_matches_next_day(self):
        rng = np.random.default_rng(3)
        dates = pd.bdate_range("2024-01-02", periods=60)
        returns = pd.DataFrame(
            [{"date": d, "country": "Japan", "return_1m": float(rng.normal(0, 0.01))} for d in dates]
        )
        signal = returns.rename(columns={"return_1m": "value"}).copy()
        aligned = align_daily(signal, returns, horizon_days=1)
        ret_by_date = returns.set_index("date")["return_1m"]
        for row in aligned.itertuples():
            i = list(dates).index(pd.Timestamp(row.date))
            assert abs(row.fwd_return - ret_by_date.iloc[i + 1]) < 1e-12


class TestStatsCore:
    def test_nw_tstat_zero_mean(self):
        rng = np.random.default_rng(0)
        s = pd.Series(rng.normal(0, 1, 500))
        assert abs(nw_tstat(s, max_lag=3)) < 3.0

    def test_nw_tstat_strong_mean(self):
        s = pd.Series(np.random.default_rng(1).normal(0.5, 1, 500))
        assert nw_tstat(s, max_lag=3) > 5.0

    def test_expected_max_sharpe_increases_with_trials(self):
        e1 = expected_max_sharpe(1, 120)
        e10 = expected_max_sharpe(10, 120)
        e100 = expected_max_sharpe(100, 120)
        assert e1 == 0.0
        assert e10 > e1
        assert e100 > e10

    def test_deflated_sharpe_penalized_by_trials(self):
        rng = np.random.default_rng(5)
        r = pd.Series(rng.normal(0.01, 0.03, 120))
        d1 = deflated_sharpe_block(r, n_trials=1)
        d50 = deflated_sharpe_block(r, n_trials=50)
        assert d1["deflated_sharpe"] > d50["deflated_sharpe"]

    def test_verdict_insufficient_coverage(self):
        v, _ = decide_verdict({"coverage_fail": True, "history_fail": False,
                               "primary_nw_t": 5.0, "pct_positive_years": 1.0}, "monthly")
        assert v == "INSUFFICIENT_COVERAGE"

    def test_verdict_watch_requires_all_gates(self):
        base = {"coverage_fail": False, "history_fail": False,
                "primary_nw_t": 3.0, "pct_positive_years": 0.8,
                "ls_sharpe_net25": 0.5, "top_excess_net25": 0.02, "deflated_sharpe": 0.05}
        v, _ = decide_verdict(base, "monthly")
        assert v == "WATCH"
        for k, bad in [("primary_nw_t", 2.0), ("pct_positive_years", 0.5),
                       ("ls_sharpe_net25", -0.1), ("deflated_sharpe", -0.01)]:
            m = dict(base)
            m[k] = bad
            v, _ = decide_verdict(m, "monthly")
            assert v != "WATCH", f"gate {k} did not block WATCH"

    def test_verdict_dead_when_no_signal(self):
        v, _ = decide_verdict({"coverage_fail": False, "history_fail": False,
                               "primary_nw_t": 0.3, "pct_positive_years": 0.5,
                               "ls_sharpe_net25": None, "top_excess_net25": None,
                               "deflated_sharpe": None}, "monthly")
        assert v == "DEAD"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
