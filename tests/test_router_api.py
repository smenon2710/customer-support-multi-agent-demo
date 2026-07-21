from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from agents.router_agent.main import app
from shared import config
from shared.db.models import Ticket, TicketEvent
from shared.db.session import get_db


def _ticket(**overrides):
    ticket = {
        "ticket_id": "T001",
        "user_email": "trader@fintechanalytics.com",
        "department": "Trading",
        "subject": "Trading dashboard down",
        "description": "Dashboard is not loading and showing a connection timeout.",
        "created_at": datetime.now().isoformat(),
        "messages": [],
    }
    ticket.update(overrides)
    return ticket


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_reports_status(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()


def test_route_ticket_classifies_and_routes(client, db_session):
    response = client.post("/route_ticket", json=_ticket())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "routed"
    assert body["assigned_agent"] == "technical_agent"
    assert body["category"] == "technical"
    assert body["priority"] == "critical"

    db_ticket = db_session.query(Ticket).filter(Ticket.ticket_id == "T001").first()
    assert db_ticket is not None
    assert db_ticket.status == "open"
    assert db_ticket.assigned_agent == "technical_agent"

    events = db_session.query(TicketEvent).filter(TicketEvent.ticket_id == "T001").all()
    assert len(events) == 1
    assert events[0].action == "classification"


def test_route_ticket_requires_token_when_configured(client, monkeypatch):
    monkeypatch.setattr(config, "INTERNAL_API_TOKEN", "secret123")
    response = client.post("/route_ticket", json=_ticket())
    assert response.status_code == 401


def test_route_ticket_accepts_correct_token(client, monkeypatch):
    monkeypatch.setattr(config, "INTERNAL_API_TOKEN", "secret123")
    response = client.post(
        "/route_ticket", json=_ticket(), headers={"X-Internal-Token": "secret123"}
    )
    assert response.status_code == 200
