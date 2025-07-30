from fastapi import FastAPI
from shared.models import SupportTicket, AgentMessage
from shared.message_queue import MessageQueue
from datetime import datetime
import json
import uvicorn

app = FastAPI(title="Technical Support Agent")
mq = MessageQueue()

class TechnicalKnowledgeBase:
    def __init__(self):
        self.solutions = {
            "dashboard_loading": {
                "symptoms": ["slow", "loading", "timeout", "dashboard"],
                "solution": "1. Check Tableau Server status\n2. Clear browser cache\n3. Reduce dashboard complexity\n4. Contact IT if server issues persist",
                "escalate": False
            },
            "database_connection": {
                "symptoms": ["connection", "database", "timeout", "oracle", "sql"],
                "solution": "1. Verify VPN connection\n2. Check database credentials\n3. Test connection from Tableau Desktop\n4. Contact DBA team if connectivity issues persist",
                "escalate": True
            },
            "data_refresh": {
                "symptoms": ["refresh", "extract", "data", "outdated"],
                "solution": "1. Check data source connection\n2. Verify refresh schedule\n3. Review extract logs\n4. Manually trigger refresh if needed",
                "escalate": False
            },
            "visualization_error": {
                "symptoms": ["chart", "visualization", "error", "display"],
                "solution": "1. Check calculated fields\n2. Verify data types\n3. Review filters and parameters\n4. Recreate visualization if corrupted",
                "escalate": False
            }
        }

    def find_solution(self, ticket_text: str) -> dict:
        text = ticket_text.lower()
        best_match = None
        max_matches = 0
        
        for issue_type, issue_data in self.solutions.items():
            matches = sum(1 for symptom in issue_data["symptoms"] if symptom in text)
            if matches > max_matches:
                max_matches = matches
                best_match = issue_data
        
        return best_match if max_matches > 0 else None

kb = TechnicalKnowledgeBase()

@app.post("/handle_ticket")
async def handle_ticket(ticket_data: dict):
    ticket = SupportTicket(**ticket_data["ticket"])
    
    # Search knowledge base
    ticket_text = f"{ticket.subject} {ticket.description}"
    solution = kb.find_solution(ticket_text)
    
    if solution:
        response_content = f"**Technical Solution Found:**\n\n{solution['solution']}"
        
        if solution['escalate']:
            response_content += "\n\n⚠️ **Escalation Required:** This issue requires specialized database team assistance."
            
            # Send escalation message
            escalation_msg = {
                "ticket": ticket.dict(),
                "action": "escalate",
                "escalated_by": "technical_agent",
                "reason": "Database connectivity issue requiring DBA team",
                "timestamp": datetime.now().isoformat()
            }
            mq.send_message("escalation_queue", escalation_msg)
    else:
        response_content = "I need to research this issue further. A senior technical specialist will follow up within 2 hours."
        
        # Send to escalation queue
        escalation_msg = {
            "ticket": ticket.dict(),
            "action": "escalate",
            "escalated_by": "technical_agent",
            "reason": "Complex technical issue requiring specialist review",
            "timestamp": datetime.now().isoformat()
        }
        mq.send_message("escalation_queue", escalation_msg)
    
    # Create response message
    response_message = AgentMessage(
        agent_name="technical_agent",
        message_type="response",
        content=response_content,
        timestamp=datetime.now(),
        confidence_score=0.9 if solution and not solution['escalate'] else 0.6
    )
    
    return {
        "status": "handled",
        "response": response_message.dict(),
        "escalated": solution['escalate'] if solution else True
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
