"""
=============================================================================
SCRIPT NAME: scripts/discovery_triage/record_look.py
=============================================================================

DESCRIPTION:
Append a Research Look (FuguPRD §11) to the append-only look ledger. A look
records what an actor (LLM/human/tool) saw before producing drafts — the
exploratory "what did we look at before deciding what to test" record. Mints an
`L_YYYYMMDD_NNN` id and validates against schemas.Look before writing.

INPUT FILES: config/discovery_triage.yaml (indirectly, via provenance normalizer).
OUTPUT FILES (append-only):
- .../journal/looks/research_looks.jsonl

VERSION: 1.0 (PR-1)
LAST UPDATED: 2026-06-25
AUTHOR: Arjun Divecha (built with Claude Code)

USAGE:
  python -m scripts.discovery_triage.record_look --actor mythos \
      --purpose find_cross_surface_contradictions --visibility-mode tool_outcome_blind \
      --model-id some-model --surface price_state_daily --surface valuation_monthly

DEPENDENCIES: pydantic>=2,<3 (via schemas)
=============================================================================
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from . import schemas
from .jsonl_store import append_with_minted_id, now_iso
from .paths import RESEARCH_LOOKS
from .provenance import normalize_visibility_mode


def record_look(
    *,
    actor: str,
    purpose: str,
    visibility_mode: str,
    model: Optional[dict[str, Any]] = None,
    surfaces_seen: Optional[list[str]] = None,
    surfaces_forbidden: Optional[list[str]] = None,
    outputs: Optional[list[str]] = None,
    contamination_class: Optional[str] = None,
    certification_route: Optional[str] = None,
    looks_path: Path = RESEARCH_LOOKS,
) -> tuple[str, dict[str, Any]]:
    """Append a look; returns (look_id, record). Normalizes visibility_mode (so a
    PRD alias is canonicalized and an unknown mode fails loudly)."""
    norm_mode = normalize_visibility_mode(visibility_mode)

    def build(look_id: str) -> dict[str, Any]:
        return {
            "look_id": look_id,
            "created_at": now_iso(),
            "actor": actor,
            "purpose": purpose,
            "visibility_mode": norm_mode,
            "model": model,
            "surfaces_seen": surfaces_seen or [],
            "surfaces_forbidden": surfaces_forbidden or [],
            "outputs": outputs or [],
            "contamination_class": contamination_class,
            "certification_route": certification_route,
        }

    return append_with_minted_id(
        looks_path, "L", "look_id", build, validate=schemas.validator_for("look")
    )


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Record a research look (FuguPRD §11).")
    ap.add_argument("--actor", required=True)
    ap.add_argument("--purpose", required=True)
    ap.add_argument("--visibility-mode", required=True)
    ap.add_argument("--model-id")
    ap.add_argument("--model-version")
    ap.add_argument("--training-cutoff")
    ap.add_argument("--surface", action="append", default=[], dest="surfaces_seen")
    ap.add_argument("--forbidden", action="append", default=[], dest="surfaces_forbidden")
    ap.add_argument("--contamination-class")
    ap.add_argument("--certification-route")
    args = ap.parse_args(argv)

    model = None
    if args.model_id:
        model = {
            "model_id": args.model_id,
            "model_version": args.model_version,
            "training_cutoff": args.training_cutoff,
        }
    try:
        look_id, record = record_look(
            actor=args.actor,
            purpose=args.purpose,
            visibility_mode=args.visibility_mode,
            model=model,
            surfaces_seen=args.surfaces_seen,
            surfaces_forbidden=args.surfaces_forbidden,
            contamination_class=args.contamination_class,
            certification_route=args.certification_route,
        )
    except Exception as exc:  # noqa: BLE001 — surface the real error loudly (FAIL IS FAIL)
        print(f"ERROR recording look: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"look_id": look_id, "record": record}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
