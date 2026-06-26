"""Tests for the harness bridge (ported from codex-kahuna). Offline: monkeypatches
the module-level harness/ledger functions — no loop DB, no ledger writes."""
from __future__ import annotations

import pytest

from scripts.discovery_triage import harness_bridge
from scripts.discovery_triage.exceptions import ContextPolicyError
from tests.discovery_triage.fixtures import valid_claim


def harness_claim():
    claim = valid_claim("post_cutoff_holdout_testable")
    claim["family_key"] = "etf_flows"
    claim["signal_spec"] = {"table": "etf_flow_signals", "variable": "ETF_FLOW_21D_Z", "hold_days": 21}
    claim["mechanism"]["text"] = (
        "ETF flow pressure can represent forced positioning, liquidity demand, and ownership crowding "
        "that prices may only absorb with a lag across country ETFs."
    )
    return claim


def test_harness_bridge_reuses_cached_existing_without_registering(monkeypatch):
    claim = harness_claim()
    monkeypatch.setattr(harness_bridge, "find_existing", lambda family, hash_value: {
        "hypothesis_id": "H_20260625_001", "verdict": "WEAK",
        "verdict_json": {"verdict": "WEAK",
                         "ic": {"21": {"mean_ic": 0.03, "nw_t": 2.2, "pct_positive_years": 0.7}},
                         "deflated_sharpe_block": {"deflated_sharpe": -0.1}},
    })
    monkeypatch.setattr(harness_bridge, "register_hypothesis",
                        lambda *a, **k: pytest.fail("should not register cached spec"))
    monkeypatch.setattr(harness_bridge, "evaluate_signal",
                        lambda *a, **k: pytest.fail("should not evaluate cached spec"))
    monkeypatch.setattr(harness_bridge, "resolve_family", lambda variable: "etf_flows")
    monkeypatch.setattr(harness_bridge, "family_trial_count", lambda family: 3)

    overlay = harness_bridge.run_harness_bridge(claim)
    assert overlay["hypothesis_id"] == "H_20260625_001"
    assert overlay["harness_cached"] is True
    assert overlay["harness_stats"]["mean_ic"] == 0.03
    assert overlay["family_trial_count"] == 3


def test_harness_bridge_registers_then_evaluates_uncached(monkeypatch):
    claim = harness_claim()
    calls = []
    monkeypatch.setattr(harness_bridge, "find_existing", lambda family, hash_value: None)
    monkeypatch.setattr(harness_bridge, "resolve_family", lambda variable: "etf_flows")
    monkeypatch.setattr(harness_bridge, "family_trial_count", lambda family: 4)
    monkeypatch.setattr(harness_bridge, "register_hypothesis",
                        lambda **k: (calls.append(("register", k)) or "H_20260625_002"))
    monkeypatch.setattr(harness_bridge, "evaluate_signal",
                        lambda **k: (calls.append(("evaluate", k)) or {
                            "verdict": "WATCH",
                            "ic": {"21": {"mean_ic": 0.04, "nw_t": 3.0, "pct_positive_years": 0.8}},
                            "deflated_sharpe_block": {"deflated_sharpe": 0.2}}))
    overlay = harness_bridge.run_harness_bridge(claim)
    assert [name for name, _ in calls] == ["register", "evaluate"]
    assert overlay["hypothesis_id"] == "H_20260625_002"
    assert overlay["harness_verdict"] == "WATCH"
    assert calls[1][1]["direction"] == "higher_is_better"


def test_harness_bridge_skips_ineligible_route(monkeypatch):
    claim = harness_claim()
    claim["provenance"]["certification_route"] = "prospective_only_unknown_cutoff"
    assert harness_bridge.run_harness_bridge(claim) is None


def test_harness_bridge_rejects_forward_return_variable(monkeypatch):
    claim = harness_claim()
    claim["signal_spec"]["variable"] = "12MRet"
    monkeypatch.setattr(harness_bridge, "resolve_family", lambda variable: "etf_flows")
    with pytest.raises(ContextPolicyError):
        harness_bridge.run_harness_bridge(claim)
