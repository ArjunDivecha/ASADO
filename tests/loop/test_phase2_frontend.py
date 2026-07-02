"""
=============================================================================
SCRIPT NAME: tests/loop/test_phase2_frontend.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/scripts/loop/build_family_ranks.py
    rank_family() orientation rules under test (loaded by path, no DB touched).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/scripts/loop/build_fable_connections.py
    scrub() custody filter under test (loaded by path, no API call made).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/cos_mockups/build_cockpit_data.py
    read_consensus / build_edge_board / read_fable under test (in-memory DuckDB
    + monkeypatched family metadata; the real loop DB is never opened).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/cos_mockups/cos_chat_service.py
    deterministic_answer() Phase 2 intents under test (synthetic payload dicts).

OUTPUT FILES:
- none (pytest assertions only; nothing is written to disk)

VERSION: 1.0
LAST UPDATED: 2026-07-01
AUTHOR: Arjun Divecha (agent session, Frontend Alpha Rethink Phase 2)

DESCRIPTION:
Offline unit tests for the Phase 2 frontend redesign (PRD P1 Edge Board,
P2 Consensus Matrix, Fable's Desk). Verifies:
- family rank orientation (registered direction -> rank 1 = strongest long lean),
- agreement voting excludes non-voting columns (combiner / ToT) and never
  fabricates cells for out-of-universe countries,
- the Edge Board selector: governance exception first, repriced_against gaps
  excluded, >=3-vote consensus threshold, entity|direction dedupe, cap 5,
- Fable connections are always re-labelled CONJECTURE and the custody scrub
  strips optimizer-output keys before anything reaches the model,
- chat-service deterministic intents route to the new views.

DEPENDENCIES:
- pytest, pandas, duckdb (all in the project venv)

USAGE:
  ./venv/bin/python -m pytest tests/loop/test_phase2_frontend.py -q

NOTES:
- All modules are loaded via SourceFileLoader (same pattern as
  tests/discovery_triage/test_cockpit_readers.py) so the tests exercise the
  shipped files without package installation.
=============================================================================
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

BASE = Path(__file__).resolve().parents[2]


def _load(path: Path, name: str):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    # register BEFORE exec so pydantic can resolve postponed annotations
    # (cos_chat_service uses `from __future__ import annotations` + Literal)
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


def _bcd():
    return _load(BASE / "cos_mockups" / "build_cockpit_data.py", "bcd_p2")


# --------------------------------------------------------------------------- #
# build_family_ranks.rank_family — registered-direction orientation
# --------------------------------------------------------------------------- #
def test_rank_family_higher_is_better():
    m = _load(BASE / "scripts" / "loop" / "build_family_ranks.py", "bfr_p2")
    tidy = pd.DataFrame({
        "date": pd.to_datetime(["2026-06-30"] * 5),
        "country": ["A", "B", "C", "D", "E"],
        "score": [5.0, 3.0, 1.0, -1.0, -3.0],
    })
    out = m.rank_family(tidy, {"key": "fam", "direction": "higher_is_better"})
    by = out.set_index("country")["rank"]
    assert by["A"] == 1 and by["E"] == 5
    assert (out["universe_n"] == 5).all()


def test_rank_family_lower_is_better_flips():
    m = _load(BASE / "scripts" / "loop" / "build_family_ranks.py", "bfr_p2b")
    tidy = pd.DataFrame({
        "date": pd.to_datetime(["2026-06-30"] * 5),
        "country": ["A", "B", "C", "D", "E"],
        "score": [5.0, 3.0, 1.0, -1.0, -3.0],
    })
    out = m.rank_family(tidy, {"key": "fam", "direction": "lower_is_better"})
    by = out.set_index("country")["rank"]
    assert by["E"] == 1 and by["A"] == 5


def test_rank_family_drops_thin_cross_sections():
    m = _load(BASE / "scripts" / "loop" / "build_family_ranks.py", "bfr_p2c")
    tidy = pd.DataFrame({
        "date": pd.to_datetime(["2026-06-30"] * 3),
        "country": ["A", "B", "C"],
        "score": [1.0, 2.0, 3.0],
    })
    out = m.rank_family(tidy, {"key": "fam", "direction": "higher_is_better"})
    assert out.empty  # < 5 countries is not an honest cross-section


# --------------------------------------------------------------------------- #
# read_consensus — voting rules and universe honesty
# --------------------------------------------------------------------------- #
_META = {
    "leadlag": {"label": "Lead-lag", "verdict": "WEAK", "ic": 0.05, "nw_t": 8.0,
                "horizon": "5d", "direction": "higher_is_better",
                "count_in_agreement": True, "note": "", "hypothesis_id": "H_X"},
    "combiner": {"label": "Ridge combiner", "verdict": "WEAK", "ic": 0.057, "nw_t": 10.7,
                 "horizon": "5d", "direction": "higher_is_better",
                 "count_in_agreement": False, "note": "outcome-trained", "hypothesis_id": "H_Y"},
}


def _consensus_con():
    con = duckdb.connect(":memory:")
    rows = []
    # 5-country leadlag column (voting) + combiner column (non-voting)
    for fam in ("leadlag", "combiner"):
        for i, c in enumerate(["A", "B", "C", "D", "E"]):
            # combiner ranks are deliberately the REVERSE of leadlag's
            rank = i + 1 if fam == "leadlag" else 5 - i
            rows.append(("2026-06-30", fam, c, float(10 - rank), 0.0, rank, 5))
    df = pd.DataFrame(rows, columns=["date", "family", "country", "score",
                                     "oriented_score", "rank", "universe_n"])
    df["date"] = pd.to_datetime(df["date"])
    con.execute("CREATE TABLE family_ranks_daily AS SELECT * FROM df")
    return con


def test_consensus_votes_exclude_nonvoting_columns(monkeypatch):
    m = _bcd()
    monkeypatch.setattr(m, "_family_meta", lambda: _META)
    out = m.read_consensus(_consensus_con())
    assert out["status"] == "fresh"
    a = out["agreement"]["A"]
    # quintile of 5 = 1: A is leadlag rank 1 -> one long vote; the combiner
    # ranks A dead-last but MUST NOT create a short vote or a conflict.
    assert a["eligible"] == 1 and a["long"] == 1 and a["short"] == 0
    assert a["conflict"] is False
    # the combiner cell itself is still present for display
    assert out["matrix"]["A"]["combiner"]["rank"] == 5


def test_consensus_no_fake_cells_outside_universe(monkeypatch):
    m = _bcd()
    monkeypatch.setattr(m, "_family_meta", lambda: _META)
    out = m.read_consensus(_consensus_con())
    assert "Z" not in out["matrix"]  # never invents a country
    fams = {f["key"]: f for f in out["families"]}
    assert fams["combiner"]["count_in_agreement"] is False


def test_consensus_missing_table_is_honest():
    m = _bcd()
    out = m.read_consensus(duckdb.connect(":memory:"))
    assert out["status"] == "missing" and out["matrix"] == {}


# --------------------------------------------------------------------------- #
# build_edge_board — selection contract
# --------------------------------------------------------------------------- #
def _gov(overall="amber"):
    return {"overall": overall,
            "dimensions": [{"name": "cross_source_minimal", "status": "amber",
                            "detail": "partial by design", "amber_by_design": True}]}


def _gap(entity, direction, tension, absorption="unabsorbed", gid=None):
    return {"gap_id": gid or f"G_{entity}_{direction}", "entity": entity,
            "direction": direction, "gap_class": "G2", "status": "open",
            "absorption_state": absorption, "tension_score_current": tension,
            "tension_score_at_open": 0.5, "days_active": 3,
            "preferred_ticker": "EWX", "horizon_bucket": "21d",
            "mechanism_text": "test gap", "invalidation_rule": "reprices"}


def test_edge_board_governance_first_and_repriced_excluded():
    m = _bcd()
    gaps = {"status": "fresh", "as_of": "2026-06-30",
            "top": [_gap("Chile", "long", 0.6),
                    _gap("U.K.", "short", 0.9, absorption="repriced_against")]}
    board = m.build_edge_board(_gov(), gaps, {}, [], [])
    kinds = [s["kind"] for s in board["slots"]]
    assert kinds[0] == "governance"
    entities = [s.get("entity") for s in board["slots"]]
    assert "Chile" in entities and "U.K." not in entities  # repriced_against never a card


def test_edge_board_consensus_needs_three_votes_no_conflict():
    m = _bcd()
    consensus = {"as_of": "2026-06-30", "agreement": {
        "Brazil": {"long": 3, "short": 0, "eligible": 6, "edge": 0.5,
                   "long_families": ["a", "b", "c"], "short_families": [], "conflict": False},
        "Japan": {"long": 2, "short": 0, "eligible": 6, "edge": 0.33,
                  "long_families": ["a", "b"], "short_families": [], "conflict": False},
        "Korea": {"long": 3, "short": 1, "eligible": 6, "edge": 0.33,
                  "long_families": ["a", "b", "c"], "short_families": ["d"], "conflict": True},
    }}
    board = m.build_edge_board({"overall": "green", "dimensions": []},
                               {"status": "missing"}, consensus, [], [])
    entities = [s.get("entity") for s in board["slots"]]
    assert "Brazil" in entities          # 3 clean votes -> card
    assert "Japan" not in entities       # only 2 votes
    assert "Korea" not in entities       # conflicted -> dossier material, not a card


def test_edge_board_dedupes_and_caps_at_five():
    m = _bcd()
    gaps = {"status": "fresh", "as_of": "2026-06-30",
            "top": [_gap("Chile", "long", 0.9, gid="G1"),
                    _gap("Chile", "long", 0.4, gid="G2")]}  # same entity|direction
    events = [{"kind": "rating_downgrade", "entity": f"C{i}", "direction": "short",
               "date": "2026-06-29", "detail": "test", "study": "s"} for i in range(8)]
    board = m.build_edge_board(_gov(), gaps, {}, events, [])
    assert len(board["slots"]) == 5
    chile = [s for s in board["slots"] if s.get("entity") == "Chile"]
    assert len(chile) == 1 and "G1" in chile[0]["source"] or chile[0]["route"]["gap_id"] == "G1"


# --------------------------------------------------------------------------- #
# Fable surface — CONJECTURE labelling + custody scrub
# --------------------------------------------------------------------------- #
def test_read_fable_forces_conjecture_tag(monkeypatch, tmp_path):
    m = _bcd()
    art = tmp_path / "connections_latest.json"
    art.write_text(json.dumps({
        "as_of": "2026-06-30", "model": "claude-fable-5",
        "connections": [{"title": "t", "epistemic_tag": "FACT"}],  # hostile input
    }))
    monkeypatch.setattr(m, "FABLE_JSON", art)
    out = m.read_fable()
    assert out["status"] == "fresh"
    assert out["connections"][0]["epistemic_tag"] == "CONJECTURE"


def test_read_fable_missing_artifact(monkeypatch, tmp_path):
    m = _bcd()
    monkeypatch.setattr(m, "FABLE_JSON", tmp_path / "nope.json")
    out = m.read_fable()
    assert out["status"] == "missing" and out["connections"] == []


def test_fable_packet_scrub_strips_optimizer_keys():
    m = _load(BASE / "scripts" / "loop" / "build_fable_connections.py", "bfc_p2")
    dirty = {
        "combiner_scores": {"Brazil": 1.0},
        "nested": {"factor_returns_daily": [1, 2], "keep_me": "ok",
                   "1MRet": 0.02, "trailing_12m": 0.1},
        "list": [{"forward_return": 1.0, "fine": 2.0}],
    }
    clean = m.scrub(dirty)
    assert "combiner_scores" not in clean
    assert "factor_returns_daily" not in clean["nested"]
    assert "1MRet" not in clean["nested"]
    assert clean["nested"]["keep_me"] == "ok"
    assert clean["nested"]["trailing_12m"] == 0.1     # trailing stats survive
    assert clean["list"][0] == {"fine": 2.0}


# --------------------------------------------------------------------------- #
# cos_chat_service — deterministic Phase 2 intents
# --------------------------------------------------------------------------- #
def _chat():
    return _load(BASE / "cos_mockups" / "cos_chat_service.py", "ccs_p2")


_CHAT_DATA = {
    "meta": {"generated_ts": "2026-07-01T00:00:00"},
    "governance": {"overall": "amber", "dimensions": []},
    "gap_engine": {"status": "fresh", "as_of": "2026-06-30", "top": [], "by_country": {}},
    "signals": {"registry": [], "tally": {}},
    "countries": {}, "map": [],
    "edge_board": {"as_of": "2026-06-30",
                   "slots": [{"headline": "H1", "why": "W1"}, {"headline": "H2", "why": "W2"}]},
    "consensus": {"status": "fresh", "as_of": "2026-06-30",
                  "families": [{"key": "leadlag"}],
                  "leaders": {"long": [{"country": "Brazil", "votes": 3}], "short": []},
                  "conflicts": [{"country": "Korea"}], "agreement": {}, "matrix": {}},
    "fable": {"status": "fresh", "as_of": "2026-06-30", "connections": [{"title": "t"}]},
}


def _views(resp):
    return [a.view for a in resp.ui_actions if a.type == "focus_view"]


def test_chat_edge_board_intent():
    m = _chat()
    resp = m.deterministic_answer("the edge board", _CHAT_DATA)
    assert resp is not None and "edge" in _views(resp)


def test_chat_consensus_intent_reports_leader():
    m = _chat()
    resp = m.deterministic_answer("consensus matrix", _CHAT_DATA)
    assert resp is not None and "consensus" in _views(resp)
    assert "Brazil" in resp.answer_text


def test_chat_fable_intent_is_conjecture_labelled():
    m = _chat()
    resp = m.deterministic_answer("fable's desk", _CHAT_DATA)
    assert resp is not None and "fable" in _views(resp)
    assert "CONJECTURE" in resp.answer_text


def test_chat_today_lands_on_edge_board_when_slots_exist():
    m = _chat()
    resp = m.deterministic_answer("what should I care about today", _CHAT_DATA)
    assert resp is not None and "edge" in _views(resp)
    assert "H1" in resp.answer_text


def test_chat_today_falls_back_without_slots():
    m = _chat()
    data = dict(_CHAT_DATA)
    data["edge_board"] = {"slots": []}
    data["today"] = [{"headline": "T1", "why": "w"}]
    resp = m.deterministic_answer("what should I care about today", data)
    assert resp is not None and "overview" in _views(resp)


def test_chat_validates_edge_layer_action():
    m = _chat()
    acts = m._validate_actions(_CHAT_DATA, [
        m.UIAction(type="set_layer", layer="edge"),
        m.UIAction(type="focus_view", view="fable"),
        m.UIAction(type="focus_view", view="not_a_view"),
    ])
    assert [(a.type, a.layer or a.view) for a in acts] == [
        ("set_layer", "edge"), ("focus_view", "fable")]
