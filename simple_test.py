import requests
import json
from datetime import datetime

# Test data
test_ticket = {
    "ticket_id": "T001",
    "user_email": "john.trader@fintechanalytics.com",
    "department": "Trading",
    "subject": "Trading dashboard showing incorrect P&L",
    "description": "The real-time P&L dashboard is showing numbers that don't match our trading system.",
    "created_at": datetime.now().isoformat(),
    "messages": []
}

print("Testing Router Agent...")
try:
    response = requests.post("http://router-agent:8001/route_ticket", json=test_ticket)
    print("Router Response:", response.status_code)
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Router Agent Error: {e}")

print("\nTesting Technical Agent...")
try:
    response = requests.post("http://technical-agent:8002/handle_ticket", json={"ticket": test_ticket})
    print("Technical Response:", response.status_code)
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Technical Agent Error: {e}")
