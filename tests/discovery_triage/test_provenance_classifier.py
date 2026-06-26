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


# --- C2 (red-team 2026-06-26): pit_preregistered cannot bypass the cutoff ----
def test_harness_still_gets_historical_route():
    r = route(generator_type="harness", visibility_mode="pit_preregistered")
    assert r == "standard_harness_then_triage"


def test_llm_pit_preregistered_precutoff_without_proof_is_contaminated():
    # The exact runtime-reproduced bypass: an LLM idea declaring pit_preregistered
    # with a pre-cutoff window and NO verifiable proof must NOT be historical.
    r = route(generator_type="llm", visibility_mode="pit_preregistered",
              model_training_cutoff="2025-03-01", certification_window_start="2010-01-01")
    assert r == "prospective_only_training_cutoff_contamination"


def test_llm_pit_preregistered_postcutoff_without_proof_is_prospective():
    r = route(generator_type="llm", visibility_mode="pit_preregistered",
              model_training_cutoff="2025-03-01", certification_window_start="2026-06-01")
    assert r == "prospective_only_no_tool_enforced_blindness"


def test_llm_pit_preregistered_with_verified_proof_is_historical():
    # A genuine pre-registration artifact dated before the window earns historical cert.
    r = route(generator_type="llm", visibility_mode="pit_preregistered",
              model_training_cutoff="2025-03-01", certification_window_start="2024-01-01",
              pit_proof_ts="2023-06-01")
    assert r == "standard_harness_then_triage"


def test_human_pit_preregistered_without_proof_is_prospective():
    r = route(generator_type="human", visibility_mode="pit_preregistered",
              certification_window_start="2026-06-01")
    assert r == "prospective_only_unverified_preregistration"
