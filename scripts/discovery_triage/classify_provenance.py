"""
=============================================================================
SCRIPT NAME: scripts/discovery_triage/classify_provenance.py
=============================================================================

DESCRIPTION:
Thin CLI/function wrapper over `provenance.classify_provenance`. It looks up a
model's training cutoff from config/model_registry.yaml (the real PIT boundary
for LLM-generated ideas), builds a ProvenanceInput, and returns the certification
route. The heavy logic lives in provenance.py (the 11-branch router); this adds
only model-registry lookup and CLI plumbing. Visibility-mode aliases are
normalized inside the classifier.

INPUT FILES:
- config/model_registry.yaml  (model_id -> training_cutoff)
OUTPUT FILES: none (prints JSON to stdout).

VERSION: 1.0 (PR-1)
LAST UPDATED: 2026-06-25
AUTHOR: Arjun Divecha (built with Claude Code)

USAGE:
  python -m scripts.discovery_triage.classify_provenance --generator llm \
      --visibility-mode tool_outcome_blind --model-id verified_model_id \
      --certification-window-start 2027-02-01 --tool-enforced

DEPENDENCIES: pyyaml
=============================================================================
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from .model_registry import load_model_registry, model_metadata
from .paths import MODEL_REGISTRY
from .provenance import ProvenanceInput, classify_provenance


def model_cutoff(model_id: Optional[str], registry_path: Path = MODEL_REGISTRY) -> Optional[str]:
    """Return the training_cutoff for model_id via the model_registry wrapper (FR7), or
    None. Missing model id / registry / cutoff all return None, routing to
    prospective_only_unknown_cutoff. The cutoff is NEVER guessed here."""
    if not model_id:
        return None
    registry = load_model_registry(registry_path)
    return model_metadata(model_id, registry).get("training_cutoff")


def classify(
    *,
    generator_type: str,
    visibility_mode: str,
    model_id: Optional[str] = None,
    certification_window_start: Optional[str] = None,
    tool_enforced_outcome_blind: bool = False,
    legacy_tier: Optional[str] = None,
    registry_path: Path = MODEL_REGISTRY,
) -> dict[str, Any]:
    cutoff = model_cutoff(model_id, registry_path)
    inp = ProvenanceInput(
        generator_type=generator_type,  # type: ignore[arg-type]
        visibility_mode=visibility_mode,
        model_training_cutoff=cutoff,
        certification_window_start=certification_window_start,
        tool_enforced_outcome_blind=tool_enforced_outcome_blind,
        legacy_tier=legacy_tier,
    )
    result = dict(classify_provenance(inp))
    result["model_id"] = model_id
    result["model_training_cutoff"] = cutoff
    return result


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Classify provenance / certification route.")
    ap.add_argument("--generator", required=True,
                    choices=["llm", "human", "deterministic", "harness"])
    ap.add_argument("--visibility-mode", required=True)
    ap.add_argument("--model-id")
    ap.add_argument("--certification-window-start")
    ap.add_argument("--tool-enforced", action="store_true")
    ap.add_argument("--legacy-tier")
    args = ap.parse_args(argv)
    try:
        result = classify(
            generator_type=args.generator,
            visibility_mode=args.visibility_mode,
            model_id=args.model_id,
            certification_window_start=args.certification_window_start,
            tool_enforced_outcome_blind=args.tool_enforced,
            legacy_tier=args.legacy_tier,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR classifying provenance: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
