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
from .build_blind_packet import build_blind_packet
from .jsonl_store import append_jsonl, append_with_minted_id, now_iso, read_jsonl
from .paths import BLIND_RULINGS

# Invariant F (FuguPRD §24): a ruling emits a verdict, never a validation/promotion claim.
_FORBIDDEN_RULING_LANGUAGE = (
    "validated alpha", "proven signal", "promoted by mythos", "promote",
    "trade recommendation", "high-confidence opportunity", "high confidence opportunity",
    "clean historical certification",
)


class BlindRulingError(ValueError):
    """Raised when a ruling uses forbidden language or violates the unseal protocol."""


def _check_ruling_language(*texts: Any) -> None:
    blob = " ".join(str(t or "") for t in texts).lower()
    hits = [p for p in _FORBIDDEN_RULING_LANGUAGE if p in blob]
    if hits:
        raise BlindRulingError(
            f"forbidden vocabulary in blind ruling (FuguPRD §24): {hits}. "
            "A ruling records a verdict, never a validation/promotion claim."
        )


def rule_on_blind_packet(
    *,
    claim: dict[str, Any],
    triage_result: dict[str, Any],
    judge: str,
    decide: Any,
    harness_stats: Optional[dict[str, Any]] = None,
    rulings_path: Path = BLIND_RULINGS,
) -> tuple[str, dict[str, Any]]:
    """H3 (red-team 2026-06-26): the ENFORCED blind protocol. Builds the blind packet
    and passes ONLY the packet to `decide` (a callable returning (decision, rationale)),
    so the generator rationale / bull case can never reach the judge, then records the
    preliminary ruling. This is the wiring the standalone functions previously lacked."""
    packet = build_blind_packet(claim, triage_result, harness_stats=harness_stats)
    decision, rationale = decide(packet)
    return record_blind_ruling(
        claim_id=packet.get("claim_id"), judge=judge,
        decision=decision, rationale=rationale, rulings_path=rulings_path,
    )


def record_blind_ruling(
    *,
    claim_id: str,
    judge: str,
    decision: str,
    rationale: str,
    rulings_path: Path = BLIND_RULINGS,
) -> tuple[str, dict[str, Any]]:
    """Write the preliminary (pre-unseal) blind ruling; returns (ruling_id, record)."""
    _check_ruling_language(decision, rationale)  # M2: Invariant-F language gate

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
    _check_ruling_language(post_unseal_decision)  # M2: Invariant-F language gate
    prelim = None
    for rec in read_jsonl(rulings_path):
        if rec.get("ruling_id") != ruling_id:
            continue
        # M2: one unseal per ruling — a second unseal would silently fold to the
        # newest, masking a flip-flop. Refuse it.
        if rec.get("unseal"):
            raise BlindRulingError(
                f"ruling {ruling_id!r} has already been unsealed; a second unseal is refused "
                "(it would mask the recorded post-unseal decision)."
            )
        if (rec.get("blind_ruling") or {}).get("decision"):
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
