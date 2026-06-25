"""
=============================================================================
SCRIPT NAME: scripts/discovery_triage/route_claim.py
=============================================================================

DESCRIPTION:
Route a frozen claim to forward tracking (FuguPRD §17/§18). EVERY claim is
tracked forward when mechanically measurable:
  - survivors / quarantined / prospective-only / holdout-testable  -> INCUBATOR
  - killed / rejected                                              -> GRAVEYARD (control arm)
The entry records carry `measurement_shape` + `direction` (mirrored on both arms
per the Sakana review) so `forward_track.py` (Phase 2B) can score readouts without
re-reading the original claim. This module writes the ENTRY record only; readouts
are appended later by the forward-track engine.

INPUT FILES: none.
OUTPUT FILES (append-only):
- .../journal/prospective_queue/prospective_queue.jsonl       (incubator_entry)
- .../journal/graveyard/graveyard_forward_tracking.jsonl      (graveyard_entry)

VERSION: 1.0 (PR-2A)
LAST UPDATED: 2026-06-25
AUTHOR: Arjun Divecha (built with Claude Code)

DEPENDENCIES: pydantic (via schemas)
=============================================================================
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from . import schemas
from .jsonl_store import append_jsonl
from .paths import GRAVEYARD_TRACKING, PROSPECTIVE_QUEUE

GRAVEYARD_DECISIONS = {"killed_fatal_leakage", "rejected_for_now", "rejected"}
EXPECTED_READOUTS = ["21d", "63d", "252d"]
OBSERVATIONS_REQUIRED = 252


def _target_country(claim: dict[str, Any]) -> Any:
    return (
        claim.get("target_country")
        or (claim.get("target") or {}).get("target_country")
        or (claim.get("universe") or {}).get("target_country")
    )


def route_claim(
    claim: dict[str, Any],
    decision: str,
    *,
    reason: str | None = None,
    prospective_path: Path = PROSPECTIVE_QUEUE,
    graveyard_path: Path = GRAVEYARD_TRACKING,
) -> tuple[str, dict[str, Any]]:
    """Route `claim` by `decision`; returns (arm, record). arm in {incubator, graveyard}."""
    target = claim.get("target") or {}
    measurement_shape = target.get("measurement_shape")
    direction = target.get("direction")
    return_surface = target.get("return_surface")
    if not measurement_shape or not return_surface:
        raise ValueError(
            "claim.target needs measurement_shape and return_surface to be forward-tracked"
        )
    claim_id = claim.get("claim_id", "UNKNOWN")
    hyp_id = (claim.get("links") or {}).get("hypothesis_id")
    start = date.today().isoformat()

    if decision in GRAVEYARD_DECISIONS:
        record = {
            "record_kind": "graveyard_entry",
            "claim_id": claim_id,
            "terminal_or_quarantine_status": decision,
            "forward_tracking_enabled": True,
            "start_date": start,
            "reason_for_tracking": reason or "false_negative_control_arm",
            "expected_readouts": EXPECTED_READOUTS,
            "return_surface": return_surface,
            "target_country": _target_country(claim),
            "measurement_shape": measurement_shape,
            "direction": direction,
            "hypothesis_id": hyp_id,
        }
        append_jsonl(graveyard_path, record, validate=schemas.validator_for("graveyard_entry"))
        return "graveyard", record

    record = {
        "record_kind": "incubator_entry",
        "claim_id": claim_id,
        "status": decision,
        "start_date": start,
        "observations_required": OBSERVATIONS_REQUIRED,
        "observations_so_far": 0,
        "in_sample_certification": "forbidden",
        "expected_readouts": EXPECTED_READOUTS,
        "return_surface": return_surface,
        "target_country": _target_country(claim),
        "measurement_shape": measurement_shape,
        "direction": direction,
        "reason": reason,
        "hypothesis_id": hyp_id,
    }
    append_jsonl(prospective_path, record, validate=schemas.validator_for("incubator_entry"))
    return "incubator", record
