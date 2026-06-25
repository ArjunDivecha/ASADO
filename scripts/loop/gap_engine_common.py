#!/usr/bin/env python3
"""Shared helpers for the ASADO Price-Discovery Gap Engine."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from scripts.loop.loopdb import BASE_DIR

CONFIG_PATH = BASE_DIR / "config" / "gap_engine.yaml"
ETF_OVERRIDES_PATH = BASE_DIR / "config" / "etf_expression_overrides.yaml"
ETF_MAP_PATH = BASE_DIR / "config" / "etf_t2_map.json"


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text()) or {}


def load_gap_config() -> tuple[dict[str, Any], str]:
    cfg = load_yaml(CONFIG_PATH)
    digest = hashlib.sha256(
        json.dumps(cfg, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return cfg, digest


def load_etf_map() -> dict[str, dict[str, Any]]:
    raw = json.loads(ETF_MAP_PATH.read_text())
    return raw.get("map", raw)


def load_etf_overrides() -> dict[str, Any]:
    return load_yaml(ETF_OVERRIDES_PATH)


def stable_hash(seed: str, n: int = 16) -> str:
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:n]


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(x)))


def norm_abs_z(z: float | None, unit: float = 3.0) -> float:
    if z is None:
        return 0.0
    try:
        if z != z:
            return 0.0
        return clamp(abs(float(z)) / unit)
    except Exception:
        return 0.0


def direction_sign(direction: str) -> int:
    if direction == "long":
        return 1
    if direction == "short":
        return -1
    return 0


def liquidity_tier(dollar_adv: float | None, cfg: dict[str, Any]) -> str:
    if dollar_adv is None or dollar_adv != dollar_adv:
        return "missing"
    tiers = cfg.get("liquidity_tiers", {})
    if dollar_adv >= float(tiers.get("high_dollar_adv_min", 50_000_000)):
        return "high"
    if dollar_adv >= float(tiers.get("medium_dollar_adv_min", 10_000_000)):
        return "medium"
    if dollar_adv >= float(tiers.get("low_dollar_adv_min", 1_000_000)):
        return "low"
    return "micro"


def latest_table_date(con, table: str):
    try:
        return con.execute(f"SELECT max(date) FROM {table}").fetchone()[0]
    except Exception:
        return None


def table_exists(con, table: str) -> bool:
    return bool(
        con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = ?",
            [table],
        ).fetchone()[0]
    )


def ensure_loop_artifact_dir() -> Path:
    out = BASE_DIR / "Data" / "loop" / "gap_engine"
    out.mkdir(parents=True, exist_ok=True)
    return out


def status_novelty_score(status: str | None) -> float:
    return {
        "new": 1.0,
        "intensifying": 0.9,
        "persisting": 0.55,
        "fading": 0.30,
        "resolved": 0.0,
    }.get(status or "", 0.35)


def staleness_penalty(days_active: int | None, max_age_days: int) -> float:
    if days_active is None:
        return 0.2
    return clamp(max(0, int(days_active) - 5) / max(1, max_age_days - 5))


def score_tension(components: dict[str, float], cfg: dict[str, Any]) -> float:
    w = cfg.get("score_weights", {})
    positive = (
        w.get("severity", 0.0) * components.get("severity_score", 0.0)
        + w.get("novelty", 0.0) * components.get("novelty_score", 0.0)
        + w.get("validation_prior", 0.0) * components.get("validation_prior_score", 0.0)
        + w.get("expression", 0.0) * components.get("expression_quality_score", 0.0)
        + w.get("catalyst", 0.0) * components.get("catalyst_nearness_score", 0.0)
    )
    negative = (
        w.get("etf_drag", 0.0) * components.get("etf_drag_score", 0.0)
        + w.get("crowding", 0.0) * components.get("crowding_penalty_score", 0.0)
        + w.get("staleness", 0.0) * components.get("staleness_penalty_score", 0.0)
        + w.get("data_quality", 0.0) * components.get("data_quality_penalty_score", 0.0)
    )
    return clamp(positive - negative)


def expected_move(gap_class: str, horizon_bucket: str, severity: float, direction: str,
                  cfg: dict[str, Any]) -> tuple[float, float, str]:
    em = cfg.get("expected_move", {})
    base_map = em.get("class_base_expected_move", {})
    base = float(base_map.get(gap_class, {}).get(horizon_bucket, 0.015))
    unit = float(em.get("severity_unit_z", 2.0))
    mult = clamp(abs(float(severity)) / max(unit, 1e-9),
                 float(em.get("min_multiplier", 0.5)),
                 float(em.get("max_multiplier", 2.0)))
    move = direction_sign(direction) * base * mult
    floor = float(em.get("default_floor_abs", 0.005))
    return move, floor, "severity_mapping"


def absorption_state(realized_move: float | None, expected: float | None, floor: float,
                     cap_abs: float) -> tuple[float | None, float | None, str]:
    if expected is None or abs(expected) < floor:
        return None, None, "insufficient_signal"
    if realized_move is None or realized_move != realized_move:
        return None, None, "insufficient_signal"
    idx = max(-cap_abs, min(cap_abs, realized_move / max(abs(expected), floor)))
    if idx < -0.25:
        state = "repriced_against"
    elif idx < 0.25:
        state = "unabsorbed"
    elif idx < 0.75:
        state = "partially_absorbed"
    else:
        state = "absorbed"
    return idx, max(0.0, min(1.0, 1.0 - idx)), state
