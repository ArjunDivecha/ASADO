#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: tests/loop/test_cross_source.py
=============================================================================

INPUT FILES: none (synthetic fixtures). OUTPUT FILES: none.

VERSION: 1.0
LAST UPDATED: 2026-06-17
AUTHOR: Arjun Divecha (built by agent session, Governance Layer PRD v1.2, item A7)

DESCRIPTION:
A7 acceptance: the cross-source pair detector catches a GSAB-style swap (one
country's series silently carrying another country's values) and does NOT flag
two agreeing sources.

USAGE:
  venv/bin/python -m pytest tests/loop/test_cross_source.py -q
=============================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
from scripts.loop import check_cross_source as ccs  # noqa: E402

_MONTHS = [pd.Timestamp(f"2026-{m:02d}-28") for m in range(1, 7)]


def _tidy(rows):
    return pd.DataFrame([{"date": d, "country": c, "value": v}
                         for d in _MONTHS for c, v in rows])


def test_synthetic_gsab_swap_caught():
    # Source A (truth): Saudi 10Y ~4.0, South Africa ~10.0
    a = _tidy([("Saudi Arabia", 4.0), ("South Africa", 10.0)])
    # Source B: Saudi silently carries South Africa's 10.0 (the GSAB swap)
    b = _tidy([("Saudi Arabia", 10.0), ("South Africa", 10.0)])
    breaches, checked = ccs.cross_source_discrepancies(a, b, threshold_abs=2.0)
    flagged = {x["country"] for x in breaches}
    assert "Saudi Arabia" in flagged, "the swapped series must breach"
    assert "South Africa" not in flagged, "the correct series must not breach"
    assert set(checked) == {"Saudi Arabia", "South Africa"}


def test_agreeing_sources_no_breach():
    a = _tidy([("Brazil", 14.2)])
    b = _tidy([("Brazil", 14.25)])  # tiny convention difference
    breaches, checked = ccs.cross_source_discrepancies(a, b, threshold_abs=2.0)
    assert breaches == []
    assert checked == ["Brazil"]


def test_no_overlap_returns_empty():
    a = _tidy([("Brazil", 14.0)])
    b = pd.DataFrame([{"date": pd.Timestamp("2019-01-28"), "country": "Brazil", "value": 9.0}])
    breaches, checked = ccs.cross_source_discrepancies(a, b, threshold_abs=2.0)
    assert breaches == [] and checked == []
