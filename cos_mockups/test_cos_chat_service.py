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
