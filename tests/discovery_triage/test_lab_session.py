"""Tests for the Discovery Lab (PR-5 + merge strict contract). Offline: fake Anthropic
client + injected snapshot. Verifies look-before-draft, source_look_id linkage, the
strict canonical schema (fatal_if/must_check/strongest_counterargument), legacy
normalization, and prospective routing."""
from __future__ import annotations

from types import SimpleNamespace

from scripts.discovery_triage.jsonl_store import read_jsonl
from scripts.discovery_triage.lab_session import normalize_card, run_lab_session, validate_card


class _FakeMessages:
    def __init__(self, resp):
        self._resp = resp

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self._resp


class FakeClient:
    def __init__(self, cards):
        block = SimpleNamespace(type="tool_use", name="emit_discovery_cards",
                                input={"cards": cards})
        self.messages = _FakeMessages(SimpleNamespace(content=[block], stop_reason="tool_use"))


def _sf():
    return {"strongest_counterargument": "could be a CNY/index-construction artifact",
            "what_would_change_my_mind": ["decompose basis: <70% mechanical"]}


def _cards():
    return [
        {  # valid canonical card
            "object_type": "detector_family_draft", "family_name": "Brazil",
            "summary": "FX skew relief while ETF flows stay negative; price has not moved.",
            "members": ["fx_skew_relief + etf_outflow", "cds_stable + flow_capitulation"],
            "falsification": {"fatal_if": ["sovereign CDS widens within 21d"],
                              "must_check": ["leave-one-crisis-out", "country jackknife"]},
            "mythos_self_falsification": _sf()},
        {  # forbidden vocabulary -> dropped
            "object_type": "detector_family_draft", "family_name": "Mexico",
            "summary": "This is validated alpha and a clear trade recommendation.",
            "members": ["x"], "falsification": {"fatal_if": ["a"], "must_check": ["b"]},
            "mythos_self_falsification": _sf()},
        {  # missing must_check -> dropped by strict validation
            "object_type": "detector_family_draft", "family_name": "Chile",
            "summary": "incomplete falsification", "members": ["y"],
            "falsification": {"fatal_if": ["only fatal_if, no must_check"]},
            "mythos_self_falsification": _sf()},
    ]


def test_normalize_card_migrates_legacy_shape():
    legacy = {"entity": "ChinaA", "summary": "9pt basis",
              "falsification": {"near_term": ["reconverges"], "structural": ["one country only"]},
              "mythos_self_falsification": {"strongest_objection": "FX artifact",
                                            "condition_under_which_i_would_abandon_this": ">70% mechanical"}}
    c = normalize_card(legacy)
    assert c["family_name"] == "ChinaA"
    assert c["falsification"]["fatal_if"] == ["reconverges"]
    assert c["falsification"]["must_check"] == ["one country only"]
    assert c["mythos_self_falsification"]["strongest_counterargument"] == "FX artifact"
    assert c["mythos_self_falsification"]["what_would_change_my_mind"] == [">70% mechanical"]
    assert validate_card(c) is None


def test_lab_session_records_look_and_strict_filters(tmp_path):
    looks = tmp_path / "research_looks.jsonl"
    drafts = tmp_path / "detector_drafts.jsonl"
    snapshot = {"price_state_daily": [{"country": "Brazil", "equity_state_json": "{}"}]}

    res = run_lab_session(
        "cross_surface_contradiction", "2026-06-24",
        client=FakeClient(_cards()), snapshot=snapshot, model_id="claude-opus-4-8",
        looks_path=looks, drafts_path=drafts, drafts_dir=tmp_path,
    )

    assert res["look_id"].startswith("L_")
    assert len(read_jsonl(looks)) == 1
    assert len(res["drafts"]) == 1
    d = res["drafts"][0]
    assert d["source_look_id"] == res["look_id"]
    assert d["family_name"] == "Brazil"
    assert d["falsification"]["fatal_if"] and d["falsification"]["must_check"]
    assert d["mythos_self_falsification"]["strongest_counterargument"]

    assert res["route"] == "prospective_only_unknown_cutoff"
    assert "prospective_only_unknown_cutoff" in d["epistemic_status"]

    reasons = {x["reason"] for x in res["dropped"]}
    assert any("forbidden" in r for r in reasons)
    assert any("must_check" in r for r in reasons)
    assert len(read_jsonl(drafts)) == 1
