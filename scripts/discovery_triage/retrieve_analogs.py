"""
=============================================================================
SCRIPT NAME: scripts/discovery_triage/retrieve_analogs.py
=============================================================================

DESCRIPTION:
Fixed-Metric Analog Shelf retrieval (FuguPRD §13). Given a registered metric
(config/analog_metric_registry.yaml) and an outcome-blind feature matrix, find the
K nearest historical episodes to a target episode and FREEZE the set. The retrieval
is outcome-blind by construction: the feature matrix is checked against the same
forbidden-column patterns as the surface loader, so a forward-return feature can
never drive analog selection. Once frozen, MEMBERSHIP IS IMMUTABLE — forward
outcomes are attached later (attach_analog_outcomes.py), and differencing may
explain a frozen set but may never change its membership or promote a trade.

INPUT FILES:
- config/analog_metric_registry.yaml (metric definitions + differencing policy)
OUTPUT FILES (write):
- .../journal/analog_sets/analog_sets.jsonl   (append-only index, minted AS_ ids)
- .../journal/analog_sets/<AS_ID>.yaml        (the frozen set)

VERSION: 1.0 (PR-4)
LAST UPDATED: 2026-06-25
AUTHOR: Arjun Divecha (built with Claude Code)

DEPENDENCIES: pandas, pyyaml
=============================================================================
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml

from .jsonl_store import append_with_minted_id, now_iso
from .paths import ANALOG_DIR, ANALOG_REGISTRY, ANALOG_SETS_INDEX
from .surface_loader import FORBIDDEN_COLUMN_PATTERNS, FORWARD_RETURN_VARIABLES


class AnalogError(ValueError):
    """Raised on an unknown metric or an outcome-leaking feature matrix."""


def load_metric(metric_id: str, registry_path: Path = ANALOG_REGISTRY) -> dict[str, Any]:
    cfg = yaml.safe_load(registry_path.read_text()) or {}
    for m in cfg.get("metrics", []):
        if m.get("metric_id") == metric_id:
            return m
    raise AnalogError(f"unknown metric {metric_id!r}; registry has "
                      f"{[m.get('metric_id') for m in cfg.get('metrics', [])]}")


def assert_outcome_blind_features(features_df: Any) -> None:
    """Refuse a feature matrix that contains any forward-return / outcome column."""
    bad = []
    for col in features_df.columns:
        c = str(col).strip().lower()
        if c in FORWARD_RETURN_VARIABLES or FORBIDDEN_COLUMN_PATTERNS.search(c):
            bad.append(str(col))
    if bad:
        raise AnalogError(
            f"feature matrix is NOT outcome-blind: {bad} look like forward returns/outcomes. "
            "Analog selection must never see outcomes (FuguPRD §13.3)."
        )


def retrieve_analogs(
    metric_id: str,
    target_key: Any,
    features_df: Any,
    *,
    k: int = 10,
    as_of: Optional[str] = None,
    registry_path: Path = ANALOG_REGISTRY,
    analog_dir: Path = ANALOG_DIR,
    index_path: Path = ANALOG_SETS_INDEX,
) -> tuple[str, dict[str, Any]]:
    """Retrieve + FREEZE the K nearest analogs to `target_key`. `features_df` is
    indexed by an episode key (e.g. a date string), columns are numeric features."""
    import pandas as pd

    metric = load_metric(metric_id, registry_path)
    assert_outcome_blind_features(features_df)
    if target_key not in features_df.index:
        raise AnalogError(f"target_key {target_key!r} not in the feature matrix index")

    # rank-normalize each column to [0,1], then Euclidean distance to the target.
    ranked = features_df.rank(pct=True)
    diff = ranked.sub(ranked.loc[target_key], axis=1)
    dist = (diff.pow(2).sum(axis=1)).pow(0.5)
    dist = dist.drop(index=target_key)
    nearest = dist.sort_values().head(k)
    members = [{"key": str(idx), "distance": round(float(d), 6)} for idx, d in nearest.items()]

    def build(set_id: str) -> dict[str, Any]:
        return {
            "analog_set_id": set_id,
            "metric_id": metric_id,
            "metric_distance": metric.get("distance"),
            "lookback_window_days": metric.get("lookback_window_days"),
            "target": str(target_key),
            "as_of": as_of,
            "frozen": True,
            "frozen_at": now_iso(),
            "outcome_blind": True,
            "outcomes_attached": False,
            "k": len(members),
            "members": members,
        }

    set_id, record = append_with_minted_id(index_path, "AS", "analog_set_id", build)
    analog_dir.mkdir(parents=True, exist_ok=True)
    (analog_dir / f"{set_id}.yaml").write_text(
        yaml.safe_dump(record, sort_keys=False), encoding="utf-8"
    )
    return set_id, record


def load_analog_set(set_id: str, analog_dir: Path = ANALOG_DIR) -> dict[str, Any]:
    path = analog_dir / f"{set_id}.yaml"
    if not path.exists():
        raise AnalogError(f"analog set {set_id!r} not found at {path}")
    return yaml.safe_load(path.read_text())
