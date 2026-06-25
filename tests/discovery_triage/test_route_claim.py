"""Tests for the router + blind ruling (PR-2A). Offline."""
from __future__ import annotations

from scripts.discovery_triage.jsonl_store import read_jsonl
from scripts.discovery_triage.record_blind_ruling import (
    latest_ruling,
    record_blind_ruling,
    record_unseal,
)
from scripts.discovery_triage.route_claim import route_claim


def _claim():
    return {
        "claim_id": "C_20270625_001",
        "links": {"hypothesis_id": "H_20270625_001"},
        "target": {"return_surface": "country_returns_daily",
                   "measurement_shape": "cross_sectional_rank_ic", "direction": "long_high_signal"},
    }


def test_prospective_routes_to_incubator(tmp_path):
    prospective = tmp_path / "prospective_queue.jsonl"
    graveyard = tmp_path / "graveyard.jsonl"
    arm, rec = route_claim(_claim(), "prospective_only",
                           prospective_path=prospective, graveyard_path=graveyard)
    assert arm == "incubator"
    assert rec["record_kind"] == "incubator_entry"
    assert rec["measurement_shape"] == "cross_sectional_rank_ic"
    assert rec["in_sample_certification"] == "forbidden"
    assert not graveyard.exists()
    assert len(read_jsonl(prospective)) == 1


def test_killed_routes_to_graveyard_with_shape(tmp_path):
    prospective = tmp_path / "prospective_queue.jsonl"
    graveyard = tmp_path / "graveyard.jsonl"
    arm, rec = route_claim(_claim(), "killed_fatal_leakage",
                           prospective_path=prospective, graveyard_path=graveyard)
    assert arm == "graveyard"
    assert rec["record_kind"] == "graveyard_entry"
    assert rec["forward_tracking_enabled"] is True
    # measurement_shape mirrored on the control arm (Sakana fix)
    assert rec["measurement_shape"] == "cross_sectional_rank_ic"
    assert rec["direction"] == "long_high_signal"


def test_blind_ruling_then_unseal_logs_change(tmp_path):
    rulings = tmp_path / "blind_rulings.jsonl"
    rid, _ = record_blind_ruling(claim_id="C_x", judge="Arjun", decision="prospective_only",
                                 rationale="forward-only; pre-cutoff discovery.", rulings_path=rulings)
    assert rid.startswith("R_")
    # unseal with a DIFFERENT decision -> ruling_changed_after_unseal True
    rec = record_unseal(ruling_id=rid, post_unseal_decision="incubating", rulings_path=rulings)
    assert rec["unseal"]["ruling_changed_after_unseal"] is True
    assert latest_ruling(rid, rulings)["unseal"]["post_unseal_decision"] == "incubating"


def test_blind_ruling_unchanged_after_unseal(tmp_path):
    rulings = tmp_path / "blind_rulings.jsonl"
    rid, _ = record_blind_ruling(claim_id="C_y", judge="Arjun", decision="prospective_only",
                                 rationale="r", rulings_path=rulings)
    rec = record_unseal(ruling_id=rid, post_unseal_decision="prospective_only", rulings_path=rulings)
    assert rec["unseal"]["ruling_changed_after_unseal"] is False
