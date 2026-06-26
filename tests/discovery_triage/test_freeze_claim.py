"""Tests for freeze_claim schema + gates (PR-1, no harness). Offline.

Covers the cutoff gate (Invariant D — classifier overrides caller route; no
laundering), the language gate (Invariant F), and sealed-rationale separation.
"""
from __future__ import annotations

import copy

import pytest

from scripts.discovery_triage import schemas
from scripts.discovery_triage.freeze_claim import ClaimGateError, freeze_claim
from scripts.discovery_triage.jsonl_store import read_jsonl


def _registry(tmp_path):
    reg = tmp_path / "model_registry.yaml"
    reg.write_text("version: 1\nmodels:\n  testmodel:\n    training_cutoff: '2027-01-31'\n")
    return reg


def _paths(tmp_path):
    return dict(
        registry_path=_registry(tmp_path),
        claims_path=tmp_path / "claims.jsonl",
        claims_dir=tmp_path / "claims",
        sealed_dir=tmp_path / "sealed",
    )


def claim(window="2027-02-01", vis="tool_outcome_blind", tool_enforced=True):
    return {
        "links": {"source_look_id": "L_x"},
        "provenance": {"source": "mythos_discovery_lab", "visibility_mode": vis,
                       "model_id": "testmodel", "certification_window_start": window,
                       "tool_enforced_outcome_blind": tool_enforced,
                       "certification_route": "post_cutoff_holdout_testable"},  # caller-supplied; must be overridden
        "neutral_claim": {"sentence": "FX stress relief may precede 21d relative outperformance."},
        "mechanism": {"text": "Macro hedge markets stop worsening before forced selling exhausts.",
                      "channels": ["fx"]},
        "variables": ["FX_RR25_1M_Z252"],
        "target": {"return_surface": "country_returns_daily", "horizon_days": 21,
                   "direction": "long_high_signal", "target_type": "relative_cross_sectional_return",
                   "measurement_shape": "cross_sectional_rank_ic"},
        "expression": {"etf_ticker": "EWZ", "proxy_type": "country_etf"},
        "universe": {"name": "fx+etf", "min_countries": 10},
        "falsification": {"fatal_if": ["target_reentry"], "must_check": ["leave_one_crisis_out"]},
    }


def test_valid_post_cutoff_claim_freezes_and_separates_bull_case(tmp_path):
    p = _paths(tmp_path)
    bull = {"bull_case": "This is huge because forced sellers are exhausted."}
    cid, rec = freeze_claim(claim(window="2027-02-01"), sealed_rationale=bull,
                            generator_type="llm", historical_intent=True, **p)
    assert cid.startswith("C_")
    # claim landed in ledger + per-object yaml
    assert len(read_jsonl(p["claims_path"])) == 1
    assert (p["claims_dir"] / f"{cid}.yaml").exists()
    # route computed by classifier (post-cutoff tool-blind) — not the caller string
    assert rec["provenance"]["certification_route"] == "post_cutoff_holdout_testable"
    # bull case is NOT in the claim record; only the sealed id is linked
    assert "bull_case" not in str(rec)
    sr_id = rec["links"]["sealed_rationale_id"]
    assert sr_id.startswith("SR_")
    sealed_file = p["sealed_dir"] / f"{sr_id}.yaml"
    assert sealed_file.exists()
    assert "bull_case" in sealed_file.read_text()
    schemas.Claim.model_validate(rec)


def test_cutoff_gate_blocks_pre_cutoff_historical_certification(tmp_path):
    p = _paths(tmp_path)
    with pytest.raises(ClaimGateError):
        # window before the model cutoff → classifier returns contamination route;
        # historical_intent must be refused (no laundering).
        freeze_claim(claim(window="2026-06-01"), generator_type="llm",
                     historical_intent=True, **p)


def test_caller_route_is_overridden_by_classifier(tmp_path):
    p = _paths(tmp_path)
    # Same pre-cutoff claim, but prospective intent (not historical) → allowed,
    # and the caller's optimistic route is overwritten with the true one.
    cid, rec = freeze_claim(claim(window="2026-06-01"), generator_type="llm",
                            historical_intent=False, **p)
    assert rec["provenance"]["certification_route"] == "prospective_only_training_cutoff_contamination"


def test_language_gate_rejects_forbidden_vocab(tmp_path):
    p = _paths(tmp_path)
    bad = claim()
    bad["neutral_claim"]["sentence"] = "This is validated alpha and a clear trade recommendation."
    with pytest.raises(ClaimGateError):
        freeze_claim(bad, generator_type="llm", **p)


def test_missing_certification_window_is_rejected(tmp_path):
    p = _paths(tmp_path)
    bad = claim()
    bad["provenance"]["certification_window_start"] = None
    with pytest.raises(ClaimGateError):
        freeze_claim(bad, generator_type="llm", **p)


def test_missing_falsification_is_rejected(tmp_path):
    p = _paths(tmp_path)
    bad = claim()
    del bad["falsification"]
    with pytest.raises(Exception):  # pydantic ValidationError inside the locked append
        freeze_claim(bad, generator_type="llm", **p)


def _claim_with_spec():
    c = claim(window="2027-02-01")  # post-cutoff (cutoff 2027-01-31) -> holdout-testable
    c["signal_spec"] = {"table": "market_implied_signals", "variable": "FX_RR25_1M_Z252"}
    c["family_key"] = "fx_2027_06"
    return c


def test_harness_wire_attaches_overlay(tmp_path, monkeypatch):
    from scripts.discovery_triage import harness_bridge
    calls = {"register": 0, "evaluate": 0}

    def reg(**k):
        calls["register"] += 1
        return "H_TEST_001"

    def ev(**k):
        calls["evaluate"] += 1
        calls["direction"] = k["direction"]
        calls["start_date"] = k.get("start_date")
        return {"verdict": "WATCH", "ic": {"21": {"mean_ic": 0.05, "nw_t": 2.2}}}

    monkeypatch.setattr(harness_bridge, "find_existing", lambda fk, h: None)
    monkeypatch.setattr(harness_bridge, "resolve_family", lambda v: "fx_family")
    monkeypatch.setattr(harness_bridge, "family_trial_count", lambda f: 2)
    monkeypatch.setattr(harness_bridge, "register_hypothesis", reg)
    monkeypatch.setattr(harness_bridge, "evaluate_signal", ev)

    cid, rec = freeze_claim(_claim_with_spec(), generator_type="llm", historical_intent=True,
                            run_harness=True, **_paths(tmp_path))
    assert rec["links"]["hypothesis_id"] == "H_TEST_001"
    assert rec["harness_verdict"] == "WATCH"
    assert rec["harness_stats"]["mean_ic"] == 0.05
    assert rec["family_trial_count"] == 2
    assert calls["register"] == 1 and calls["evaluate"] == 1
    assert calls["direction"] == "higher_is_better"        # long_high_signal -> higher_is_better
    assert calls["start_date"] == "2027-02-01"             # post-cutoff holdout window only


def test_harness_wire_reuses_existing_without_recharge(tmp_path, monkeypatch):
    from scripts.discovery_triage import harness_bridge
    monkeypatch.setattr(harness_bridge, "find_existing", lambda fk, h: {
        "hypothesis_id": "H_OLD_009", "verdict": "WEAK", "verdict_json": {"verdict": "WEAK"}})
    monkeypatch.setattr(harness_bridge, "resolve_family", lambda v: "fx_family")
    monkeypatch.setattr(harness_bridge, "family_trial_count", lambda f: 5)
    monkeypatch.setattr(harness_bridge, "register_hypothesis",
                        lambda **k: pytest.fail("should not register cached spec"))
    monkeypatch.setattr(harness_bridge, "evaluate_signal",
                        lambda **k: pytest.fail("should not evaluate cached spec"))

    cid, rec = freeze_claim(_claim_with_spec(), generator_type="llm", historical_intent=True,
                            run_harness=True, **_paths(tmp_path))
    assert rec["links"]["hypothesis_id"] == "H_OLD_009"
    assert rec["harness_verdict"] == "WEAK"
    assert rec["harness_cached"] is True
