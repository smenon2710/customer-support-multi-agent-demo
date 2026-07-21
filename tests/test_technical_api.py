from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from agents.technical_agent.main import app
from shared import config
from shared.db.models import TicketEvent
from shared.db.session import get_db


def _ticket_payload(subject, description):
    return {
        "ticket": {
            "ticket_id": "T001",
            "user_email": "user@fintechanalytics.com",
            "department": "Trading",
            "subject": subject,
            "description": description,
            "created_at": datetime.now().isoformat(),
            "messages": [],
        }
    }


@pytest.fixture()
def client(seeded_db):
    app.dependency_overrides[get_db] = lambda: seeded_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_reports_status(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()


def test_handle_ticket_matches_known_issue(client):
    response = client.post(
        "/handle_ticket",
        json=_ticket_payload("Dashboard slow", "The dashboard is slow and keeps loading."),
    )
    assert response.status_code == 200
    body = response.json()
    assert "Technical Solution Found" in body["response"]["content"]
    assert body["escalated"] is False


def test_handle_ticket_escalates_unknown_issue(client):
    response = client.post(
        "/handle_ticket",
        json=_ticket_payload("Random request", "Something completely unrelated to Tableau."),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["escalated"] is True


def test_handle_ticket_records_method_and_articles_used(client, seeded_db):
    response = client.post(
        "/handle_ticket",
        json=_ticket_payload("Dashboard slow", "The dashboard is slow and keeps loading."),
    )
    assert response.status_code == 200

    event = seeded_db.query(TicketEvent).filter(
        TicketEvent.ticket_id == "T001", TicketEvent.action == "response"
    ).first()
    assert event is not None
    # No OPENROUTER_API_KEY is configured in the test environment, so this always
    # exercises the rules fallback.
    assert event.payload["method"] == "rules"
    assert "Dashboard Loading Issues" in event.payload["kb_articles_used"]


def test_second_ticket_with_same_subject_uses_cache(client, seeded_db):
    first = client.post(
        "/handle_ticket",
        json=_ticket_payload("Dashboard slow", "The dashboard is slow and keeps loading."),
    )
    assert first.status_code == 200

    second_payload = _ticket_payload("Dashboard slow", "Completely different description text.")
    second_payload["ticket"]["ticket_id"] = "T002"
    second = client.post("/handle_ticket", json=second_payload)
    assert second.status_code == 200
    assert second.json()["response"]["content"] == first.json()["response"]["content"]

    event = seeded_db.query(TicketEvent).filter(
        TicketEvent.ticket_id == "T002", TicketEvent.action == "response"
    ).first()
    assert event.payload["method"] == "cache"


def test_handle_ticket_requires_token_when_configured(client, monkeypatch):
    monkeypatch.setattr(config, "INTERNAL_API_TOKEN", "secret123")
    response = client.post(
        "/handle_ticket",
        json=_ticket_payload("Dashboard slow", "The dashboard is slow and keeps loading."),
    )
    assert response.status_code == 401


def test_handle_ticket_accepts_correct_token(client, monkeypatch):
    monkeypatch.setattr(config, "INTERNAL_API_TOKEN", "secret123")
    response = client.post(
        "/handle_ticket",
        json=_ticket_payload("Dashboard slow", "The dashboard is slow and keeps loading."),
        headers={"X-Internal-Token": "secret123"},
    )
    assert response.status_code == 200
