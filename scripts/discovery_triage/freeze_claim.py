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
from .jsonl_store import append_with_minted_id, atomic_write_text, write_json
from .paths import CLAIMS_DIR, CLAIMS_JSONL, MODEL_REGISTRY, SEALED_DIR

# FuguPRD §24 forbidden vocabulary (unless truly earned). Word-boundary, case-insensitive.
_FORBIDDEN_PHRASES = [
    "validated alpha", "proven signal", "promoted by mythos",
    "trade recommendation", "high-confidence opportunity", "high confidence opportunity",
    "clean historical certification",
]
_PROSPECTIVE_ROUTE = re.compile(r"prospective_only|unknown_cutoff")


class ClaimGateError(ValueError):
    """Raised when a claim fails the cutoff or language gate."""


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
    # C2 (red-team 2026-06-26): bind the EFFECTIVE generator to the claim's real
    # model origin. If a model produced/touched this claim (model_id present), it is
    # LLM-contaminated regardless of what the caller declares — a caller cannot
    # relabel an LLM idea as `harness` to skip the model-cutoff PIT boundary.
    effective_generator = "llm" if prov.get("model_id") else generator_type
    route_info = classify(
        generator_type=effective_generator,
        visibility_mode=prov.get("visibility_mode", ""),
        model_id=prov.get("model_id"),
        certification_window_start=prov.get("certification_window_start"),
        tool_enforced_outcome_blind=bool(prov.get("tool_enforced_outcome_blind", False)),
        legacy_tier=prov.get("legacy_tier"),
        # A pit_preregistered declaration earns historical cert only with a verifiable
        # proof timestamp predating the window; otherwise the cutoff still applies.
        pit_proof_ts=prov.get("pit_proof_ts"),
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

    # --- harness wire (Invariant B) — delegated to the harness_bridge module (FR6).
    # run_harness_bridge() does its own route gating (returns None if ineligible).
    if run_harness:
        from . import harness_bridge
        overlay = harness_bridge.run_harness_bridge(claim)
        if overlay:
            claim["links"]["hypothesis_id"] = overlay["hypothesis_id"]
            for k in ("harness_verdict", "harness_stats", "harness_cached",
                      "family_trial_count", "canonical_family"):
                if overlay.get(k) is not None:
                    claim[k] = overlay[k]

    # --- sealed rationale (bull case) -> separate file, only its id in the claim ---
    if sealed_rationale is not None:
        sealed_dir.mkdir(parents=True, exist_ok=True)
        sr_id = _next_sr_id(sealed_dir)
        sealed_obj = {"sealed_rationale_id": sr_id, **sealed_rationale}
        atomic_write_text(sealed_dir / f"{sr_id}.yaml", yaml.safe_dump(sealed_obj, sort_keys=False))
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
