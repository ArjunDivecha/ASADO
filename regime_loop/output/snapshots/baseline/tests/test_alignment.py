"""
=============================================================================
SCRIPT NAME: test_alignment.py
=============================================================================

DESCRIPTION:
    Unit tests for IC (Information Coefficient) alignment in a factor
    regime-loop framework. Verifies that there is no lookahead bias when
    matching lagged factor values (at time t) to forward returns (at time
    t+1). Constructs in-memory factor and forward-return DataFrames with
    known values, passes them through prepare_ic_panel(), and asserts
    that the resulting panel correctly aligns signals and returns without
    leaking future information into past observations.

INPUT FILES:
    (none — this script constructs its own test data in memory)

OUTPUT FILES:
    (none — this script only runs assertions via pytest)

VERSION: 1.0
LAST UPDATED: 2026-06-05
AUTHOR: Arjun Divecha

DEPENDENCIES:
    - pandas
    - src.ic_analysis (from local package)

USAGE:
    python test_alignment.py

NOTES:
    - Intended to be run via pytest (pytest will auto-discover the tests).
    - Requires the parent directory to be importable; sys.path is patched
      at the top of the file to include the package root.
=============================================================================
"""

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
