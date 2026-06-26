from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import cos_mockups.cos_chat_service as svc


client = TestClient(svc.app)
HERE = Path(__file__).resolve().parent


def test_health_serves_cockpit_service():
    response = client.get("/api/cos/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["service"] == "asado-cos-chat"


def test_brazil_routes_to_country_panel():
    response = client.post("/api/cos/chat", json={"message": "Brazil"})
    assert response.status_code == 200
    payload = response.json()
    assert "Brazil" in payload["answer_text"]
    assert {"type": "focus_country", "view": None, "country": "Brazil", "gap_id": None, "signal": None, "layer": None} in payload["ui_actions"]
    assert payload["external_agent"] is None


def test_top_gap_routes_to_gap_panel():
    response = client.post("/api/cos/chat", json={"message": "Where is price not absorbing the data?"})
    assert response.status_code == 200
    payload = response.json()
    assert "gap" in payload["answer_text"].lower()
    assert any(action["type"] == "focus_gap" for action in payload["ui_actions"])


def test_open_ended_question_uses_sanitized_opus(monkeypatch):
    def fake_opus(question, data):
        return "FACT: <script>alert('x')</script>\nINFERENCE: ASADO should explain the gap.", "claude-opus-test"

    monkeypatch.setattr(svc, "call_opus_agent", fake_opus)
    response = client.post("/api/cos/chat", json={"message": "Explain the whole ASADO system", "mode": "research"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["external_agent"] == "opus"
    assert payload["model"] == "claude-opus-test"
    assert "<script>" not in payload["answer_html"]
    assert "&lt;script&gt;" in payload["answer_html"]


def test_invalid_ui_actions_are_rejected():
    data = svc.load_cockpit_data()
    actions = [
        svc.UIAction(type="focus_country", country="Atlantis"),
        svc.UIAction(type="focus_view", view="overview"),
        svc.UIAction(type="set_layer", layer="banana"),
    ]
    valid = svc._validate_actions(data, actions)
    assert [action.type for action in valid] == ["focus_view"]


def test_cockpit_posts_existing_view_state_name():
    source = (HERE / "cockpit.html").read_text()
    live = (HERE / "cockpit_live.html").read_text()
    assert "active_view:CUR?.view||\"overview\"" in source
    assert "active_view:CURRENT" not in source
    assert "active_view:CURRENT" not in live


# --- C1 follow-up (red-team 2026-06-26): evidence packet must not carry the combiner ---
def test_evidence_packet_scrubs_forward_return_combiner():
    import json
    data = svc.load_cockpit_data()
    blob = json.dumps(svc._evidence_packet("Downside if Indonesia keeps falling?", data))
    assert "COMBINER_RIDGE_DAILY_V1" not in blob
    assert "combiner_scores_daily" not in blob
    assert "9.552327532121927e-05" not in blob  # the live leaked value


# --- API deterministic nav routing must match the browser (no Opus spend) ---
def _forbid_opus(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("Opus must NOT be called for a deterministic nav command")
    monkeypatch.setattr(svc, "call_opus_agent", boom)


def _post(msg):
    return client.post("/api/cos/chat", json={"message": msg}).json()


def test_research_desk_routes_local_no_opus(monkeypatch):
    _forbid_opus(monkeypatch)
    r = _post("Research Desk")
    assert r["external_agent"] is None
    assert any(a["type"] == "focus_view" and a["view"] == "desk_discovery" for a in r["ui_actions"])


def test_downside_routes_to_tail_not_country(monkeypatch):
    _forbid_opus(monkeypatch)
    r = _post("Downside if Indonesia keeps falling?")
    assert r["external_agent"] is None
    assert any(a["type"] == "focus_view" and a["view"] == "tail" for a in r["ui_actions"])
    assert not any(a["type"] == "focus_country" for a in r["ui_actions"])


def test_pressure_routes_to_map_layer(monkeypatch):
    _forbid_opus(monkeypatch)
    r = _post("Where is pressure building?")
    assert r["external_agent"] is None
    assert any(a["type"] == "set_layer" and a["layer"] == "dislocation" for a in r["ui_actions"])


def test_full_brief_routes_to_dislo(monkeypatch):
    _forbid_opus(monkeypatch)
    r = _post("open the full brief")
    assert r["external_agent"] is None
    assert any(a["type"] == "focus_view" and a["view"] == "dislo" for a in r["ui_actions"])


def test_real_country_question_still_routes_to_country(monkeypatch):
    # guard: the nav handlers must NOT steal a genuine country query
    _forbid_opus(monkeypatch)
    r = _post("Brazil")
    assert any(a["type"] == "focus_country" and a["country"] == "Brazil" for a in r["ui_actions"])


def test_analytical_question_mentioning_discovery_lab_reaches_opus(monkeypatch):
    # over-route guard: an analytical question that merely MENTIONS "discovery lab"
    # must reach Opus, not be force-routed to the Research Desk (anchored matching).
    def fake_opus(question, data):
        return "FACT: synthesized analytical answer.", "claude-opus-test"
    monkeypatch.setattr(svc, "call_opus_agent", fake_opus)
    r = _post("Which of the discovery lab drafts looks strongest and why?")
    assert r["external_agent"] == "opus"
    assert r["model"] == "claude-opus-test"
