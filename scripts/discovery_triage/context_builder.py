from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .exceptions import ContextPolicyError  # re-exported for back-compat
from .paths import DISCOVERY_CONFIG
from .provenance import normalize_visibility_mode

__all__ = ["ContextPolicyError", "ContextRequest", "assert_outcome_blind", "build_context_manifest"]


@dataclass
class ContextRequest:
    visibility_mode: str
    requested_surfaces: list[str]
    as_of_date: str | None = None
    model_id: str | None = None
    model_training_cutoff: str | None = None
    purpose: str = "discovery"
    extra_metadata: dict[str, Any] = field(default_factory=dict)


def _load_forbidden(config_path: Path = DISCOVERY_CONFIG) -> list[str]:
    cfg = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
    return list(cfg.get("forbidden_context_surfaces", []))


def _matches_forbidden(surface: str, forbidden: str) -> bool:
    s = surface.lower()
    f = forbidden.lower()
    if "." in f:
        return s == f or s.endswith("." + f.split(".", 1)[1]) or f in s
    if s == f or f in s:
        return True
    # return/PnL aliases: catch common derived outcome leaks without banning
    # safe state words like price_state_daily.
    if f in {"forward_returns", "future_returns", "realized_forward_outcomes", "pnl"}:
        return bool(re.search(r"(^|[_\.])(forward|future|pnl|profit|realized_return|outcome)([_\.]|$)", s))
    return False


def assert_outcome_blind(requested_surfaces: list[str], *, config_path: Path = DISCOVERY_CONFIG) -> None:
    forbidden = _load_forbidden(config_path)
    leaks: list[tuple[str, str]] = []
    for surface in requested_surfaces:
        for f in forbidden:
            if _matches_forbidden(surface, f):
                leaks.append((surface, f))
    if leaks:
        detail = "; ".join(f"{s} matched forbidden {f}" for s, f in leaks)
        raise ContextPolicyError(f"Discovery context is not outcome-blind: {detail}")


def build_context_manifest(req: ContextRequest) -> dict[str, Any]:
    """Return a manifest for the tool-enforced context.

    V1 does not ship raw data to an LLM. It creates a manifest that proves which
    surfaces were allowed/rejected. Outcome-blind mode is enforced here, not by
    prompt instruction. The visibility mode is normalized through the SAME
    normalizer used by provenance, so a PRD alias (`tool_outcome_blind`) cannot
    skip the enforcement below by failing the literal `in {...}` check.
    """
    mode = normalize_visibility_mode(req.visibility_mode)
    blind = mode in {"outcome_blind", "frozen_window"}
    if blind:
        assert_outcome_blind(req.requested_surfaces)
    return {
        "visibility_mode": mode,
        "as_of_date": req.as_of_date,
        "model_id": req.model_id,
        "model_training_cutoff": req.model_training_cutoff,
        "purpose": req.purpose,
        "allowed_surfaces": list(req.requested_surfaces),
        "forbidden_surfaces_enforced": _load_forbidden(),
        "tool_enforced_outcome_blind": blind,
        "extra_metadata": req.extra_metadata,
    }
