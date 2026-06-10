"""Unit tests for deterministic regime tagging."""

import pandas as pd
import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.regime_tagger import tag_regime


def test_crisis_vix():
    row = pd.Series({"vix": 35, "baa_oas": 4.0})
    label, rules = tag_regime(row)
    assert label == "Crisis"
    assert "R1_Crisis" in rules


def test_recession_nber():
    row = pd.Series({"vix": 18, "baa_oas": 2.5, "nber_recession": 1, "fed_funds_chg_12m": -1})
    label, _ = tag_regime(row)
    assert label == "Recession"


def test_expansion():
    row = pd.Series(
        {
            "vix": 15,
            "baa_oas": 2.0,
            "yield_2s10s": 1.0,
            "umcsent": 95,
            "nber_recession": 0,
            "fed_funds_chg_12m": -0.25,
        }
    )
    label, _ = tag_regime(row)
    assert label == "Expansion"


def test_transition_fallback():
    row = pd.Series({"vix": 22, "baa_oas": 2.5, "nber_recession": 0})
    label, rules = tag_regime(row)
    assert label == "Transition"
    assert "R7_Transition" in rules
