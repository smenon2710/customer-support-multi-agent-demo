from datetime import datetime

from fastapi.testclient import TestClient

from agents.router_agent.main import app

client = TestClient(app)


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


def test_health_reports_status():
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()


def test_route_ticket_classifies_and_routes():
    response = client.post("/route_ticket", json=_ticket())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "routed"
    assert body["assigned_agent"] == "technical_agent"
    assert body["category"] == "technical"
    assert body["priority"] == "critical"
