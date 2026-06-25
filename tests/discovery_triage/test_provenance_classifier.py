"""Tests for the provenance classifier + visibility-mode normalization (PR-1).

Verifies FuguPRD §7 routing and the Sakana must-fix #1 (alias normalization /
fail-safe on unknown modes). Offline, no network/DB.
"""
from __future__ import annotations

import pytest

from scripts.discovery_triage.provenance import (
    ProvenanceInput,
    classify_provenance,
    normalize_visibility_mode,
)


def route(**kw):
    return classify_provenance(ProvenanceInput(**kw))["certification_route"]


def test_missing_cutoff_routes_prospective():
    r = route(generator_type="llm", visibility_mode="outcome_blind",
              certification_window_start="2027-02-01", tool_enforced_outcome_blind=True)
    assert r == "prospective_only_unknown_cutoff"


def test_window_before_cutoff_is_contaminated():
    r = route(generator_type="llm", visibility_mode="outcome_blind",
              model_training_cutoff="2027-01-31", certification_window_start="2026-06-01",
              tool_enforced_outcome_blind=True)
    assert r == "prospective_only_training_cutoff_contamination"


def test_post_cutoff_tool_blind_is_holdout_testable():
    r = route(generator_type="llm", visibility_mode="outcome_blind",
              model_training_cutoff="2027-01-31", certification_window_start="2027-02-01",
              tool_enforced_outcome_blind=True)
    assert r == "post_cutoff_holdout_testable"


def test_deterministic_is_measured_gap():
    r = route(generator_type="deterministic", visibility_mode="deterministic_detector")
    assert r == "measured_gap_claim_required"


def test_legacy_is_grandfathered():
    r = route(generator_type="human", visibility_mode="legacy_unknown")
    assert r == "legacy_grandfathered_forward_tracking"


@pytest.mark.parametrize("alias", ["tool_outcome_blind", "tool-outcome-blind", "Tool Outcome Blind"])
def test_aliases_normalize_to_outcome_blind(alias):
    assert normalize_visibility_mode(alias) == "outcome_blind"


def test_alias_does_not_bypass_enforcement():
    # A PRD-style alias must route identically to canonical outcome_blind.
    r = route(generator_type="llm", visibility_mode="tool_outcome_blind",
              model_training_cutoff="2027-01-31", certification_window_start="2027-02-01",
              tool_enforced_outcome_blind=True)
    assert r == "post_cutoff_holdout_testable"


def test_unknown_mode_is_fail_safe_error():
    with pytest.raises(ValueError):
        normalize_visibility_mode("definitely_not_a_mode")
    with pytest.raises(ValueError):
        normalize_visibility_mode("")
