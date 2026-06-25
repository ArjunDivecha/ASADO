"""
=============================================================================
SCRIPT NAME: scripts/discovery_triage/build_blind_packet.py
=============================================================================

DESCRIPTION:
Build the blind packet a human judge rules on BEFORE the generator rationale /
bull case is unsealed (FuguPRD §16). The packet is assembled from a strict
WHITELIST of allowed inputs (§16.2), so a forbidden input (§16.3 — generator
rationale, bull case, excitement score, trade recommendation, discovery
transcript) can never appear. The packet builder NEVER reads `SR_*.yaml`.

ROUTE-AWARE HARNESS STATS (Sakana review): historical IC / Sharpe / verdict are
included ONLY for routes that may certify on history (post_cutoff_holdout_testable,
pit_preregistered, deterministic/harness-clean). For prospective_only_* /
legacy_unknown / retrospective routes, the pre-ruling packet EXCLUDES historical
stats even if someone ran them descriptively.

INPUT FILES: none (operates on a claim dict + triage_result dict in memory).
OUTPUT FILES: none (returns the packet dict; the caller may persist/print it).

VERSION: 1.0 (PR-2A)
LAST UPDATED: 2026-06-25
AUTHOR: Arjun Divecha (built with Claude Code)
=============================================================================
"""
from __future__ import annotations

from typing import Any, Optional

# Routes for which pre-ruling historical harness stats are permissible.
_HISTORICAL_OK_ROUTES = {
    "post_cutoff_holdout_testable",
    "pit_preregistered",
    "standard_harness_then_triage",
    "measured_gap_claim_required",
}
# Inputs that must never be in a blind packet (§16.3).
FORBIDDEN_PACKET_KEYS = (
    "bull_case", "generator_rationale", "rationale", "excitement_score",
    "trade_recommendation", "discovery_transcript", "sealed_rationale",
)


def _route_allows_history(route: str) -> bool:
    r = str(route or "")
    if r.startswith("prospective_only") or "unknown_cutoff" in r:
        return False
    if r == "legacy_grandfathered_forward_tracking":
        return False
    return r in _HISTORICAL_OK_ROUTES


def build_blind_packet(
    claim: dict[str, Any],
    triage_result: dict[str, Any],
    *,
    harness_stats: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Return the blind packet (allowed inputs only). Whitelisted construction
    guarantees no §16.3 input leaks; harness stats are gated by certification route."""
    prov = claim.get("provenance") or {}
    route = str(prov.get("certification_route", ""))

    packet: dict[str, Any] = {
        "claim_id": claim.get("claim_id"),
        "neutral_claim": claim.get("neutral_claim"),
        "provenance": {
            k: prov.get(k) for k in (
                "source", "visibility_mode", "certification_route",
                "model_training_cutoff", "certification_window_start", "contamination_class",
            )
        },
        "target": claim.get("target"),
        "expression": claim.get("expression"),
        "triage": triage_result,
        "power_budget": (triage_result or {}).get("power_budget"),
    }

    if harness_stats is not None and _route_allows_history(route):
        packet["harness_stats"] = harness_stats
    elif harness_stats is not None:
        packet["harness_stats_excluded"] = (
            f"route {route!r} is prospective/legacy/retrospective — pre-ruling "
            "packet excludes historical IC/Sharpe/verdict (Sakana review)."
        )

    # Defense in depth: strip any forbidden key that somehow rode along.
    for bad in FORBIDDEN_PACKET_KEYS:
        packet.pop(bad, None)
    return packet
