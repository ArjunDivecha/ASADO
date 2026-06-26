"""Shared test fixtures for Discovery Triage (ported from codex-kahuna)."""
from __future__ import annotations


def valid_claim(route: str = "prospective_only_unknown_cutoff") -> dict:
    return {
        "claim_id": "C_20260625_001",
        "links": {
            "hypothesis_id": "H_20260625_001",
            "detector_draft_id": None,
            "source_look_id": "L_20260625_001",
            "sealed_rationale_id": "SR_20260625_001",
        },
        "provenance": {
            "source": "llm_lab",
            "visibility_mode": "outcome_blind",
            "model_training_cutoff": None,
            "certification_window_start": "2026-06-25",
            "contamination_class": "unknown_cutoff",
            "certification_route": route,
            "generator_type": "llm",
            "tool_enforced_outcome_blind": True,
        },
        "neutral_claim": {"sentence": "Brazil pressure may resolve differently from ETF pricing."},
        "mechanism": {
            "text": "ETF flows, commodity exposures, and options stress can combine into a measurable pricing gap.",
            "channels": ["flows", "terms_of_trade"],
        },
        "variables": ["ETF_FLOW_21D_Z"],
        "target": {
            "return_surface": "country_returns_daily",
            "horizon_days": 21,
            "direction": "higher_is_better",
            "target_type": "country_etf",
            "measurement_shape": "cross_sectional_rank_ic",
        },
        "expression": {
            "etf_ticker": "EWZ",
            "proxy_type": "country_etf",
            "liquidity_tier": "high",
            "dollar_adv_21d": 100000000.0,
            "bid_ask_spread_bps": 2.0,
            "expense_ratio_bps": 59.0,
            "tracking_or_basis_gap": None,
            "ownership_or_crowding": "watch flows",
            "flow_drag": None,
        },
        "universe": {"name": "t2_34", "min_countries": 20},
        "falsification": {"fatal_if": ["lookahead leakage"], "must_check": ["jackknife"]},
        "bull_case": "sealed only",
        "generator_rationale": "sealed only",
        "discovery_transcript": "sealed only",
        "harness_verdict": "WATCH",
        "harness_stats": {"mean_ic": 0.03, "nw_t": 2.5},
    }
