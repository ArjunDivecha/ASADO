from __future__ import annotations

import pandas as pd

from scripts.loop.gap_engine_common import (
    absorption_state,
    load_gap_config,
    stable_hash,
    tension_current,
)
from scripts.loop.loopdb import LOOP_DB
from scripts.loop.render_dislocation_brief import (
    START,
    dedupe_entity_direction,
    insert_section,
    select_diversified_gaps,
    strip_existing,
)


def test_gap_id_seed_excludes_asof_date_for_existing_episode_contract():
    episode_key = "Brazil|G2|long|21d"
    seed = f"{episode_key}|2026-06-24|1"
    first = stable_hash(seed, 20)
    second = stable_hash(seed, 20)
    assert first == second
    assert stable_hash(f"{episode_key}|2026-06-25|1", 20) != first
    assert stable_hash(f"{episode_key}|2026-06-24|2", 20) != first


def test_absorption_state_provisional_mapping_states():
    idx, unabsorbed, state = absorption_state(0.002, 0.02, 0.005, 2.0)
    assert state == "unabsorbed"
    assert idx == 0.1
    assert unabsorbed == 0.9

    idx, _, state = absorption_state(0.02, 0.02, 0.005, 2.0)
    assert state == "absorbed"
    assert idx == 1.0

    idx, _, state = absorption_state(-0.01, 0.02, 0.005, 2.0)
    assert state == "repriced_against"
    assert idx == -0.5


_OPEN_COMPONENTS = {
    "severity_score": 1.0,
    "novelty_score": 1.0,
    "validation_prior_score": 0.65,
    "catalyst_nearness_score": 0.35,
    "etf_drag_score": 0.0,
}


def test_tension_current_forces_repriced_against_below_promotion_floor():
    cfg, _ = load_gap_config()
    floor = float(cfg["promotion"]["min_tension_score"])
    fresh = tension_current(_OPEN_COMPONENTS, cfg, 1, 63, "unabsorbed", 0.1, 0.95, 0.1, 0.0)
    against = tension_current(_OPEN_COMPONENTS, cfg, 1, 63, "repriced_against", -0.5, 0.95, 0.1, 0.0)
    deep = tension_current(_OPEN_COMPONENTS, cfg, 1, 63, "repriced_against", -2.0, 0.95, 0.1, 0.0)
    assert fresh > floor
    assert against < floor
    assert deep == 0.0
    assert against < fresh


def test_tension_current_scales_by_remaining_absorption_and_staleness():
    cfg, _ = load_gap_config()
    fresh = tension_current(_OPEN_COMPONENTS, cfg, 1, 63, "unabsorbed", 0.1, 0.95, 0.1, 0.0)
    partial = tension_current(_OPEN_COMPONENTS, cfg, 1, 63, "partially_absorbed", 0.5, 0.95, 0.1, 0.0)
    absorbed = tension_current(_OPEN_COMPONENTS, cfg, 1, 63, "absorbed", 1.0, 0.95, 0.1, 0.0)
    stale = tension_current(_OPEN_COMPONENTS, cfg, 60, 63, "unabsorbed", 0.1, 0.95, 0.1, 0.0)
    assert 0.0 < partial < fresh
    assert absorbed == 0.0
    assert stale < fresh


def test_tension_current_is_nan_safe():
    cfg, _ = load_gap_config()
    nan = float("nan")
    got = tension_current(
        {k: nan for k in _OPEN_COMPONENTS}, cfg, None, 63,
        "unabsorbed", nan, nan, nan, nan,
    )
    assert got == got  # not NaN
    assert 0.0 <= got <= 1.0


def test_renderer_section_is_idempotent():
    original = "# Dislocation brief - 2026-06-24\n\nOld body\n"
    section = f"{START}\n\n## Top Price-Discovery Gaps (pilot)\n\nExample\n<!-- GAP_ENGINE_TOP_END -->"
    once = insert_section(original, section)
    twice = insert_section(once, section)
    assert once == twice
    assert once.count(START) == 1
    assert strip_existing(once).count(START) == 0


def test_renderer_inserts_after_governance_block():
    original = (
        "<!-- GOVERNANCE_SCORECARD_START -->\n"
        "## Governance\n"
        "<!-- GOVERNANCE_SCORECARD_END -->\n\n"
        "# Dislocation brief - 2026-06-24\n\nOld body\n"
    )
    section = f"{START}\n\n## Top Price-Discovery Gaps (pilot)\n\nExample\n<!-- GAP_ENGINE_TOP_END -->"
    rendered = insert_section(original, section)
    assert rendered.index("<!-- GOVERNANCE_SCORECARD_END -->") < rendered.index(START)
    assert rendered.index(START) < rendered.index("# Dislocation brief")


def test_entity_direction_dedup_nests_related_rows():
    df = pd.DataFrame(
        [
            {"entity": "Brazil", "direction": "long", "gap_class": "G2", "gap_id": "a" * 20},
            {"entity": "Brazil", "direction": "long", "gap_class": "G5", "gap_id": "b" * 20},
            {"entity": "Korea", "direction": "short", "gap_class": "G5", "gap_id": "c" * 20},
        ]
    )
    got = dedupe_entity_direction(df, 5)
    assert [r["entity"] for r in got] == ["Brazil", "Korea"]
    assert got[0]["_related"][0]["gap_class"] == "G5"


def test_brief_headline_gaps_diversify_classes_after_strongest():
    df = pd.DataFrame(
        [
            {"entity": "Japan", "direction": "short", "gap_class": "G2", "gap_id": "a" * 20},
            {"entity": "India", "direction": "short", "gap_class": "G2", "gap_id": "b" * 20},
            {"entity": "Korea", "direction": "short", "gap_class": "G2", "gap_id": "c" * 20},
            {"entity": "Taiwan", "direction": "short", "gap_class": "G3", "gap_id": "d" * 20},
            {"entity": "Vietnam", "direction": "long", "gap_class": "G4", "gap_id": "e" * 20},
        ]
    )
    got = select_diversified_gaps(df, 5)
    assert got[0]["entity"] == "Japan"
    assert [r["gap_class"] for r in got[:3]] == ["G2", "G3", "G4"]


def test_live_gap_engine_tables_if_present():
    if not LOOP_DB.exists():
        return
    import duckdb

    con = duckdb.connect(str(LOOP_DB), read_only=True)
    try:
        tables = {
            r[0]
            for r in con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
            ).fetchall()
        }
        required = {
            "price_state_daily",
            "price_state_surface",
            "gap_episodes",
            "gap_episode_expression",
            "gap_episode_marks",
            "gap_holdout_daily",
        }
        if not required.issubset(tables):
            return
        assert con.execute("SELECT count(*) FROM price_state_daily").fetchone()[0] >= 34
        assert con.execute("SELECT count(*) FROM price_state_surface").fetchone()[0] >= 34
        assert con.execute("SELECT count(*) FROM gap_holdout_daily").fetchone()[0] > 0
        bad = con.execute(
            """
            SELECT count(*)
            FROM gap_episodes
            WHERE gap_id != substr(sha1(gap_id_seed), 1, 20)
               OR scoring_config_hash IS NULL
               OR severity_score_at_open IS NULL
               OR expression_quality_score_at_open IS NULL
            """
        ).fetchone()[0]
        assert bad == 0
        invalid_json = con.execute(
            """
            SELECT count(*)
            FROM gap_episodes
            WHERE json_valid(world_state_json) = false
               OR json_valid(price_state_json) = false
               OR json_valid(tension_components_json) = false
            """
        ).fetchone()[0]
        assert invalid_json == 0
    finally:
        con.close()
