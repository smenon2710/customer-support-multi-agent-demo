from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from agents.account_agent.main import app
from shared.db.models import TicketEvent
from shared.db.session import get_db


def _ticket_payload(subject, description, department="Trading"):
    return {
        "ticket": {
            "ticket_id": "T001",
            "user_email": "user@fintechanalytics.com",
            "department": department,
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


def test_handle_ticket_approves_when_capacity_available(client):
    response = client.post(
        "/handle_ticket",
        json=_ticket_payload("Add user", "Please add 2 new users to Trading."),
    )
    assert response.status_code == 200
    body = response.json()
    assert "Access Request Approved" in body["response"]["content"]
    assert body["escalated"] is False


def test_handle_ticket_requires_approval_over_capacity(client):
    response = client.post(
        "/handle_ticket",
        json=_ticket_payload("Add users", "Please add 500 new users to Trading."),
    )
    assert response.status_code == 200
    body = response.json()
    assert "Manager Approval Required" in body["response"]["content"]
    assert body["escalated"] is True


def test_handle_ticket_records_method_and_intent(client, seeded_db):
    response = client.post(
        "/handle_ticket",
        json=_ticket_payload("Add user", "Please add 2 new users to Trading."),
    )
    assert response.status_code == 200

    event = seeded_db.query(TicketEvent).filter(
        TicketEvent.ticket_id == "T001", TicketEvent.action == "response"
    ).first()
    assert event is not None
    assert event.payload["method"] == "rules"
    assert event.payload["intent"] == "add_users"
