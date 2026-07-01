from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from regime_ew.src.contrarian_strategy import add_time_series_percentile, evaluate_weights  # noqa: E402


def test_time_series_percentile_uses_prior_history_only():
    panel = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=5, freq="MS"),
            "country": ["A"] * 5,
            "P_adverse": [0.1, 0.2, 0.3, 0.4, 0.5],
            "dP_adverse": [None, 0.1, 0.1, 0.1, 0.1],
            "fwd_ret_1m": [0.0] * 5,
            "fwd_ret_3m": [0.0] * 5,
        }
    )
    out = add_time_series_percentile(panel, min_history=3)
    assert pd.isna(out.loc[out["date"] == "2020-03-01", "P_adverse_ts_pct"]).iloc[0]
    assert out.loc[out["date"] == "2020-04-01", "P_adverse_ts_pct"].iloc[0] == 1.0


def test_turnover_cost_reduces_return():
    panel = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-01", "2020-01-01", "2020-02-01", "2020-02-01"]),
            "country": ["A", "B", "A", "B"],
            "fwd_ret_1m": [0.02, -0.01, 0.03, -0.02],
        }
    )
    weights = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-01", "2020-01-01", "2020-02-01", "2020-02-01"]),
            "country": ["A", "B", "A", "B"],
            "weight": [1.0, -1.0, 1.0, -1.0],
        }
    )
    returns, summary = evaluate_weights(panel, weights, "TEST", cost_bps=(0.0, 10.0))
    assert returns["gross_ret"].iloc[0] == 0.03
    assert returns["net_ret_10bps"].iloc[0] < returns["gross_ret"].iloc[0]
    assert summary["gross_sharpe"] >= summary["net_10bps_sharpe"]

