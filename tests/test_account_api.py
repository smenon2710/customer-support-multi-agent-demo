from datetime import datetime

from fastapi.testclient import TestClient

from agents.account_agent.main import app

client = TestClient(app)


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


def test_health_reports_status():
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()


def test_handle_ticket_approves_when_capacity_available():
    response = client.post(
        "/handle_ticket",
        json=_ticket_payload("Add user", "Please add 2 new users to Trading."),
    )
    assert response.status_code == 200
    body = response.json()
    assert "Access Request Approved" in body["response"]["content"]
    assert body["escalated"] is False


def test_handle_ticket_requires_approval_over_capacity():
    response = client.post(
        "/handle_ticket",
        json=_ticket_payload("Add users", "Please add 500 new users to Trading."),
    )
    assert response.status_code == 200
    body = response.json()
    assert "Manager Approval Required" in body["response"]["content"]
    assert body["escalated"] is True
