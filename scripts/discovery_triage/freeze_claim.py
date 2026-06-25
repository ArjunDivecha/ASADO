"""
=============================================================================
SCRIPT NAME: scripts/discovery_triage/freeze_claim.py
=============================================================================

DESCRIPTION:
Convert a draft into an attackable, frozen claim (FuguPRD §14). PR-1 implements
the SCHEMA + GATE portion only (no harness wire — that is Phase 2B):
  1. Schema validation (schemas.Claim) — requires provenance, neutral_claim,
     mechanism, variables, target.measurement_shape, expression, falsification.
  2. Cutoff gate (Invariant D): require certification_window_start, RE-RUN the
     provenance classifier itself (never trust a caller-supplied route), stamp
     the computed route, and REJECT a freeze that claims historical certification
     while the computed route is prospective_only_* / *_unknown_cutoff — a human
     cannot launder a pre-cutoff LLM idea into historical certification.
  3. Language gate (Invariant F): reject forbidden vocabulary in the neutral
     claim / mechanism text (caught on manually-frozen claims, not just Lab output).
The bull case / generator rationale is written to a SEPARATE sealed file; only
its id goes into the claim.

INPUT FILES:
- config/model_registry.yaml (for the cutoff re-classification)
OUTPUT FILES (write):
- .../journal/claims/claims.jsonl              (append-only overlay/claim)
- .../journal/claims/<CLAIM_ID>.yaml           (per-object frozen claim)
- .../journal/sealed_rationales/<SR_ID>.yaml   (sealed bull case, separate)

VERSION: 1.0 (PR-1, schema+gates only)
LAST UPDATED: 2026-06-25
AUTHOR: Arjun Divecha (built with Claude Code)

DEPENDENCIES: pyyaml, pydantic>=2,<3
=============================================================================
"""
from __future__ import annotations

import copy
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

from . import schemas
from .classify_provenance import classify
from .jsonl_store import append_with_minted_id, write_json
from .paths import CLAIMS_DIR, CLAIMS_JSONL, MODEL_REGISTRY, SEALED_DIR

# FuguPRD §24 forbidden vocabulary (unless truly earned). Word-boundary, case-insensitive.
_FORBIDDEN_PHRASES = [
    "validated alpha", "proven signal", "promoted by mythos",
    "trade recommendation", "high-confidence opportunity", "high confidence opportunity",
    "clean historical certification",
]
_PROSPECTIVE_ROUTE = re.compile(r"prospective_only|unknown_cutoff")

# Routes for which a historical evaluate_signal run is permitted (Invariant C+D).
HARNESS_OK_ROUTES = {
    "post_cutoff_holdout_testable", "pit_preregistered",
    "standard_harness_then_triage", "measured_gap_claim_required",
}


class ClaimGateError(ValueError):
    """Raised when a claim fails the cutoff or language gate."""


def _direction(d: object) -> str:
    """Map a claim's target.direction to the harness's higher/lower_is_better."""
    s = str(d or "").lower()
    if s in ("lower_is_better", "long_low_signal", "short_high_signal", "short"):
        return "lower_is_better"
    return "higher_is_better"


def _default_hooks() -> dict[str, Any]:
    """Lazy-bind the REAL harness/ledger functions (kept out of import time so the
    schema+gate path works without the loop DB / ledger present)."""
    from scripts.harness.evaluate_signal import evaluate_signal
    from scripts.harness.sweep_signals import find_existing, spec_hash
    from scripts.loop.ledgers import register_hypothesis
    return {"spec_hash": spec_hash, "find_existing": find_existing,
            "register_hypothesis": register_hypothesis, "evaluate_signal": evaluate_signal}


def _harness_bridge(
    claim: dict[str, Any],
    route: str,
    *,
    hooks: Optional[dict[str, Any]] = None,
    opts: Optional[dict[str, Any]] = None,
) -> tuple[str, dict[str, Any]]:
    """Wire a route-eligible claim to the existing harness WITHOUT duplicating it
    (Invariant B): dedup by (family_key, spec_hash); register only if new; evaluate;
    return (hypothesis_id, overlay). Never writes Court fields into the ledger."""
    opts = opts or {}
    hooks = hooks or _default_hooks()
    spec = claim.get("signal_spec")
    family_key = claim.get("family_key")
    if not spec or not family_key:
        raise ClaimGateError("harness wire needs claim.signal_spec and claim.family_key")
    mech = str((claim.get("mechanism") or {}).get("text", ""))

    h = hooks["spec_hash"](spec, mech)
    existing = hooks["find_existing"](family_key, h)
    if existing and existing.get("verdict"):
        # cached path — do NOT re-register, do NOT re-charge the family
        hyp_id = existing["hypothesis_id"]
        result: dict[str, Any] = {"verdict": existing.get("verdict"), "reused": True,
                                  "result_file": existing.get("result_file")}
        reused = True
    else:
        hyp_id = hooks["register_hypothesis"](
            archetype=claim.get("archetype", "other"),
            family_key=family_key,
            mechanism_text=mech,
            signal_spec=spec,
            author=(claim.get("provenance") or {}).get("model_id") or "discovery_triage",
            primary_horizon=opts.get("primary_horizon"),
        )
        reused = False
        start_date = opts.get("start_date")
        if start_date is None and route == "post_cutoff_holdout_testable":
            # only the post-cutoff holdout window certifies for an LLM idea
            start_date = (claim.get("provenance") or {}).get("certification_window_start")
        ev_kwargs: dict[str, Any] = {"frequency": opts.get("frequency", "monthly"),
                                     "horizons": opts.get("horizons"),
                                     "universe": opts.get("universe", "t2_34")}
        if start_date:
            ev_kwargs["start_date"] = start_date
        result = hooks["evaluate_signal"](
            hyp_id, spec, _direction((claim.get("target") or {}).get("direction")), **ev_kwargs
        )

    overlay: dict[str, Any] = {
        "harness_verdict": result.get("verdict"),
        "harness_result_file": result.get("result_file"),
        "harness_reused": reused,
    }
    ic = result.get("ic") if isinstance(result.get("ic"), dict) else None
    if ic:
        prim = next(iter(ic.values()))
        if isinstance(prim, dict):
            overlay["harness_mean_ic"] = prim.get("mean_ic")
            overlay["harness_nw_t"] = prim.get("nw_t")
    return hyp_id, overlay


def _check_language(claim: dict[str, Any]) -> None:
    blob = " ".join([
        str(claim.get("neutral_claim", {}).get("sentence", "")),
        str(claim.get("mechanism", {}).get("text", "")),
    ]).lower()
    hits = [p for p in _FORBIDDEN_PHRASES if p in blob]
    if hits:
        raise ClaimGateError(
            f"forbidden vocabulary in claim text (FuguPRD §24): {hits}. "
            "A frozen claim emits drafts/measured language, never validation claims."
        )


def _next_sr_id(sealed_dir: Path) -> str:
    today = datetime.now().strftime("%Y%m%d")
    best = 0
    for p in sealed_dir.glob(f"SR_{today}_*.yaml"):
        try:
            best = max(best, int(p.stem.rsplit("_", 1)[1]))
        except ValueError:
            pass
    return f"SR_{today}_{best + 1:03d}"


def freeze_claim(
    claim: dict[str, Any],
    sealed_rationale: Optional[dict[str, Any]] = None,
    *,
    generator_type: str = "llm",
    historical_intent: bool = False,
    run_harness: bool = False,
    harness_hooks: Optional[dict[str, Any]] = None,
    harness_opts: Optional[dict[str, Any]] = None,
    registry_path: Path = MODEL_REGISTRY,
    claims_path: Path = CLAIMS_JSONL,
    claims_dir: Path = CLAIMS_DIR,
    sealed_dir: Path = SEALED_DIR,
) -> tuple[str, dict[str, Any]]:
    """Freeze `claim` (schema + gates). Returns (claim_id, record). The bull case,
    if any, is written to a separate sealed file and never embedded in the claim.

    `historical_intent=True` asserts the freezer wants to certify this claim on
    historical data; the cutoff gate will REJECT that unless the recomputed route
    permits it (post_cutoff_holdout_testable / pit_preregistered / measured_gap_*)."""
    claim = copy.deepcopy(claim)
    claim.setdefault("links", {})

    # --- gate: language discipline (Invariant F) ---
    _check_language(claim)

    # --- gate: cutoff / route (Invariant D) ---
    prov = claim.get("provenance") or {}
    if not prov.get("certification_window_start"):
        raise ClaimGateError(
            "provenance.certification_window_start is required to freeze a claim "
            "(the cutoff gate cannot run without it)."
        )
    route_info = classify(
        generator_type=generator_type,
        visibility_mode=prov.get("visibility_mode", ""),
        model_id=prov.get("model_id"),
        certification_window_start=prov.get("certification_window_start"),
        tool_enforced_outcome_blind=bool(prov.get("tool_enforced_outcome_blind", False)),
        legacy_tier=prov.get("legacy_tier"),
        registry_path=registry_path,
    )
    computed_route = str(route_info.get("certification_route"))
    # The classifier decides — not the caller. Stamp the computed route.
    prov["certification_route"] = computed_route
    prov.setdefault("model_training_cutoff", route_info.get("model_training_cutoff"))
    claim["provenance"] = prov
    if historical_intent and _PROSPECTIVE_ROUTE.search(computed_route):
        raise ClaimGateError(
            f"historical certification refused: computed route is {computed_route!r}. "
            "An LLM/pre-cutoff/unknown-cutoff claim is prospective-only; it cannot be "
            "certified on historical data (FuguPRD §1.4, Invariant D)."
        )

    # --- harness wire (Invariant B; Phase 2B) — only for route-eligible claims ---
    if run_harness and computed_route in HARNESS_OK_ROUTES:
        hyp_id, overlay = _harness_bridge(
            claim, computed_route, hooks=harness_hooks, opts=harness_opts
        )
        claim["links"]["hypothesis_id"] = hyp_id
        for k, v in overlay.items():
            if v is not None:
                claim[k] = v

    # --- sealed rationale (bull case) -> separate file, only its id in the claim ---
    if sealed_rationale is not None:
        sealed_dir.mkdir(parents=True, exist_ok=True)
        sr_id = _next_sr_id(sealed_dir)
        sealed_obj = {"sealed_rationale_id": sr_id, **sealed_rationale}
        (sealed_dir / f"{sr_id}.yaml").write_text(
            yaml.safe_dump(sealed_obj, sort_keys=False), encoding="utf-8"
        )
        claim["links"]["sealed_rationale_id"] = sr_id

    # --- mint claim id + append (schema-validated inside the lock) ---
    def build(claim_id: str) -> dict[str, Any]:
        rec = copy.deepcopy(claim)
        rec["claim_id"] = claim_id
        return rec

    claim_id, record = append_with_minted_id(
        claims_path, "C", "claim_id", build, validate=schemas.validator_for("claim")
    )
    claims_dir.mkdir(parents=True, exist_ok=True)
    write_json(claims_dir / f"{claim_id}.yaml", record)
    return claim_id, record
