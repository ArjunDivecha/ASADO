"""Tests for the blind ruling protocol (red-team 2026-06-26: H3 wiring + M2 gates).

Covers the enforced blind orchestrator (judge sees ONLY the scrubbed packet), the
Invariant-F language gate on rulings, and the one-unseal-per-ruling rule.
"""
from __future__ import annotations

import pytest

from scripts.discovery_triage.record_blind_ruling import (
    BlindRulingError,
    record_blind_ruling,
    record_unseal,
    rule_on_blind_packet,
)


def _claim():
    return {
        "claim_id": "C_x",
        "neutral_claim": {"sentence": "FX relief may precede outperformance.",
                          "rationale": "BULL CASE: huge, the model loved it"},
        "provenance": {"source": "mythos_discovery_lab", "visibility_mode": "outcome_blind",
                       "certification_route": "post_cutoff_holdout_testable"},
        "target": {"return_surface": "country_returns_daily",
                   "measurement_shape": "cross_sectional_rank_ic", "direction": "long_high_signal"},
        "expression": {"etf_ticker": "EWZ", "proxy_type": "country_etf"},
        "bull_case": "THIS IS HUGE",
    }


def test_orchestrator_passes_only_scrubbed_packet_to_judge(tmp_path):
    seen = {}

    def judge(packet):
        seen["packet"] = packet
        return "incubate", "looks plausible, route prospective"

    path = tmp_path / "rulings.jsonl"
    rid, rec = rule_on_blind_packet(claim=_claim(), triage_result={"claim_id": "C_x", "status": "ok"},
                                    judge="arjun", decide=judge, rulings_path=path)
    assert rid.startswith("R_")
    blob = str(seen["packet"]).lower()
    # the judge never saw the bull case / nested rationale
    assert "huge" not in blob and "loved it" not in blob and "bull_case" not in str(seen["packet"])
    assert rec["blind_ruling"]["decision"] == "incubate"


def test_ruling_language_gate_rejects_promotion(tmp_path):
    path = tmp_path / "rulings.jsonl"
    with pytest.raises(BlindRulingError):
        record_blind_ruling(claim_id="C_x", judge="arjun",
                            decision="validated alpha — promote", rationale="great", rulings_path=path)


def test_second_unseal_is_refused(tmp_path):
    path = tmp_path / "rulings.jsonl"
    rid, _ = record_blind_ruling(claim_id="C_x", judge="arjun", decision="incubate",
                                 rationale="ok", rulings_path=path)
    record_unseal(ruling_id=rid, post_unseal_decision="kill", rulings_path=path)
    with pytest.raises(BlindRulingError):
        record_unseal(ruling_id=rid, post_unseal_decision="incubate", rulings_path=path)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
