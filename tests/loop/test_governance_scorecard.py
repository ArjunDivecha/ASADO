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


def test_cross_source_minimal_is_status_driven_from_contract():
    # A7/cross_source_minimal was made STATUS-DRIVEN in commit 8295530 (green when
    # sentinels + pair checks pass AND coverage >= 90%, amber on partial/pair, red
    # on hard breach). It is therefore NO LONGER amber-by-design: amber_by_design is
    # read straight from the contract spec (currently false) and its effective colour
    # is driven by the live cross_source_status.json, not hard-coded to never-green.
    contract = yaml.safe_load((BASE_DIR / "config" / "governance_contract.yaml").read_text())
    spec = next(s for s in contract["scorecard_dimensions"] if s["name"] == "cross_source_minimal")

    sc = gs.build_scorecard()
    cs = next(d for d in sc["dimensions"] if d["name"] == "cross_source_minimal")

    # amber_by_design mirrors the contract (single source of truth), whatever it is.
    assert cs["amber_by_design"] is bool(spec.get("amber_by_design", False))

    # When there is no hard/pair breach AND coverage clears the green threshold,
    # the dimension legitimately drives GREEN (this is the whole point of making
    # it status-driven). When a breach or sub-threshold coverage forces amber/red,
    # it must not be green. Assert the builder's actual status-driven contract.
    # Mirror the builder's own status source (build_governance_scorecard._dim_*):
    # the dimension reads Data/loop/governance/cross_source_status.json, so the test
    # reads the exact same artifact to validate the status-driven outcome.
    status_path = gs.GOV_DIR / "cross_source_status.json"
    if status_path.exists():
        import json as _json
        st = _json.loads(status_path.read_text())
    else:
        st = None
    if cs["status"] == "green":
        assert st is not None
        assert not st.get("hard_breach") and not st.get("pair_breach")
        assert float(st.get("coverage_fraction") or 0.0) >= gs.CROSS_SOURCE_GREEN_COVERAGE
        assert cs["effective"] == "green"
    else:
        # If no live status file exists, the builder reports "blind" (never green).
        assert cs["effective"] in ("amber", "red", "blind")
        assert cs["effective"] != "green"
        if st is not None:
            assert (st.get("hard_breach") or st.get("pair_breach")
                    or float(st.get("coverage_fraction") or 0.0) < gs.CROSS_SOURCE_GREEN_COVERAGE)


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
