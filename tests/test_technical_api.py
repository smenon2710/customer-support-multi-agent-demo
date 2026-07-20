from datetime import datetime

from fastapi.testclient import TestClient

from agents.technical_agent.main import app

client = TestClient(app)


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


def test_health_reports_status():
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()


def test_handle_ticket_matches_known_issue():
    response = client.post(
        "/handle_ticket",
        json=_ticket_payload("Dashboard slow", "The dashboard is slow and keeps loading."),
    )
    assert response.status_code == 200
    body = response.json()
    assert "Technical Solution Found" in body["response"]["content"]
    assert body["escalated"] is False


def test_handle_ticket_escalates_unknown_issue():
    response = client.post(
        "/handle_ticket",
        json=_ticket_payload("Random request", "Something completely unrelated to Tableau."),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["escalated"] is True
