"""Tests for the Research Desk cockpit readers (adopted Codex build_cockpit_data).
Offline; monkeypatches read_jsonl. Verifies empty-state (no fabrication) and that
the rich card content (falsification / self-falsification) survives into the payload."""
from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path


def _load():
    p = Path(__file__).resolve().parents[2] / "cos_mockups" / "build_cockpit_data.py"
    loader = importlib.machinery.SourceFileLoader("bcd", str(p))
    spec = importlib.util.spec_from_loader("bcd", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


_DRAFT = {
    "draft_id": "DRAFT_20260625_001", "family_name": "ChinaA", "members": ["a 9pt T2-vs-ASHR basis"],
    "certification_route": "prospective_only_unknown_cutoff",
    "epistemic_status": ["unvalidated", "tool_outcome_blind", "prospective_only_unknown_cutoff"],
    "falsification": {"near_term": ["the basis reconverges within 10 days"]},
    "mythos_self_falsification": {"strongest_objection": "likely a CNY/index-construction artifact",
                                  "first_probe_to_run": "decompose the basis into FX vs NAV",
                                  "condition_under_which_i_would_abandon_this": ">70% is mechanical"},
    "recorded_ts": "2026-06-25T09:00:00-07:00",
}

_PANELS = ("discovery_lab", "analog_shelf", "under_triage", "blind_rulings", "prospective", "graveyard")


def test_discovery_lab_preserves_rich_content(monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "read_jsonl", lambda p: [_DRAFT])
    rows = m.read_discovery_lab()
    assert rows and rows[0]["id"] == "DRAFT_20260625_001"
    assert rows[0]["title"] == "ChinaA"
    # the actual insight is NOT stripped (Codex review P2)
    assert rows[0]["falsification"].get("near_term")
    assert rows[0]["self_falsification"].get("strongest_objection")


def test_empty_state_no_fabrication(monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "read_jsonl", lambda p: [])
    assert m.read_discovery_lab() == []
    rd = m.read_research_desk()
    for k in _PANELS:
        assert rd.get(k) == []


def test_research_desk_has_all_panels(monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "read_jsonl", lambda p: [])
    rd = m.read_research_desk()
    for k in _PANELS:
        assert k in rd
