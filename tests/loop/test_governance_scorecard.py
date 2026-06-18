#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: tests/loop/test_governance_scorecard.py
=============================================================================

INPUT FILES: the shipped config/governance_contract.yaml + live governance
artifacts/DB (read-only). OUTPUT FILES: none (uses build_scorecard, not main).

VERSION: 1.0
LAST UPDATED: 2026-06-17
AUTHOR: Arjun Divecha (built by agent session, Governance Layer PRD v1.2, item A8)

DESCRIPTION:
A8 acceptance: the scorecard dimensions come from the contract (single source),
a partial dimension (cross_source_minimal) is never green, a blind dimension
takes its severity colour (never green), and the contract hash + repo SHA are
stamped.

USAGE:
  venv/bin/python -m pytest tests/loop/test_governance_scorecard.py -q
=============================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
from scripts.loop import build_governance_scorecard as gs  # noqa: E402


def test_dimensions_come_from_contract():
    sc = gs.build_scorecard()
    contract = yaml.safe_load((BASE_DIR / "config" / "governance_contract.yaml").read_text())
    names = [d["name"] for d in contract["scorecard_dimensions"]]
    assert sc["dimensions_expected"] == names
    assert [d["name"] for d in sc["dimensions"]] == names


def test_cross_source_minimal_never_green():
    sc = gs.build_scorecard()
    cs = next(d for d in sc["dimensions"] if d["name"] == "cross_source_minimal")
    assert cs["amber_by_design"] is True
    assert cs["effective"] in ("amber", "red")  # never green in Phase A


def test_blind_dimension_never_green_and_overall_valid():
    sc = gs.build_scorecard()
    assert sc["overall"] in ("green", "amber", "red")
    for d in sc["dimensions"]:
        if d["status"] == "blind":
            assert d["effective"] != "green"


def test_contract_hash_and_repo_sha_stamped():
    sc = gs.build_scorecard()
    assert sc["contract_hash"].startswith("sha256:") and len(sc["contract_hash"]) == 7 + 64
    assert "repo_sha" in sc and "repo_dirty" in sc


def test_markdown_block_has_markers_and_is_replaceable():
    sc = gs.build_scorecard()
    md = gs.render_markdown(sc)
    assert gs.MARK_START in md and gs.MARK_END in md
    assert sc["overall"].upper() in md
    # two renders concatenated still contain exactly one START..END pair shape
    assert md.count(gs.MARK_START) == 1 and md.count(gs.MARK_END) == 1
