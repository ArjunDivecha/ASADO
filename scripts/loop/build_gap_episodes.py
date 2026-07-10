#!/usr/bin/env python3
"""
Build ASADO Price-Discovery Gap Engine episodes, marks, expressions, and holdout rows.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.loop.gap_engine_common import (  # noqa: E402
    absorption_state,
    clamp,
    direction_sign,
    ensure_loop_artifact_dir,
    expected_move,
    json_dumps,
    liquidity_tier,
    load_etf_map,
    load_etf_overrides,
    load_gap_config,
    norm_abs_z,
    score_tension,
    stable_hash,
    staleness_penalty,
    status_novelty_score,
    table_exists,
    tension_current,
)
from scripts.loop.loopdb import T2_UNIVERSE, loop_connection  # noqa: E402


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} [gap-engine] {msg}", flush=True)


EPISODE_COLUMNS = [
    "gap_id", "episode_key", "episode_instance", "gap_id_seed", "opened_at",
    "first_seen_date", "as_of_date_open", "entity", "direction", "gap_class",
    "horizon_days", "horizon_bucket", "source_dislocation_ids", "related_gap_ids",
    "world_state_json", "price_state_json", "mechanism_template_id", "mechanism_text",
    "validation_prior", "scoring_config_version", "scoring_config_hash",
    "preferred_ticker", "proxy_type", "expression_quality_at_open",
    "liquidity_tier_at_open", "etf_ownership_drag_bps", "currency_basis",
    "basis_gap_z_at_open", "crowding_score_at_open", "severity_score_at_open",
    "novelty_score_at_open", "validation_prior_score_at_open",
    "expression_quality_score_at_open", "catalyst_nearness_score_at_open",
    "etf_drag_score_at_open", "crowding_penalty_score_at_open",
    "staleness_penalty_score_at_open", "data_quality_penalty_score_at_open",
    "tension_score_at_open", "tension_components_json",
    "expected_absorption_path_json", "invalidation_rule", "research_only",
    "paper_candidate", "status", "closed_at", "close_reason",
]


def ensure_schema(con) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS gap_episodes (
            gap_id VARCHAR, episode_key VARCHAR, episode_instance INTEGER,
            gap_id_seed VARCHAR, opened_at TIMESTAMP, first_seen_date DATE,
            as_of_date_open DATE, entity VARCHAR, direction VARCHAR,
            gap_class VARCHAR, horizon_days INTEGER, horizon_bucket VARCHAR,
            source_dislocation_ids VARCHAR, related_gap_ids VARCHAR,
            world_state_json VARCHAR, price_state_json VARCHAR,
            mechanism_template_id VARCHAR, mechanism_text VARCHAR,
            validation_prior DOUBLE, scoring_config_version VARCHAR,
            scoring_config_hash VARCHAR, preferred_ticker VARCHAR,
            proxy_type VARCHAR, expression_quality_at_open DOUBLE,
            liquidity_tier_at_open VARCHAR, etf_ownership_drag_bps DOUBLE,
            currency_basis VARCHAR, basis_gap_z_at_open DOUBLE,
            crowding_score_at_open DOUBLE, severity_score_at_open DOUBLE,
            novelty_score_at_open DOUBLE, validation_prior_score_at_open DOUBLE,
            expression_quality_score_at_open DOUBLE, catalyst_nearness_score_at_open DOUBLE,
            etf_drag_score_at_open DOUBLE, crowding_penalty_score_at_open DOUBLE,
            staleness_penalty_score_at_open DOUBLE, data_quality_penalty_score_at_open DOUBLE,
            tension_score_at_open DOUBLE, tension_components_json VARCHAR,
            expected_absorption_path_json VARCHAR, invalidation_rule VARCHAR,
            research_only BOOLEAN, paper_candidate BOOLEAN, status VARCHAR,
            closed_at TIMESTAMP, close_reason VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS gap_episode_expression (
            gap_id VARCHAR, ticker VARCHAR, is_primary BOOLEAN, proxy_type VARCHAR,
            currency_basis VARCHAR, expense_ratio_bps DOUBLE, dollar_adv_21d DOUBLE,
            liquidity_tier VARCHAR, basis_gap_21d DOUBLE, basis_gap_z DOUBLE,
            fx_adjusted_basis_gap_21d DOUBLE, expression_quality DOUBLE, reason VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS gap_episode_marks (
            gap_id VARCHAR, date DATE, mark_window VARCHAR, entity VARCHAR,
            preferred_ticker VARCHAR, realized_etf_return DOUBLE,
            realized_country_return DOUBLE, realized_move DOUBLE,
            expected_move DOUBLE, expected_move_source VARCHAR,
            price_absorption_index DOUBLE, unabsorbed_fraction DOUBLE,
            absorption_state VARCHAR, tension_score_current DOUBLE,
            days_active INTEGER, expression_quality_current DOUBLE,
            crowding_penalty_current DOUBLE, source_freshness_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS gap_episode_autopsy (
            gap_id VARCHAR, closed_at TIMESTAMP, close_reason VARCHAR,
            outcome_label VARCHAR, absorption_half_life_days DOUBLE,
            realized_etf_return DOUBLE, realized_country_return DOUBLE,
            net_return_after_etf_drag DOUBLE, notes VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS gap_holdout_daily (
            date DATE, candidate_id VARCHAR, candidate_signature VARCHAR,
            gap_id VARCHAR, entity VARCHAR, gap_class VARCHAR, direction VARCHAR,
            horizon_bucket VARCHAR, source_dislocation_ids VARCHAR, eligible BOOLEAN,
            promoted BOOLEAN, scoring_config_version VARCHAR, scoring_config_hash VARCHAR,
            severity_score DOUBLE, novelty_score DOUBLE, validation_prior_score DOUBLE,
            expression_quality_score DOUBLE, catalyst_nearness_score DOUBLE,
            etf_drag_score DOUBLE, crowding_penalty_score DOUBLE,
            staleness_penalty_score DOUBLE, data_quality_penalty_score DOUBLE,
            tension_score_at_selection DOUBLE, random_shadow_score DOUBLE,
            reason_not_promoted VARCHAR, future_return_21d DOUBLE, future_return_63d DOUBLE
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS gap_engine_config_history (
            as_of_date DATE, config_version VARCHAR, scoring_config_hash VARCHAR,
            config_json VARCHAR, recorded_at TIMESTAMP
        )
        """
    )


def latest_asof(con, explicit: str | None) -> pd.Timestamp:
    if explicit:
        return pd.Timestamp(explicit)
    if table_exists(con, "price_state_daily"):
        d = con.execute("SELECT max(date) FROM price_state_daily").fetchone()[0]
        if d:
            return pd.Timestamp(d)
    d = con.execute("SELECT max(date) FROM dislocation_daily").fetchone()[0]
    if not d:
        raise RuntimeError("dislocation_daily is empty")
    return pd.Timestamp(d)


def mechanism_text(template: str, entity: str, direction: str) -> str:
    return template.format(entity=entity, direction=direction)


def expression_quality(row: pd.Series | None) -> tuple[float, float, float]:
    if row is None:
        return 0.10, 0.0, 0.8
    tier_score = {"high": 0.95, "medium": 0.80, "low": 0.55, "micro": 0.25, "missing": 0.10}
    q = tier_score.get(row.get("liquidity_tier"), 0.20)
    basis_z = row.get("basis_gap_z")
    if basis_z is not None and basis_z == basis_z:
        q -= min(0.30, abs(float(basis_z)) / 10.0)
    if pd.isna(row.get("preferred_ticker")):
        q = 0.10
    data_penalty = 0.0 if q >= 0.25 else 0.8
    return clamp(q), clamp(1.0 - q), data_penalty


def crowding_penalty(price: pd.Series | None) -> float:
    if price is None:
        return 0.2
    try:
        flow = json.loads(price.get("flow_state_json") or "{}")
    except Exception:
        return 0.2
    zvals = []
    for key in ["ETF_FLOW_21D_Z", "ETF_SHORT_PCT_Z"]:
        val = flow.get(key, {})
        if isinstance(val, dict) and val.get("value") is not None:
            zvals.append(abs(float(val["value"])))
    return clamp(max(zvals) / 3.0) if zvals else 0.15


def candidate_signature(disloc: pd.Series, horizon_bucket: str) -> str:
    did = disloc.get("dislocation_id")
    if did:
        return str(did)
    comp = disloc.get("components_json") or "{}"
    try:
        parsed = json.loads(comp)
    except Exception:
        parsed = {"raw": comp}
    rounded = {k: round(float(v), 4) if isinstance(v, (int, float)) else v for k, v in parsed.items()}
    seed = json_dumps({
        "detector": disloc.get("detector"),
        "entity": disloc.get("entity"),
        "direction": disloc.get("direction"),
        "horizon_bucket": horizon_bucket,
        "components": rounded,
    })
    return stable_hash(seed, 20)


def random_shadow(candidate_id: str, cfg_hash: str, cfg: dict[str, Any]) -> float:
    seed = stable_hash(f"{candidate_id}|{cfg_hash}|{cfg.get('holdout', {}).get('random_shadow_seed', 'shadow_v1')}", 16)
    return random.Random(seed).random()


def open_episode_lookup(con) -> dict[str, Any]:
    if not table_exists(con, "gap_episodes"):
        return {}
    df = con.execute("SELECT gap_id, episode_key FROM gap_episodes WHERE status = 'open'").fetchdf()
    return {r.episode_key: r.gap_id for r in df.itertuples()}


def next_instance(con, episode_key: str) -> int:
    if not table_exists(con, "gap_episodes"):
        return 1
    got = con.execute(
        "SELECT max(episode_instance) FROM gap_episodes WHERE episode_key = ?",
        [episode_key],
    ).fetchone()[0]
    return int(got or 0) + 1


def build(as_of: str | None = None) -> dict[str, int]:
    cfg, cfg_hash = load_gap_config()
    etf_map = load_etf_map()
    etf_overrides = load_etf_overrides()
    con = loop_connection()
    try:
        ensure_schema(con)
        as_ts = latest_asof(con, as_of)
        as_str = str(as_ts.date())
        cfg_version = cfg.get("config_version", "gap_engine_v1")
        con.execute("DELETE FROM gap_engine_config_history WHERE as_of_date = ?", [as_str])
        con.execute(
            "INSERT INTO gap_engine_config_history VALUES (?, ?, ?, ?, ?)",
            [as_str, cfg_version, cfg_hash, json_dumps(cfg), datetime.now()],
        )

        if not table_exists(con, "price_state_daily"):
            raise RuntimeError("price_state_daily missing; run build_price_state.py first")

        price_df = con.execute(
            "SELECT * FROM price_state_daily WHERE CAST(date AS DATE) = CAST(? AS DATE)",
            [as_str],
        ).fetchdf()
        price_by_country = {r.country: pd.Series(r._asdict()) for r in price_df.itertuples()}
        disloc = con.execute(
            "SELECT * FROM dislocation_daily WHERE CAST(date AS DATE) = CAST(? AS DATE)",
            [as_str],
        ).fetchdf()
        if disloc.empty:
            log(f"no dislocations for {as_str}; only marking existing open episodes")

        open_by_key = open_episode_lookup(con)
        detector_map = cfg.get("detector_map", {})
        horizons = cfg.get("horizons", {}).get("buckets", {})
        ranked_classes = set(cfg.get("promotion", {}).get("ranked_gap_classes", []))
        never_rank = set(cfg.get("promotion", {}).get("never_rank_detectors", []))
        max_age = int(cfg.get("promotion", {}).get("max_age_days", 63))
        min_sev = float(cfg.get("promotion", {}).get("min_abs_severity", 1.0))
        min_score = float(cfg.get("promotion", {}).get("min_tension_score", 0.35))
        allow_statuses = set(cfg.get("promotion", {}).get("allow_statuses", []))
        templates = cfg.get("mechanism_templates", {})
        defaults = cfg.get("score_defaults", {})

        new_episode_rows: list[dict[str, Any]] = []
        expression_rows: list[dict[str, Any]] = []
        holdout_rows: list[dict[str, Any]] = []
        promoted_gap_ids: dict[str, str] = {}

        for rec in disloc.to_dict("records"):
            detector = rec.get("detector")
            dcfg = detector_map.get(detector, {})
            gap_class = dcfg.get("gap_class", "G1")
            horizon_bucket = dcfg.get("horizon_bucket", cfg.get("horizons", {}).get("default_bucket", "21d"))
            horizon_days = int(horizons.get(horizon_bucket, 21))
            entity = rec.get("entity")
            direction = rec.get("direction")
            status = rec.get("status")
            archetype = rec.get("archetype")
            price = price_by_country.get(entity)
            episode_key = f"{entity}|{gap_class}|{direction}|{horizon_bucket}"
            signature = candidate_signature(pd.Series(rec), horizon_bucket)
            candidate_id = stable_hash(f"{as_str}|{episode_key}|{signature}", 20)
            severity = float(rec.get("severity") or 0.0)
            validation_prior = float(dcfg.get("validation_prior_score", defaults.get("validation_prior_neutral", 0.5)))
            expr_q, expr_penalty, data_penalty = expression_quality(price)
            crowd_pen = crowding_penalty(price)
            expense_ratio = 0.0
            if price is not None and price.get("expense_ratio_bps") is not None and price.get("expense_ratio_bps") == price.get("expense_ratio_bps"):
                expense_ratio = float(price.get("expense_ratio_bps"))
            components = {
                "severity_score": norm_abs_z(severity),
                "novelty_score": status_novelty_score(status),
                "validation_prior_score": clamp(validation_prior),
                "expression_quality_score": expr_q,
                "catalyst_nearness_score": float(defaults.get("catalyst_neutral", 0.35)),
                "etf_drag_score": clamp(expense_ratio / 100.0),
                "crowding_penalty_score": crowd_pen,
                "staleness_penalty_score": staleness_penalty(rec.get("days_active"), max_age),
                "data_quality_penalty_score": data_penalty,
            }
            tension = score_tension(components, cfg)
            research_only = bool(dcfg.get("research_only")) or gap_class not in ranked_classes or detector in never_rank
            eligible = (
                status in allow_statuses
                and archetype != "degraded"
                and abs(severity) >= min_sev
                and entity in T2_UNIVERSE
                and direction in ("long", "short")
                and price is not None
            )
            promoted = bool(eligible and not research_only and tension >= min_score)
            reason_not = None
            if not promoted:
                reason_not = "research_only" if research_only else "below_threshold_or_ineligible"
            gap_id = open_by_key.get(episode_key)
            if promoted and not gap_id:
                instance = next_instance(con, episode_key)
                gap_seed = f"{episode_key}|{as_str}|{instance}"
                gap_id = stable_hash(gap_seed, 20)
                open_by_key[episode_key] = gap_id
                promoted_gap_ids[candidate_id] = gap_id
                expected, floor, source = expected_move(gap_class, horizon_bucket, severity, direction, cfg)
                pjson = price.to_dict() if price is not None else {}
                preferred_ticker = pjson.get("preferred_ticker")
                template_id = dcfg.get("mechanism_template_id", f"{detector}_template")
                row = {
                    "gap_id": gap_id,
                    "episode_key": episode_key,
                    "episode_instance": instance,
                    "gap_id_seed": gap_seed,
                    "opened_at": datetime.now(),
                    "first_seen_date": as_str,
                    "as_of_date_open": as_str,
                    "entity": entity,
                    "direction": direction,
                    "gap_class": gap_class,
                    "horizon_days": horizon_days,
                    "horizon_bucket": horizon_bucket,
                    "source_dislocation_ids": json_dumps([rec.get("dislocation_id")]),
                    "related_gap_ids": json_dumps([]),
                    "world_state_json": rec.get("components_json") or "{}",
                    "price_state_json": json_dumps(pjson),
                    "mechanism_template_id": template_id,
                    "mechanism_text": mechanism_text(templates.get(template_id, "{entity} {direction}: price-discovery gap."), entity, direction),
                    "validation_prior": validation_prior,
                    "scoring_config_version": cfg_version,
                    "scoring_config_hash": cfg_hash,
                    "preferred_ticker": preferred_ticker,
                    "proxy_type": pjson.get("proxy_type"),
                    "expression_quality_at_open": expr_q,
                    "liquidity_tier_at_open": pjson.get("liquidity_tier"),
                    "etf_ownership_drag_bps": float(pjson.get("expense_ratio_bps") or 0.0) * horizon_days / 365.0,
                    "currency_basis": pjson.get("currency_basis"),
                    "basis_gap_z_at_open": pjson.get("basis_gap_z"),
                    "crowding_score_at_open": crowd_pen,
                    "severity_score_at_open": components["severity_score"],
                    "novelty_score_at_open": components["novelty_score"],
                    "validation_prior_score_at_open": components["validation_prior_score"],
                    "expression_quality_score_at_open": components["expression_quality_score"],
                    "catalyst_nearness_score_at_open": components["catalyst_nearness_score"],
                    "etf_drag_score_at_open": components["etf_drag_score"],
                    "crowding_penalty_score_at_open": components["crowding_penalty_score"],
                    "staleness_penalty_score_at_open": components["staleness_penalty_score"],
                    "data_quality_penalty_score_at_open": components["data_quality_penalty_score"],
                    "tension_score_at_open": tension,
                    "tension_components_json": json_dumps({"weights": cfg.get("score_weights", {}), "components": components, "config_hash": cfg_hash}),
                    "expected_absorption_path_json": json_dumps({"expected_move": expected, "expected_move_floor": floor, "expected_move_source": source, "provisional": True}),
                    "invalidation_rule": f"Invalidate if {entity} price-state reprices against the {direction} mechanism or source severity fades below threshold.",
                    "research_only": research_only,
                    "paper_candidate": False,
                    "status": "open",
                    "closed_at": None,
                    "close_reason": None,
                }
                new_episode_rows.append(row)

                primary = pjson.get("preferred_ticker")
                tickers = [primary] + list((etf_map.get(entity, {}) or {}).get("alternates", []))
                seen = set()
                for t in [x for x in tickers if x and not (x in seen or seen.add(x))]:
                    is_primary = t == primary
                    expression_rows.append({
                        "gap_id": gap_id,
                        "ticker": t,
                        "is_primary": is_primary,
                        "proxy_type": pjson.get("proxy_type") if is_primary else "alternate",
                        "currency_basis": pjson.get("currency_basis"),
                        "expense_ratio_bps": pjson.get("expense_ratio_bps") if is_primary else etf_overrides.get("defaults", {}).get("expense_ratio_bps"),
                        "dollar_adv_21d": pjson.get("dollar_adv_21d") if is_primary else None,
                        "liquidity_tier": pjson.get("liquidity_tier") if is_primary else "missing",
                        "basis_gap_21d": pjson.get("basis_gap_21d") if is_primary else None,
                        "basis_gap_z": pjson.get("basis_gap_z") if is_primary else None,
                        "fx_adjusted_basis_gap_21d": pjson.get("fx_adjusted_basis_gap_21d") if is_primary else None,
                        "expression_quality": expr_q if is_primary else 0.4,
                        "reason": "primary from etf_t2_map + overrides" if is_primary else "alternate from etf_t2_map",
                    })
            elif promoted and gap_id:
                promoted_gap_ids[candidate_id] = gap_id

            holdout_rows.append({
                "date": as_str,
                "candidate_id": candidate_id,
                "candidate_signature": signature,
                "gap_id": gap_id if promoted else None,
                "entity": entity,
                "gap_class": gap_class,
                "direction": direction,
                "horizon_bucket": horizon_bucket,
                "source_dislocation_ids": json_dumps([rec.get("dislocation_id")]),
                "eligible": eligible,
                "promoted": promoted,
                "scoring_config_version": cfg_version,
                "scoring_config_hash": cfg_hash,
                "severity_score": components["severity_score"],
                "novelty_score": components["novelty_score"],
                "validation_prior_score": components["validation_prior_score"],
                "expression_quality_score": components["expression_quality_score"],
                "catalyst_nearness_score": components["catalyst_nearness_score"],
                "etf_drag_score": components["etf_drag_score"],
                "crowding_penalty_score": components["crowding_penalty_score"],
                "staleness_penalty_score": components["staleness_penalty_score"],
                "data_quality_penalty_score": components["data_quality_penalty_score"],
                "tension_score_at_selection": tension,
                "random_shadow_score": random_shadow(candidate_id, cfg_hash, cfg),
                "reason_not_promoted": reason_not,
                "future_return_21d": None,
                "future_return_63d": None,
            })

        if new_episode_rows:
            episode_df = pd.DataFrame(new_episode_rows, columns=EPISODE_COLUMNS)
            con.execute("INSERT INTO gap_episodes BY NAME SELECT * FROM episode_df")
        if expression_rows:
            expr_df = pd.DataFrame(expression_rows)
            con.execute("INSERT INTO gap_episode_expression BY NAME SELECT * FROM expr_df")

        holdout_df = pd.DataFrame(holdout_rows)
        con.execute("DELETE FROM gap_holdout_daily WHERE date = ?", [as_str])
        if not holdout_df.empty:
            con.execute("INSERT INTO gap_holdout_daily BY NAME SELECT * FROM holdout_df")

        mark_rows, autopsy_rows = build_marks_and_closures(con, as_ts, cfg)
        con.execute("DELETE FROM gap_episode_marks WHERE date = ?", [as_str])
        if mark_rows:
            marks_df = pd.DataFrame(mark_rows)
            con.execute("INSERT INTO gap_episode_marks BY NAME SELECT * FROM marks_df")
        if autopsy_rows:
            autopsy_df = pd.DataFrame(autopsy_rows)
            con.execute("INSERT INTO gap_episode_autopsy BY NAME SELECT * FROM autopsy_df")

        out_dir = ensure_loop_artifact_dir()
        for table in ["gap_episodes", "gap_episode_expression", "gap_episode_marks",
                      "gap_episode_autopsy", "gap_holdout_daily"]:
            try:
                df = con.execute(f"SELECT * FROM {table}").fetchdf()
                df.to_parquet(out_dir / f"{table}.parquet", index=False)
            except Exception as exc:
                log(f"parquet skip {table}: {exc}")
        log(f"new episodes={len(new_episode_rows)} holdout={len(holdout_rows)} marks={len(mark_rows)} autopsies={len(autopsy_rows)}")
        return {"episodes": len(new_episode_rows), "holdout": len(holdout_rows), "marks": len(mark_rows), "autopsies": len(autopsy_rows)}
    finally:
        con.close()


def build_marks_and_closures(con, as_ts: pd.Timestamp, cfg: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    open_eps = con.execute("SELECT * FROM gap_episodes WHERE status = 'open'").fetchdf()
    if open_eps.empty:
        return [], []
    price = con.execute(
        "SELECT * FROM price_state_daily WHERE CAST(date AS DATE) = CAST(? AS DATE)",
        [str(as_ts.date())],
    ).fetchdf()
    price_by_country = {r.country: r._asdict() for r in price.itertuples()}
    cap = float(cfg.get("expected_move", {}).get("index_cap_abs", 2.0))
    max_age = int(cfg.get("promotion", {}).get("max_age_days", 63))
    marks = []
    autopsies = []
    for ep in open_eps.to_dict("records"):
        p = price_by_country.get(ep["entity"], {})
        direction = ep["direction"]
        ds = direction_sign(direction)
        etf_ret = p.get("etf_return_21d")
        country_ret = p.get("country_return_21d")
        realized = None
        if ds and etf_ret is not None and etf_ret == etf_ret:
            realized = ds * float(etf_ret)
        try:
            expected_info = json.loads(ep.get("expected_absorption_path_json") or "{}")
        except Exception:
            expected_info = {}
        exp = expected_info.get("expected_move")
        floor = float(expected_info.get("expected_move_floor") or cfg.get("expected_move", {}).get("default_floor_abs", 0.005))
        idx, unabs, state = absorption_state(realized, exp, floor, cap)
        days_active = int((as_ts.date() - pd.Timestamp(ep["first_seen_date"]).date()).days) + 1
        # net_return_after_etf_drag stores the DIRECTION-ADJUSTED realized return
        # (`realized` = direction_sign * etf_return_21d), not the raw undirected
        # ETF move — otherwise a winning short reads as a loss. No expense drag is
        # separately subtracted (it is already inside the price series). This is a
        # lightweight lifecycle marker; the append-only gap_outcomes table is the
        # authoritative net-of-cost outcome measure.
        if days_active > max_age and state in ("unabsorbed", "insufficient_signal"):
            state = "decayed"
            con.execute(
                "UPDATE gap_episodes SET status='expired', closed_at=?, close_reason=? WHERE gap_id=?",
                [datetime.now(), "max_age_unabsorbed", ep["gap_id"]],
            )
            autopsies.append({
                "gap_id": ep["gap_id"],
                "closed_at": datetime.now(),
                "close_reason": "max_age_unabsorbed",
                "outcome_label": "unresolved_decay",
                "absorption_half_life_days": None,
                "realized_etf_return": etf_ret,
                "realized_country_return": country_ret,
                "net_return_after_etf_drag": realized,
                "notes": "Auto-expired by max_age_days with no clear absorption.",
            })
        elif days_active > max_age and state == "repriced_against":
            # Falsified gap: price moved AGAINST the thesis through max_age. Close
            # it as an explicit failure autopsy so adverse episodes enter outcome
            # statistics — otherwise repriced_against gaps linger open forever and
            # the autopsy population is selected on success (GPT-5.6, 2026-07-10).
            con.execute(
                "UPDATE gap_episodes SET status='closed', closed_at=?, close_reason=? WHERE gap_id=?",
                [datetime.now(), "max_age_repriced_against", ep["gap_id"]],
            )
            autopsies.append({
                "gap_id": ep["gap_id"],
                "closed_at": datetime.now(),
                "close_reason": "max_age_repriced_against",
                "outcome_label": "falsified",
                "absorption_half_life_days": None,
                "realized_etf_return": etf_ret,
                "realized_country_return": country_ret,
                "net_return_after_etf_drag": realized,
                "notes": "Auto-closed: price repriced against the thesis through max_age.",
            })
        elif state == "absorbed":
            con.execute(
                "UPDATE gap_episodes SET status='closed', closed_at=?, close_reason=? WHERE gap_id=?",
                [datetime.now(), "absorbed", ep["gap_id"]],
            )
            autopsies.append({
                "gap_id": ep["gap_id"],
                "closed_at": datetime.now(),
                "close_reason": "absorbed",
                "outcome_label": "success_with_absorption",
                "absorption_half_life_days": days_active,
                "realized_etf_return": etf_ret,
                "realized_country_return": country_ret,
                "net_return_after_etf_drag": realized,
                "notes": "Auto-closed after price absorption threshold cleared.",
            })
        has_price = bool(p)
        expr_q, _, data_pen = expression_quality(pd.Series(p) if has_price else None)
        crowd = crowding_penalty(pd.Series(p) if has_price else None)
        # Live tension (gap_engine_v2): re-scored with today's expression /
        # crowding / staleness / absorption instead of copying the open score
        # forward. repriced_against episodes are forced below the promotion
        # floor so the cockpit and brief never headline a falsified gap.
        tension_now = tension_current(
            {
                "severity_score": ep.get("severity_score_at_open"),
                "novelty_score": ep.get("novelty_score_at_open"),
                "validation_prior_score": ep.get("validation_prior_score_at_open"),
                "catalyst_nearness_score": ep.get("catalyst_nearness_score_at_open"),
                "etf_drag_score": ep.get("etf_drag_score_at_open"),
            },
            cfg, days_active, max_age, state, idx, expr_q, crowd, data_pen,
        )
        marks.append({
            "gap_id": ep["gap_id"],
            "date": str(as_ts.date()),
            "mark_window": "21d",
            "entity": ep["entity"],
            "preferred_ticker": ep["preferred_ticker"],
            "realized_etf_return": etf_ret,
            "realized_country_return": country_ret,
            "realized_move": realized,
            "expected_move": exp,
            "expected_move_source": expected_info.get("expected_move_source", "severity_mapping"),
            "price_absorption_index": idx,
            "unabsorbed_fraction": unabs,
            "absorption_state": state,
            "tension_score_current": tension_now,
            "days_active": days_active,
            "expression_quality_current": expr_q,
            "crowding_penalty_current": crowd,
            "source_freshness_json": p.get("source_freshness_json") if p else "{}",
        })
    return marks, autopsies


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        for table in ["gap_episodes", "gap_episode_expression", "gap_episode_marks",
                      "gap_episode_autopsy", "gap_holdout_daily"]:
            n = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            print(f"{table}: rows={n}")
        return 0
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Price-Discovery Gap Engine episodes.")
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        return check()
    build(args.as_of)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
