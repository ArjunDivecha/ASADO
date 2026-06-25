"""Tests for the Research Desk cockpit readers (PR-3). Offline; no loop DB.

Each reader returns [] (empty-state) when its journal is absent — never fabricates —
and build_payload includes the research_desk block even when the loop DB is down.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
from pathlib import Path


def _load():
    p = Path(__file__).resolve().parents[2] / "cos_mockups" / "build_cockpit_data.py"
    loader = importlib.machinery.SourceFileLoader("bcd", str(p))
    spec = importlib.util.spec_from_loader("bcd", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def test_empty_state_no_fabrication(tmp_path):
    m = _load()
    rd = m.build_research_desk(journal_dir=tmp_path)
    assert rd["empty"] is True
    for k in ("discovery_lab", "analog_shelf", "under_triage",
              "blind_rulings", "prospective", "graveyard"):
        assert rd[k] == []


def test_readers_parse_golden_rows_with_badges(tmp_path):
    m = _load()
    (tmp_path / "prospective_queue").mkdir()
    (tmp_path / "prospective_queue" / "prospective_queue.jsonl").write_text(
        json.dumps({"record_kind": "incubator_entry", "claim_id": "C_1",
                    "status": "prospective_only", "measurement_shape": "cross_sectional_rank_ic"}) + "\n",
        encoding="utf-8")
    rows = m.read_prospective(journal_dir=tmp_path)
    assert len(rows) == 1 and rows[0]["claim_id"] == "C_1"
    assert rows[0]["badge"] == "PROSPECTIVE REQUIRED"

    (tmp_path / "drafts").mkdir()
    (tmp_path / "drafts" / "detector_drafts.jsonl").write_text(
        json.dumps({"draft_id": "DRAFT_1", "family_name": "fx", "source_look_id": "L_1",
                    "certification_route": "post_cutoff_holdout_testable"}) + "\n", encoding="utf-8")
    assert m.read_discovery_lab(journal_dir=tmp_path)[0]["badge"] == "POST-CUTOFF HOLDOUT TESTABLE"

    (tmp_path / "graveyard").mkdir()
    (tmp_path / "graveyard" / "graveyard_forward_tracking.jsonl").write_text(
        json.dumps({"record_kind": "graveyard_entry", "claim_id": "C_2",
                    "terminal_or_quarantine_status": "killed_fatal_leakage",
                    "measurement_shape": "single_country_event"}) + "\n", encoding="utf-8")
    assert m.read_graveyard(journal_dir=tmp_path)[0]["badge"] == "KILLED FATAL LEAKAGE"


def test_build_payload_has_research_desk_without_loop_db(monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "_connect", lambda: None)  # simulate loop DB unavailable
    monkeypatch.setattr(m, "read_governance", lambda: {"overall": None, "dimensions": []})
    payload = m.build_payload()
    assert "research_desk" in payload  # present even though DB is down + payload has error
    assert payload.get("error") == "loop DB unavailable"
