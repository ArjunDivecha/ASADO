#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: test_cockpit_selection.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/cos_mockups/build_cockpit_data.py
    The module under test (imported, not executed).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/cos_mockups/cockpit_data.json
    The live payload (only used by the @live invariant tests; skipped if absent).

OUTPUT FILES:
- none (pytest assertions only)

VERSION: 1.0
LAST UPDATED: 2026-06-19
AUTHOR: Arjun Divecha / Claude Code

DESCRIPTION:
Guards the SELECTION INTELLIGENCE (DESIGN_BRIEF.md §1) so it cannot drift
silently as the underlying loop data changes. Two layers:
  1. Deterministic unit tests of the pure rule functions (build_today, build_map)
     with synthetic inputs — these encode the rules themselves.
  2. Invariant tests over the live cockpit_data.json artifact (skipped if it has
     not been generated yet).

DEPENDENCIES:
- pytest

USAGE:
  source venv/bin/activate
  pytest cos_mockups/test_cockpit_selection.py -v
=============================================================================
"""

import importlib.util
import json
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
MOD_PATH = HERE / "build_cockpit_data.py"
PAYLOAD = HERE / "cockpit_data.json"

# import build_cockpit_data.py as a module without running main()
_spec = importlib.util.spec_from_file_location("build_cockpit_data", MOD_PATH)
bcd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bcd)


# --------------------------------------------------------------------------- #
# Fixtures: synthetic inputs that exercise each promotion rule
# --------------------------------------------------------------------------- #
def gov(overall="amber"):
    return {
        "overall": overall,
        "dimensions": [
            {"name": "run_manifest", "status": "green", "amber_by_design": False, "detail": "ok"},
            {"name": "cross_source_minimal", "status": "amber", "amber_by_design": True,
             "detail": "coverage 1.0 (partial by design)"},
        ],
    }


def signals():
    return [
        {"id": "S1", "name": "momentum_sanity", "verdict": "WATCH", "horizon": "1m",
         "ic": 0.25, "nw_t": 15.4, "is_sanity": True},
        {"id": "S2", "name": "graph_trade_gap", "verdict": "WATCH", "horizon": "5d",
         "ic": 0.027, "nw_t": 7.1, "is_sanity": False},
        {"id": "S3", "name": "ml_combiner", "verdict": "WEAK", "horizon": "5d",
         "ic": 0.05, "nw_t": 10.7, "is_sanity": False},
    ]


def dislo():
    rows = [
        {"id": "d1", "detector": "D2", "archetype": "A2", "entity": "Netherlands",
         "direction": "short", "severity": -2.82, "abs_severity": 2.82, "days_active": 6,
         "first_seen": "2026-06-10", "reading": "country outran neighbors", "is_country": True},
        {"id": "d2", "detector": "D1", "archetype": "A1", "entity": "Germany",
         "direction": "short", "severity": -2.38, "abs_severity": 2.38, "days_active": 3,
         "first_seen": "2026-06-12", "reading": "ToT deteriorating", "is_country": True},
        # structural detector with the largest |severity| — must NOT be promoted
        {"id": "d3", "detector": "D8", "archetype": "A8", "entity": "stewardship",
         "direction": "flat", "severity": 9.9, "abs_severity": 9.9, "days_active": 1,
         "first_seen": "2026-06-16", "reading": "36 open theses", "is_country": False},
    ]
    country = sorted([r for r in rows if r["is_country"]],
                     key=lambda x: (-x["abs_severity"], x["days_active"]))
    return {"as_of": "2026-06-16", "counts": {"D1": 1, "D2": 1, "D8": 1},
            "rows": rows, "country_ranked": country, "total": len(rows)}


def gap_engine(status="fresh"):
    return {
        "status": status,
        "as_of": "2026-06-23",
        "top": [{
            "gap_id": "g1",
            "entity": "Japan",
            "direction": "short",
            "gap_class": "G2",
            "preferred_ticker": "EWJ",
            "absorption_state": "repriced_against",
            "unabsorbed_fraction": 0.61,
            "horizon_bucket": "21d",
            "mechanism_text": "Terms-of-trade impulse remains ahead of ETF price.",
            "tension_score_current": 0.5,
        }] if status == "fresh" else [],
        "by_country": {
            "Japan": {
                "primary": {
                    "gap_id": "g1",
                    "entity": "Japan",
                    "direction": "short",
                    "gap_class": "G2",
                    "preferred_ticker": "EWJ",
                    "absorption_state": "repriced_against",
                    "tension_score_current": 0.5,
                },
                "all": [],
            }
        } if status == "fresh" else {},
        "counts": {},
        "holdout": {},
        "staleness": {},
    }


# --------------------------------------------------------------------------- #
# §1.2 — three-slot promotion rule
# --------------------------------------------------------------------------- #
def test_today_has_at_most_three_slots():
    assert len(bcd.build_today(gov(), signals(), dislo())) <= 3


def test_slot1_is_governance_when_not_green():
    slots = bcd.build_today(gov("amber"), signals(), dislo())
    assert slots[0]["kind"] == "governance"
    assert "AMBER" in slots[0]["headline"]


def test_no_governance_slot_when_all_green():
    slots = bcd.build_today(gov("green"), signals(), dislo())
    assert all(s["kind"] != "governance" for s in slots)


def test_slot_signal_excludes_sanity_family():
    # momentum_sanity has the highest NW-t but must be skipped; graph_trade_gap wins
    slots = bcd.build_today(gov(), signals(), dislo())
    sig = [s for s in slots if s["kind"] == "signal"][0]
    assert "graph_trade_gap" in sig["headline"]
    assert "momentum_sanity" not in sig["headline"]


def test_signal_slot_only_promotes_watch():
    only_weak = [s for s in signals() if s["verdict"] != "WATCH"]
    slots = bcd.build_today(gov("green"), only_weak, dislo())
    assert all(s["kind"] != "signal" for s in slots)


def test_dislocation_slot_is_strongest_country_not_structural():
    slots = bcd.build_today(gov(), signals(), dislo())
    dsl = [s for s in slots if s["kind"] == "dislocation"][0]
    # Netherlands (|2.82|) beats Germany (|2.38|); structural D8 (9.9) excluded
    assert "Netherlands" in dsl["headline"]
    assert "stewardship" not in dsl["headline"]


def test_fresh_gap_slot_replaces_raw_dislocation():
    slots = bcd.build_today(gov(), signals(), dislo(), gap_engine())
    gap = [s for s in slots if s["kind"] == "gap"][0]
    assert "Japan short gap" in gap["headline"]
    assert "EWJ" in gap["headline"]
    assert all(s["kind"] != "dislocation" for s in slots)


def test_stale_gap_falls_back_to_dislocation_with_label():
    slots = bcd.build_today(gov(), signals(), dislo(), gap_engine("stale"))
    dsl = [s for s in slots if s["kind"] == "dislocation"][0]
    assert "Gap engine stale" in dsl["why"]


def test_dislocation_tiebreak_prefers_fresher():
    rows = [
        {"id": "a", "detector": "D1", "entity": "A", "direction": "long", "severity": 2.0,
         "abs_severity": 2.0, "days_active": 9, "archetype": "A1", "reading": "r", "is_country": True},
        {"id": "b", "detector": "D1", "entity": "B", "direction": "long", "severity": 2.0,
         "abs_severity": 2.0, "days_active": 2, "archetype": "A1", "reading": "r", "is_country": True},
    ]
    country = sorted(rows, key=lambda x: (-x["abs_severity"], x["days_active"]))
    d = {"as_of": "x", "country_ranked": country, "rows": rows, "counts": {}, "total": 2}
    slots = bcd.build_today(gov("green"), [], d)
    assert "B" in [s for s in slots if s["kind"] == "dislocation"][0]["headline"]


# --------------------------------------------------------------------------- #
# §1.3 — the map covers the full 34-country universe
# --------------------------------------------------------------------------- #
def test_map_covers_all_34_countries():
    m = bcd.build_map({}, dislo(), {"scores": {}}, {})
    countries = [t["country"] for reg in m for t in reg["tiles"]]
    assert len(countries) == 34
    assert set(countries) == set(bcd.ALL_COUNTRIES)


def test_map_attaches_dislocation_label_only_to_fired_entities():
    m = bcd.build_map({}, dislo(), {"scores": {}}, {})
    tiles = {t["country"]: t for reg in m for t in reg["tiles"]}
    assert tiles["Netherlands"]["dislocation"] is not None
    assert tiles["Japan"]["dislocation"] is None


def test_map_attaches_gap_metadata():
    m = bcd.build_map({}, dislo(), {"scores": {}}, {}, gap_engine())
    tiles = {t["country"]: t for reg in m for t in reg["tiles"]}
    assert tiles["Japan"]["gap_id"] == "g1"
    assert tiles["Japan"]["gap_ticker"] == "EWJ"
    assert tiles["Japan"]["gap"] == "G2 short EWJ repriced_against"


def test_gap_attention_list_diversifies_classes_after_strongest():
    rows = [
        {"gap_id": "g2a", "gap_class": "G2", "tension_score_current": 0.50},
        {"gap_id": "g2b", "gap_class": "G2", "tension_score_current": 0.49},
        {"gap_id": "g2c", "gap_class": "G2", "tension_score_current": 0.48},
        {"gap_id": "g3a", "gap_class": "G3", "tension_score_current": 0.42},
        {"gap_id": "g4a", "gap_class": "G4", "tension_score_current": 0.35},
        {"gap_id": "g2d", "gap_class": "G2", "tension_score_current": 0.34},
    ]
    got = bcd._diversified_gap_rows(rows, 5)
    assert got[0]["gap_id"] == "g2a"
    assert [x["gap_class"] for x in got[:3]] == ["G2", "G3", "G4"]
    assert len(got) == 5


# --------------------------------------------------------------------------- #
# §1.4 — verdict ordering metadata is self-consistent
# --------------------------------------------------------------------------- #
def test_watch_sorts_before_dead():
    assert bcd.VERDICT_ORDER["WATCH"] < bcd.VERDICT_ORDER["DEAD"]


def test_ic_point_sampler_preserves_edges():
    points = [{"date": f"2026-01-{i:02d}", "ic": i / 100} for i in range(1, 21)]
    got = bcd._sample_points(points, limit=5)
    assert len(got) == 5
    assert got[0] == points[0]
    assert got[-1] == points[-1]


# --------------------------------------------------------------------------- #
# Live-artifact invariants (skipped until cockpit_data.json is generated)
# --------------------------------------------------------------------------- #
live = pytest.mark.skipif(not PAYLOAD.exists(), reason="cockpit_data.json not generated yet")


@live
def test_live_tally_sums_to_registry():
    d = json.loads(PAYLOAD.read_text())
    reg = d["signals"]["registry"]
    assert sum(d["signals"]["tally"].values()) == len(reg)


@live
def test_live_registry_sorted_by_verdict_then_nwt():
    d = json.loads(PAYLOAD.read_text())
    reg = d["signals"]["registry"]
    keys = [(bcd.VERDICT_ORDER.get(s["verdict"], 9), -(s["nw_t"] or -99)) for s in reg]
    assert keys == sorted(keys)


@live
def test_live_registry_uses_latest_run_per_hypothesis():
    d = json.loads(PAYLOAD.read_text())
    ids = [s["id"] for s in d["signals"]["registry"]]
    assert len(ids) == len(set(ids))


@live
def test_live_signal_ic_series_is_bound_when_backfilled():
    d = json.loads(PAYLOAD.read_text())
    reg = d["signals"]["registry"]
    assert reg
    fresh = [s for s in reg if s["ic_series"]["status"] == "fresh"]
    missing = [s for s in reg if s["ic_series"]["status"] != "fresh"]
    assert fresh
    # Two archived harness runs are expected to remain uncharted: the old
    # forward-return lookahead canary and one dead valuation run with no live rows.
    assert len(missing) <= 2
    assert all(s["ic_series"]["horizons"] for s in fresh)


@live
def test_live_governance_overall_is_worst_dimension():
    d = json.loads(PAYLOAD.read_text())
    statuses = {dim["status"] for dim in d["governance"]["dimensions"]}
    overall = d["governance"]["overall"]
    if "red" in statuses:
        assert overall == "red"
    elif "amber" in statuses:
        assert overall == "amber"
    else:
        assert overall == "green"


@live
def test_live_combiner_ic_series_not_fabricated():
    # §1.1 epistemic contract: no IC time series exists -> must be null, not invented
    d = json.loads(PAYLOAD.read_text())
    assert d["combiner"]["ic_series"] is None


@live
def test_live_drawdowns_are_material_only():
    d = json.loads(PAYLOAD.read_text())
    assert all(v < -15 for v in d["drawdowns"].values())


@live
def test_live_gap_engine_contract():
    d = json.loads(PAYLOAD.read_text())
    assert d["gap_engine"]["status"] in {"fresh", "stale", "missing", "empty"}
    if d["gap_engine"]["status"] == "fresh":
        assert d["gap_engine"]["top"]
        top = d["gap_engine"]["top"][0]
        for key in ["gap_id", "entity", "direction", "preferred_ticker",
                    "tension_score_current", "absorption_state", "invalidation_rule"]:
            assert key in top
        assert any(s["kind"] == "gap" for s in d["today"])
        assert "raw_top" in d["gap_engine"]
        classes = {row.get("gap_class") for row in d["gap_engine"]["top"]}
        raw_classes = {row.get("gap_class") for row in d["gap_engine"]["raw_top"]}
        if len(classes) < len(raw_classes):
            # The diversified list may match raw classes on sparse days, but should never
            # be less diverse than the pure tension top.
            raise AssertionError("diversified top lost gap-class breadth")


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
