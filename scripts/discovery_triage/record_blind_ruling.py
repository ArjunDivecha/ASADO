"""
=============================================================================
SCRIPT NAME: scripts/discovery_triage/record_blind_ruling.py
=============================================================================

DESCRIPTION:
Record a blind human ruling (FuguPRD §16). The protocol is enforced by ORDER:
  1. `record_blind_ruling(...)` writes the PRELIMINARY ruling (made on the blind
     packet, before the bull case is unsealed). `unseal` is null at this point.
  2. `record_unseal(...)` appends a second event (same ruling_id) after the bull
     case is unsealed, recording `post_unseal_decision` and the computed
     `ruling_changed_after_unseal` flag.
Records are append-only; consumers fold by ruling_id taking the latest event.

INPUT FILES: none.
OUTPUT FILES (append-only):
- .../journal/blind_rulings/blind_rulings.jsonl

VERSION: 1.0 (PR-2A)
LAST UPDATED: 2026-06-25
AUTHOR: Arjun Divecha (built with Claude Code)

DEPENDENCIES: pydantic (via schemas)
=============================================================================
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from . import schemas
from .jsonl_store import append_jsonl, append_with_minted_id, now_iso, read_jsonl
from .paths import BLIND_RULINGS


def record_blind_ruling(
    *,
    claim_id: str,
    judge: str,
    decision: str,
    rationale: str,
    rulings_path: Path = BLIND_RULINGS,
) -> tuple[str, dict[str, Any]]:
    """Write the preliminary (pre-unseal) blind ruling; returns (ruling_id, record)."""
    def build(ruling_id: str) -> dict[str, Any]:
        return {
            "ruling_id": ruling_id,
            "claim_id": claim_id,
            "judge": judge,
            "blind_ruling": {"decision": decision, "timestamp": now_iso(), "rationale": rationale},
            "unseal": None,
        }

    return append_with_minted_id(
        rulings_path, "R", "ruling_id", build, validate=schemas.validator_for("blind_ruling")
    )


def record_unseal(
    *,
    ruling_id: str,
    post_unseal_decision: str,
    rulings_path: Path = BLIND_RULINGS,
) -> dict[str, Any]:
    """Append the post-unseal event for an existing ruling, computing
    `ruling_changed_after_unseal` against the preliminary decision."""
    prelim = None
    for rec in read_jsonl(rulings_path):
        if rec.get("ruling_id") == ruling_id and (rec.get("blind_ruling") or {}).get("decision"):
            prelim = rec
    if prelim is None:
        raise ValueError(f"no preliminary ruling found for {ruling_id!r}")
    prelim_decision = prelim["blind_ruling"]["decision"]
    record = {
        "ruling_id": ruling_id,
        "claim_id": prelim["claim_id"],
        "judge": prelim["judge"],
        "blind_ruling": prelim["blind_ruling"],
        "unseal": {
            "sealed_rationale_unsealed_at": now_iso(),
            "post_unseal_decision": post_unseal_decision,
            "ruling_changed_after_unseal": post_unseal_decision != prelim_decision,
        },
    }
    return append_jsonl(rulings_path, record, validate=schemas.validator_for("blind_ruling"))


def latest_ruling(ruling_id: str, rulings_path: Path = BLIND_RULINGS) -> Optional[dict[str, Any]]:
    """Fold: return the latest event for a ruling_id (post-unseal if present)."""
    found = None
    for rec in read_jsonl(rulings_path):
        if rec.get("ruling_id") == ruling_id:
            found = rec
    return found
