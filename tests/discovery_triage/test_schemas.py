"""Tests for schemas (Pydantic) + jsonl_store hardening (PR-1). Offline.

Covers Sakana must-fix #3 (lock-protected append, not temp-file replace; no
duplicate IDs) and #4/#5 (measurement_shape + expression required on claims).
"""
from __future__ import annotations

import copy
import re
import threading

import pytest
from pydantic import ValidationError

from scripts.discovery_triage import schemas
from scripts.discovery_triage.jsonl_store import append_with_minted_id, now_iso, read_jsonl


def good_claim():
    return {
        "claim_id": "C_20270625_001",
        "links": {"source_look_id": "L_20270625_001"},
        "provenance": {"source": "mythos_discovery_lab", "visibility_mode": "outcome_blind",
                       "certification_route": "post_cutoff_holdout_testable",
                       "certification_window_start": "2027-02-01"},
        "neutral_claim": {"sentence": "FX stress relief may precede 21d relative outperformance."},
        "mechanism": {"text": "Macro hedge markets stop worsening before forced selling exhausts.",
                      "channels": ["fx"]},
        "variables": ["FX_RR25_1M_Z252"],
        "target": {"return_surface": "country_returns_daily", "horizon_days": 21,
                   "direction": "long_high_signal", "target_type": "relative_cross_sectional_return",
                   "measurement_shape": "cross_sectional_rank_ic"},
        "expression": {"etf_ticker": "EWZ", "proxy_type": "country_etf", "liquidity_tier": "tier1"},
        "universe": {"name": "fx+etf", "min_countries": 10},
        "falsification": {"fatal_if": ["target_reentry"], "must_check": ["leave_one_crisis_out"]},
    }


def test_claim_golden_validates():
    schemas.Claim.model_validate(good_claim())


def test_claim_requires_measurement_shape():
    bad = copy.deepcopy(good_claim())
    del bad["target"]["measurement_shape"]
    with pytest.raises(ValidationError):
        schemas.Claim.model_validate(bad)


def test_claim_requires_expression():
    bad = copy.deepcopy(good_claim())
    del bad["expression"]
    with pytest.raises(ValidationError):
        schemas.Claim.model_validate(bad)


def test_graveyard_entry_carries_measurement_shape():
    gy = {
        "claim_id": "C_x", "terminal_or_quarantine_status": "killed_fatal_leakage",
        "start_date": "2027-06-25", "return_surface": "country_returns_daily",
        "measurement_shape": "single_country_event", "direction": "long_high_signal",
    }
    obj = schemas.GraveyardEntry.model_validate(gy)
    assert obj.measurement_shape == "single_country_event"
    # measurement_shape is required (mirrors incubator so forward_track can score it)
    with pytest.raises(ValidationError):
        schemas.GraveyardEntry.model_validate({k: v for k, v in gy.items()
                                               if k != "measurement_shape"})


def test_now_iso_has_offset():
    assert re.search(r"[+-]\d{2}:\d{2}$", now_iso())


def test_validate_failure_leaves_file_intact(tmp_path):
    path = tmp_path / "looks.jsonl"
    append_with_minted_id(path, "L", "look_id", lambda i: {"look_id": i, "ok": True})
    before = path.read_text()

    def boom(_rec):
        raise ValueError("schema rejected")

    with pytest.raises(ValueError):
        append_with_minted_id(path, "L", "look_id", lambda i: {"look_id": i}, validate=boom)
    assert path.read_text() == before  # no torn line, prior content intact
    assert len(read_jsonl(path)) == 1


def test_no_duplicate_ids_under_threads(tmp_path):
    path = tmp_path / "looks.jsonl"
    ids: list[str] = []
    lock = threading.Lock()

    def worker():
        i, _ = append_with_minted_id(path, "L", "look_id", lambda x: {"look_id": x})
        with lock:
            ids.append(i)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(ids) == 8
    assert len(set(ids)) == 8  # flock serialized minting → no collisions
    assert len(read_jsonl(path)) == 8
