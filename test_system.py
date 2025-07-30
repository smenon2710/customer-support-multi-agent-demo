from shared.models import SupportTicket
from shared.orchestrator import AgentOrchestrator
from datetime import datetime
import json
import uuid

# Custom JSON encoder for datetime objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# Sample test tickets
test_tickets = [
    SupportTicket(
        ticket_id="T001",
        user_email="john.trader@fintechanalytics.com",
        department="Trading",
        subject="Trading dashboard showing incorrect P&L",
        description="The real-time P&L dashboard is showing numbers that don't match our trading system. This is affecting our risk calculations.",
        created_at=datetime.now()
    ),
    SupportTicket(
        ticket_id="T002", 
        user_email="mike.compliance@fintechanalytics.com",
        department="Compliance",
        subject="Need access for 3 new team members",
        description="We hired 3 new compliance analysts who need Tableau access for regulatory reporting.",
        created_at=datetime.now()
    )
]

if __name__ == "__main__":
    orchestrator = AgentOrchestrator()
    
    for ticket in test_tickets:
        print(f"\n{'='*50}")
        print(f"Processing Ticket: {ticket.ticket_id}")
        print(f"Subject: {ticket.subject}")
        print(f"{'='*50}")
        
        result = orchestrator.process_support_ticket(ticket)
        # Use the custom encoder to handle datetime objects
        print(json.dumps(result, indent=2, cls=DateTimeEncoder))
