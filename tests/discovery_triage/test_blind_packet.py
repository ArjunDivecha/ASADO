"""Tests for the blind packet (PR-2A): §16.3 exclusions + route-aware harness stats."""
from __future__ import annotations

from scripts.discovery_triage.build_blind_packet import build_blind_packet


def _claim(route):
    return {
        "claim_id": "C_x",
        "neutral_claim": {"sentence": "FX relief may precede outperformance."},
        "provenance": {"source": "mythos_discovery_lab", "visibility_mode": "outcome_blind",
                       "certification_route": route},
        "target": {"return_surface": "country_returns_daily", "measurement_shape": "cross_sectional_rank_ic",
                   "direction": "long_high_signal"},
        "expression": {"etf_ticker": "EWZ", "proxy_type": "country_etf"},
        # stray forbidden fields that must never reach the packet:
        "bull_case": "THIS IS HUGE",
        "generator_rationale": "the model loved it",
    }


def test_packet_excludes_bull_case_and_rationale():
    packet = build_blind_packet(_claim("post_cutoff_holdout_testable"),
                                {"claim_id": "C_x", "status": "triage_passed_not_validated"})
    blob = str(packet).lower()
    assert "bull_case" not in packet and "huge" not in blob
    assert "generator_rationale" not in packet and "loved it" not in blob
    assert packet["neutral_claim"]["sentence"]


def test_harness_stats_excluded_for_prospective_route():
    stats = {"mean_ic": 0.08, "nw_t": 2.3, "verdict": "WATCH"}
    packet = build_blind_packet(_claim("prospective_only_training_cutoff_contamination"),
                                {"claim_id": "C_x", "status": "triage_passed_not_validated"},
                                harness_stats=stats)
    assert "harness_stats" not in packet
    assert "harness_stats_excluded" in packet


def test_harness_stats_included_for_holdout_route():
    stats = {"mean_ic": 0.08, "nw_t": 2.3, "verdict": "WATCH"}
    packet = build_blind_packet(_claim("post_cutoff_holdout_testable"),
                                {"claim_id": "C_x", "status": "triage_passed_not_validated"},
                                harness_stats=stats)
    assert packet["harness_stats"] == stats
