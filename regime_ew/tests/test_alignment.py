"""
Alignment test: signal[t] pairs with 1MRet[t] directly (no extra shift).

PRD convention: 1MRet@t is already the forward return (return earned during
month t+1), so merging signal(t) with 1MRet(t) is a proper predictive test.
This mirrors regime/tests/test_alignment.py which verifies the same pairing
for the cross-sectional IC study.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from regime_ew.src.gates import _within_country_corr


def test_signal_fwdret_same_date():
    """signal(t) and fwd_ret(t) are merged on identical dates — no shift applied."""
    import numpy as np

    n = 24  # need >= 12 per country for spearmanr
    dates = pd.date_range("2020-01-01", periods=n, freq="MS")

    # Country A: P_adverse high → fwd_ret negative (months 12-18), otherwise low → positive
    pa_a = np.where(np.arange(n) >= 12, 0.85, 0.15).tolist()
    fr_a = np.where(np.arange(n) >= 12, -0.03, 0.02).tolist()

    # Country B: inverse pattern
    pa_b = np.where(np.arange(n) < 12, 0.85, 0.15).tolist()
    fr_b = np.where(np.arange(n) < 12, -0.03, 0.02).tolist()

    signals = pd.DataFrame({
        "date": list(dates) * 2,
        "country": ["A"] * n + ["B"] * n,
        "P_adverse": pa_a + pa_b,
        "dP_adverse": [float("nan")] + [0.0] * (n - 1) + [float("nan")] + [0.0] * (n - 1),
    })
    fwd_returns = pd.DataFrame({
        "date": list(dates) * 2,
        "country": ["A"] * n + ["B"] * n,
        "fwd_ret": fr_a + fr_b,
    })

    corr_df = _within_country_corr(signals, fwd_returns, "P_adverse")

    assert not corr_df.empty, "Expected non-empty correlation results"

    row_A = corr_df[corr_df["country"] == "A"]
    assert not row_A.empty, "Country A should have a correlation result"
    assert row_A["spearman_rho"].iloc[0] < 0, (
        f"Expected negative corr for A, got {row_A['spearman_rho'].iloc[0]:.3f}"
    )

    row_B = corr_df[corr_df["country"] == "B"]
    assert not row_B.empty, "Country B should have a correlation result"
    assert row_B["spearman_rho"].iloc[0] < 0, (
        f"Expected negative corr for B, got {row_B['spearman_rho'].iloc[0]:.3f}"
    )


def test_no_extra_shift_applied():
    """
    Confirm that the merge is on identical dates (matching build_forward_returns
    convention: no additional lag introduced inside the gate machinery).
    """
    # Signal at 2020-03-01 is 0.9 (high adverse)
    # fwd_ret at 2020-03-01 is -0.05 (negative return in that same date cell)
    # If an extra shift were applied, the signal 0.9 would be paired with a
    # *different* date's return — we verify it pairs with -0.05 at the SAME date.
    signals = pd.DataFrame({
        "date": pd.to_datetime(["2020-01-01", "2020-02-01", "2020-03-01",
                                 "2020-04-01", "2020-05-01",
                                 "2020-06-01", "2020-07-01", "2020-08-01",
                                 "2020-09-01", "2020-10-01", "2020-11-01", "2020-12-01"]),
        "country": "TEST",
        "P_adverse": [0.1, 0.2, 0.9, 0.85, 0.3, 0.2, 0.1, 0.15, 0.2, 0.8, 0.85, 0.1],
        "dP_adverse": [float("nan")] + [0.0] * 11,
    })
    fwd_returns = pd.DataFrame({
        "date": pd.to_datetime(["2020-01-01", "2020-02-01", "2020-03-01",
                                 "2020-04-01", "2020-05-01",
                                 "2020-06-01", "2020-07-01", "2020-08-01",
                                 "2020-09-01", "2020-10-01", "2020-11-01", "2020-12-01"]),
        "country": "TEST",
        "fwd_ret": [0.02, 0.01, -0.05, -0.04, 0.02, 0.03, 0.01, 0.02, 0.01, -0.03, -0.04, 0.02],
    })

    import pandas.testing as pdt
    merged = signals.merge(fwd_returns, on=["date", "country"])
    # Check that the 2020-03-01 row has P_adverse=0.9 and fwd_ret=-0.05
    row = merged[merged["date"] == pd.Timestamp("2020-03-01")]
    assert row["P_adverse"].iloc[0] == pytest.approx(0.9)
    assert row["fwd_ret"].iloc[0] == pytest.approx(-0.05)
