"""
=============================================================================
SCRIPT NAME: scripts/discovery_triage/make_detector_draft.py
=============================================================================

DESCRIPTION:
Write a detector_family_draft (FuguPRD §10.2) to the append-only drafts ledger
and a per-object YAML. Enforces that the draft links to a `source_look_id` that
actually exists in the look ledger (FuguPRD §11.4 — no draft without a recorded
look) and that the mandatory falsification (§10.5) and mythos_self_falsification
(§10.6) blocks are present (enforced by schemas.DetectorDraft).

INPUT FILES (read):
- .../journal/looks/research_looks.jsonl   (to verify source_look_id exists)
OUTPUT FILES (write):
- .../journal/drafts/detector_drafts.jsonl (append-only)
- .../journal/drafts/<DRAFT_ID>.yaml       (per-object frozen artifact)

VERSION: 1.0 (PR-1)
LAST UPDATED: 2026-06-25
AUTHOR: Arjun Divecha (built with Claude Code)

DEPENDENCIES: pyyaml, pydantic>=2,<3
=============================================================================
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml

from . import schemas
from .jsonl_store import append_with_minted_id, atomic_write_text, read_jsonl
from .paths import DETECTOR_DRAFTS, DRAFTS_DIR, RESEARCH_LOOKS


class LookNotFoundError(ValueError):
    """Raised when a draft references a source_look_id with no matching look."""


def make_detector_draft(
    *,
    source_look_id: str,
    family_name: str,
    members: list[str],
    falsification: dict[str, Any],
    mythos_self_falsification: dict[str, Any],
    certification_route: Optional[str] = None,
    epistemic_status: Optional[list[str]] = None,
    looks_path: Path = RESEARCH_LOOKS,
    drafts_path: Path = DETECTOR_DRAFTS,
    drafts_dir: Path = DRAFTS_DIR,
) -> tuple[str, dict[str, Any]]:
    """Persist a detector draft; returns (draft_id, record). Refuses to write if
    `source_look_id` is not found in the look ledger."""
    known = {str(r.get("look_id")) for r in read_jsonl(looks_path)}
    if source_look_id not in known:
        raise LookNotFoundError(
            f"source_look_id {source_look_id!r} not found in {looks_path}; "
            "a draft must link to a recorded look (FuguPRD §11.4)."
        )

    def build(draft_id: str) -> dict[str, Any]:
        return {
            "object_type": "detector_family_draft",
            "draft_id": draft_id,
            "family_name": family_name,
            "members": members,
            "source_look_id": source_look_id,
            "certification_route": certification_route,
            "epistemic_status": epistemic_status or ["unvalidated"],
            "falsification": falsification,
            "mythos_self_falsification": mythos_self_falsification,
        }

    draft_id, record = append_with_minted_id(
        drafts_path, "DRAFT", "draft_id", build,
        validate=schemas.validator_for("detector_draft"),
    )
    drafts_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(drafts_dir / f"{draft_id}.yaml", yaml.safe_dump(record, sort_keys=False))
    return draft_id, record
