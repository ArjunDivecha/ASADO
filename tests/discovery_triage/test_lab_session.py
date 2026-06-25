"""Tests for the Discovery Lab (PR-5). Offline: fake Anthropic client + injected
snapshot — no API spend, no DB. Verifies look-before-draft, source_look_id linkage,
language gate, falsification requirement, and prospective routing."""
from __future__ import annotations

from types import SimpleNamespace

from scripts.discovery_triage.jsonl_store import read_jsonl
from scripts.discovery_triage.lab_session import run_lab_session


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


def _self_fals():
    return {"strongest_objection": "could be a flow artifact",
            "easiest_way_this_is_leakage": "stale valuation snapshot",
            "first_probe_to_run": "leave-one-crisis-out",
            "condition_under_which_i_would_abandon_this": "sign flips outside exporters"}


def _cards():
    return [
        {"object_type": "contradiction_card", "entity": "Brazil",
         "summary": "FX skew relief while ETF flows stay negative; equity price has not moved.",
         "falsification": {"near_term": ["sovereign CDS widens within 21d"]},
         "mythos_self_falsification": _self_fals()},
        {"object_type": "contradiction_card", "entity": "Mexico",
         "summary": "This is validated alpha and a clear trade recommendation.",  # forbidden vocab
         "falsification": {"near_term": ["x"]}, "mythos_self_falsification": _self_fals()},
        {"object_type": "contradiction_card", "entity": "Chile",
         "summary": "missing its falsification block",  # no falsification -> dropped
         "mythos_self_falsification": _self_fals()},
    ]


def test_lab_session_records_look_and_filters(tmp_path):
    looks = tmp_path / "research_looks.jsonl"
    drafts = tmp_path / "detector_drafts.jsonl"
    snapshot = {"price_state_daily": [{"country": "Brazil", "equity_state_json": "{}"}]}

    res = run_lab_session(
        "cross_surface_contradiction", "2026-06-24",
        client=FakeClient(_cards()), snapshot=snapshot, model_id="claude-opus-4-8",
        looks_path=looks, drafts_path=drafts, drafts_dir=tmp_path,
    )

    # a look was recorded BEFORE drafts; draft links to it
    assert res["look_id"].startswith("L_")
    assert len(read_jsonl(looks)) == 1
    assert len(res["drafts"]) == 1                      # only the clean card survived
    assert res["drafts"][0]["source_look_id"] == res["look_id"]
    assert res["drafts"][0]["family_name"] == "Brazil"

    # null model cutoff -> prospective-only route, tagged on the draft
    assert res["route"] == "prospective_only_unknown_cutoff"
    assert "prospective_only_unknown_cutoff" in res["drafts"][0]["epistemic_status"]

    # two cards were dropped, for the right reasons
    reasons = {d["reason"] for d in res["dropped"]}
    assert reasons == {"forbidden_vocabulary", "missing_falsification_block"}

    # persisted draft round-trips and is the only one
    assert len(read_jsonl(drafts)) == 1
