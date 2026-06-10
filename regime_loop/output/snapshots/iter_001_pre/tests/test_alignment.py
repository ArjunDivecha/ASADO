"""IC alignment: lagged factor at t vs return at t."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.ic_analysis import prepare_ic_panel, spearman_ic


def test_no_lookahead_in_panel():
    factors = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-01", "2020-02-01", "2020-03-01"] * 2),
            "country": ["A", "A", "A", "B", "B", "B"],
            "factor": ["F_CS"] * 6,
            "value": [1.0, 2.0, 3.0, 0.5, 1.5, 2.5],
        }
    )
    fwd = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-02-01", "2020-03-01"] * 2),
            "country": ["A", "A", "B", "B"],
            "fwd_ret": [0.1, 0.2, 0.05, 0.15],
        }
    )
    panel = prepare_ic_panel(factors, fwd)
    assert panel["date"].min() == pd.Timestamp("2020-02-01")
    feb_a = panel[(panel["date"] == "2020-02-01") & (panel["country"] == "A")]
    assert feb_a["signal"].iloc[0] == 1.0
