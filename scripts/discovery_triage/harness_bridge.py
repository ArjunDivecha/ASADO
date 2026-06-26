"""
=============================================================================
SCRIPT NAME: scripts/discovery_triage/harness_bridge.py
=============================================================================

DESCRIPTION:
The single boundary between a frozen claim and ASADO's existing signal harness
(merge PRD FR6 — ported from codex-kahuna, with the route gating + pre-harness
gate kept). Invariant B: dedup by (family_key, spec_hash); register only if new
(no double-charge); evaluate; return an overlay. Never writes Court fields into
the ledger.

Injectability for offline tests: the harness/ledger functions are imported as
module globals (`find_existing`, `register_hypothesis`, `evaluate_signal`,
`resolve_family`, `family_trial_count`) so tests monkeypatch THIS module.

INPUT FILES: reads the loop DB / ledgers only when actually evaluating.
OUTPUT FILES: none directly (the ledger writes are register_hypothesis's job).
VERSION: 1.0 (merge consolidation)
=============================================================================
"""
from __future__ import annotations

import re
from typing import Any

from .exceptions import ContextPolicyError, HarnessBridgeError
from .surface_loader import FORBIDDEN_SURFACES
from scripts.harness.evaluate_signal import evaluate_signal
from scripts.harness.sweep_signals import find_existing, spec_hash
from scripts.loop.family_registry import resolve_family
from scripts.loop.ledgers import family_trial_count, register_hypothesis

HARNESS_ELIGIBLE_ROUTES = {
    "post_cutoff_holdout_testable",
    "pit_preregistered",
    "standard_harness_then_triage",
    "measured_gap_claim_required",
    "measured_gap_claim",
}

FORWARD_RETURN_VARIABLE_RE = re.compile(r"(^|_)(1D|1M|3M|6M|12M)Ret($|_)|NMRet|forward", re.IGNORECASE)


def run_harness_bridge(claim: dict[str, Any]) -> dict[str, Any] | None:
    """Wire a route-eligible claim into the harness. Returns the overlay, or None
    when the claim's certification route is not harness-eligible."""
    route = (claim.get("provenance") or {}).get("certification_route")
    if route not in HARNESS_ELIGIBLE_ROUTES:
        return None

    signal_spec = _signal_spec(claim)
    _pre_harness_gate(claim, signal_spec)
    family_key = claim.get("family_key") or (claim.get("harness") or {}).get("family_key")
    if not family_key:
        raise HarnessBridgeError("family_key is required to run the harness bridge")
    mechanism = str((claim.get("mechanism") or {}).get("text") or "").strip()
    direction = _harness_direction((claim.get("target") or {}).get("direction"))
    frequency = claim.get("frequency") or (claim.get("harness") or {}).get("frequency") or "daily"
    horizons = claim.get("horizons") or (claim.get("harness") or {}).get("horizons")
    start_date = claim.get("start_date") or (claim.get("harness") or {}).get("start_date") or "2008-01-01"
    if start_date == "2008-01-01" and route == "post_cutoff_holdout_testable":
        # only the post-cutoff holdout window certifies for an LLM idea
        start_date = (claim.get("provenance") or {}).get("certification_window_start") or start_date
    universe = ((claim.get("universe") or {}).get("name")) or "t2_34"

    existing = find_existing(family_key, spec_hash(signal_spec, mechanism))
    cached = bool(existing and existing.get("verdict"))
    if cached:
        hyp_id = existing["hypothesis_id"]
        result = existing.get("verdict_json") or {"verdict": existing.get("verdict")}
        verdict = existing.get("verdict")
    else:
        hyp_id = register_hypothesis(
            archetype=claim.get("archetype", "other"),
            family_key=family_key,
            mechanism_text=mechanism,
            signal_spec=signal_spec,
            author=(claim.get("provenance") or {}).get("source", "discovery_triage"),
            primary_horizon=(claim.get("target") or {}).get("horizon_days"),
        )
        result = evaluate_signal(
            hypothesis_id=hyp_id,
            signal_spec=signal_spec,
            direction=direction,
            frequency=frequency,
            horizons=horizons,
            universe=universe,
            start_date=start_date,
        )
        verdict = result.get("verdict")

    canonical_family = resolve_family(signal_spec.get("variable", ""))
    return {
        "hypothesis_id": hyp_id,
        "harness_verdict": verdict,
        "harness_stats": _summarize_result(result),
        "harness_cached": cached,
        "family_key": family_key,
        "canonical_family": canonical_family,
        "family_trial_count": family_trial_count(canonical_family),
    }


def _signal_spec(claim: dict[str, Any]) -> dict[str, Any]:
    signal_spec = claim.get("signal_spec") or {}
    if not signal_spec:
        variables = claim.get("variables") or []
        signal_spec = {
            "table": claim.get("table"),
            "variable": variables[0] if variables else None,
            "source": claim.get("source"),
            "publication_lag_months": claim.get("publication_lag_months"),
            "hold_days": claim.get("hold_days"),
        }
    out = {k: v for k, v in signal_spec.items() if v is not None}
    if not out.get("table") or not out.get("variable"):
        raise HarnessBridgeError("signal_spec.table and signal_spec.variable are required")
    return out


def _pre_harness_gate(claim: dict[str, Any], signal_spec: dict[str, Any]) -> None:
    refs = [str(signal_spec.get("table", "")), str(claim.get("sql", ""))]
    refs.extend(str(v) for v in claim.get("variables", []))
    haystack = " ".join(refs)
    for surface in FORBIDDEN_SURFACES:
        if surface in haystack:
            raise ContextPolicyError(f"pre-harness gate rejected forbidden surface: {surface}")
    variable = str(signal_spec.get("variable", ""))
    if FORWARD_RETURN_VARIABLE_RE.search(variable):
        raise ContextPolicyError(f"pre-harness gate rejected forward-return variable: {variable}")
    resolve_family(variable)


def _harness_direction(value: str | None) -> str:
    s = str(value or "").lower()
    if s in {"higher_is_better", "long", "outperform", "up", "positive", "long_high_signal"}:
        return "higher_is_better"
    if s in {"lower_is_better", "short", "underperform", "down", "negative",
             "short_high_signal", "long_low_signal"}:
        return "lower_is_better"
    raise ValueError(f"cannot translate target direction to harness direction: {value!r}")


def _summarize_result(result: dict[str, Any]) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "verdict": result.get("verdict"),
        "result_file": result.get("result_file"),
    }
    ic = result.get("ic") or {}
    if ic:
        first = ic[sorted(ic.keys())[0]]
        stats.update({
            "mean_ic": first.get("mean_ic"),
            "nw_t": first.get("nw_t"),
            "pct_positive_years": first.get("pct_positive_years"),
        })
    dsr = result.get("deflated_sharpe_block") or {}
    if dsr:
        stats["deflated_sharpe"] = dsr.get("deflated_sharpe")
    return stats
