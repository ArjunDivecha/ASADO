"""
=============================================================================
SCRIPT NAME: scripts/discovery_triage/model_registry.py
=============================================================================

DESCRIPTION:
Thin wrapper over config/model_registry.yaml (merge PRD FR7). A missing/unknown
training cutoff leaves `training_cutoff` None, which the provenance classifier
routes to prospective_only_unknown_cutoff. Cutoffs are NEVER guessed here.

INPUT FILES:
- config/model_registry.yaml
OUTPUT FILES: none.
VERSION: 1.0 (merge consolidation; ported from codex-kahuna)
=============================================================================
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .paths import MODEL_REGISTRY_PATH


def load_model_registry(path: Path = MODEL_REGISTRY_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "default_model": None, "models": {}}
    return yaml.safe_load(path.read_text()) or {"version": 1, "default_model": None, "models": {}}


def model_metadata(model_id: str | None, registry: dict[str, Any] | None = None) -> dict[str, Any]:
    reg = registry or load_model_registry()
    resolved_id = model_id or reg.get("default_model")
    model = (reg.get("models") or {}).get(resolved_id or "", {})
    return {
        "model_id": resolved_id,
        "model_version": model.get("model_version"),
        "training_cutoff": model.get("training_cutoff"),
        "tool_context_cutoff": model.get("tool_context_cutoff"),
    }


def model_cutoff(model_id: str | None, registry: dict[str, Any] | None = None) -> str | None:
    """Convenience: the training_cutoff for a model (None => unknown-cutoff route)."""
    return model_metadata(model_id, registry).get("training_cutoff")
