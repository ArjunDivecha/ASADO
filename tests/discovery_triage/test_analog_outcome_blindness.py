"""Tests for the Fixed-Metric Analog Shelf (PR-4): outcome-blind retrieval, frozen
membership, post-freeze outcome attachment, constrained differencing. Offline."""
from __future__ import annotations

import pandas as pd
import pytest

from scripts.discovery_triage.attach_analog_outcomes import (
    attach_analog_outcomes,
    difference_analogs,
)
from scripts.discovery_triage.retrieve_analogs import AnalogError, retrieve_analogs


def _features():
    idx = [f"2020-{m:02d}-01" for m in range(1, 13)]
    return pd.DataFrame({"f1": list(range(12)), "f2": [x * 0.5 for x in range(12)]}, index=idx)


def _returns():
    dates = pd.bdate_range("2020-02-03", periods=320)
    return pd.DataFrame({"date": [str(d.date()) for d in dates], "ret": [0.001] * 320})


def test_retrieve_freezes_outcome_blind_set(tmp_path):
    df = _features()
    sid, rec = retrieve_analogs("macro_state_v1", "2020-01-01", df, k=3,
                                analog_dir=tmp_path, index_path=tmp_path / "idx.jsonl")
    assert sid.startswith("AS_")
    assert rec["k"] == 3 and rec["outcome_blind"] is True and rec["frozen"] is True
    assert rec["outcomes_attached"] is False
    assert (tmp_path / f"{sid}.yaml").exists()
    # nearest by rank distance: 2020-02 / 03 / 04 are closest to 2020-01
    assert rec["members"][0]["key"] == "2020-02-01"


def test_outcome_leaking_features_rejected(tmp_path):
    df = _features()
    df["country_return_21d"] = 1.0  # a forward-return column must never drive selection
    with pytest.raises(AnalogError):
        retrieve_analogs("macro_state_v1", "2020-01-01", df,
                         analog_dir=tmp_path, index_path=tmp_path / "i2.jsonl")


def test_unknown_metric_rejected(tmp_path):
    with pytest.raises(AnalogError):
        retrieve_analogs("not_a_metric", "2020-01-01", _features(),
                         analog_dir=tmp_path, index_path=tmp_path / "i3.jsonl")


def test_attach_outcomes_keeps_membership_and_is_write_once(tmp_path):
    sid, rec = retrieve_analogs("macro_state_v1", "2020-01-01", _features(), k=4,
                                analog_dir=tmp_path, index_path=tmp_path / "idx.jsonl")
    before = [m["key"] for m in rec["members"]]
    rec2 = attach_analog_outcomes(sid, _returns(), 21, analog_dir=tmp_path)
    assert rec2["outcomes_attached"] is True
    assert [m["key"] for m in rec2["members"]] == before        # membership unchanged
    assert all("forward_outcome" in m for m in rec2["members"])
    # re-attaching is refused (frozen set's outcomes are written once)
    with pytest.raises(AnalogError):
        attach_analog_outcomes(sid, _returns(), 21, analog_dir=tmp_path)


def test_differencing_is_constrained(tmp_path):
    sid, rec = retrieve_analogs("macro_state_v1", "2020-01-01", _features(), k=3,
                                analog_dir=tmp_path, index_path=tmp_path / "idx.jsonl")
    before = [m["key"] for m in rec["members"]]
    notes = difference_analogs(rec, ["valuation_state"])
    assert notes and notes[0]["output_type"] == "analog_note"   # never a trade
    assert notes[0]["axis"] == "valuation_state"
    with pytest.raises(AnalogError):
        difference_analogs(rec, ["not_an_axis"])                # disallowed axis
    assert [m["key"] for m in rec["members"]] == before          # membership untouched
