"""
=============================================================================
SCRIPT NAME: scripts/discovery_triage/attach_analog_outcomes.py
=============================================================================

DESCRIPTION:
Attach forward outcomes to a FROZEN analog set, and run constrained differencing
(FuguPRD §13.4–§13.6). The two hard rules:
  1. Outcomes are attached ONLY after the set is frozen, and attaching them NEVER
     changes membership (the member keys are asserted identical before/after).
     Re-attaching is refused — a frozen set's outcomes are written once.
  2. Differencing may EXPLAIN a frozen set along allowed difference axes
     (config/analog_metric_registry.yaml differencing_policy) but may NOT change
     membership and may NOT promote a trade — its only outputs are notes/caveats.

INPUT FILES:
- config/analog_metric_registry.yaml (differencing_policy: allowed axes/outputs)
- .../journal/analog_sets/<AS_ID>.yaml (the frozen set)
OUTPUT FILES (write):
- .../journal/analog_sets/<AS_ID>.yaml (rewritten with member forward_outcome + flag)

VERSION: 1.0 (PR-4)
LAST UPDATED: 2026-06-25
AUTHOR: Arjun Divecha (built with Claude Code)

DEPENDENCIES: pandas, pyyaml
=============================================================================
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .jsonl_store import now_iso
from .paths import ANALOG_DIR, ANALOG_REGISTRY
from .retrieve_analogs import AnalogError, load_analog_set


def _forward_outcome(returns_df: Any, episode_date: str, horizon: int) -> float | None:
    """Cumulative return over `horizon` observations AFTER episode_date. Returns None
    (immature) if fewer than `horizon` observations exist after the episode."""
    import pandas as pd

    df = returns_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    fwd = df[df["date"] > pd.to_datetime(episode_date)].sort_values("date").head(horizon)
    if len(fwd) < horizon:
        return None
    return round(float((1.0 + fwd["ret"]).prod() - 1.0), 6)


def attach_analog_outcomes(
    set_id: str,
    returns_df: Any,
    horizon: int,
    *,
    analog_dir: Path = ANALOG_DIR,
) -> dict[str, Any]:
    """Attach forward outcomes to a frozen set WITHOUT changing membership."""
    record = load_analog_set(set_id, analog_dir)
    if record.get("outcomes_attached"):
        raise AnalogError(
            f"{set_id} already has outcomes attached — a frozen set's outcomes are "
            "written once and are immutable (FuguPRD §13.4)."
        )
    members_before = [m["key"] for m in record.get("members", [])]
    for m in record.get("members", []):
        m["forward_outcome"] = _forward_outcome(returns_df, m["key"], horizon)
    members_after = [m["key"] for m in record.get("members", [])]
    if members_before != members_after:
        raise AnalogError("attaching outcomes must not change analog membership")
    record["outcomes_attached"] = True
    record["outcomes_horizon"] = horizon
    record["outcomes_attached_at"] = now_iso()
    (analog_dir / f"{set_id}.yaml").write_text(
        yaml.safe_dump(record, sort_keys=False), encoding="utf-8"
    )
    return record


def _differencing_policy(registry_path: Path = ANALOG_REGISTRY) -> dict[str, Any]:
    cfg = yaml.safe_load(registry_path.read_text()) or {}
    return cfg.get("differencing_policy", {}) or {}


def difference_analogs(
    analog_set: dict[str, Any],
    axes: list[str],
    notes: dict[str, str] | None = None,
    *,
    registry_path: Path = ANALOG_REGISTRY,
) -> list[dict[str, Any]]:
    """Explain a frozen set along ALLOWED difference axes. Returns analog_note objects.
    Raises on a disallowed axis. NEVER changes membership and NEVER promotes a trade."""
    policy = _differencing_policy(registry_path)
    allowed_axes = set(policy.get("allowed_difference_axes", []))
    if policy.get("may_change_analog_membership", False):
        raise AnalogError("registry policy must forbid changing analog membership")
    bad = [a for a in axes if a not in allowed_axes]
    if bad:
        raise AnalogError(f"difference axes {bad} are not in the allowed set {sorted(allowed_axes)}")
    notes = notes or {}
    out = []
    for a in axes:
        out.append({
            "output_type": "analog_note",   # never a trade (allowed_outputs only)
            "analog_set_id": analog_set.get("analog_set_id"),
            "axis": a,
            "note": notes.get(a, f"differs from the frozen set along {a}"),
        })
    return out
