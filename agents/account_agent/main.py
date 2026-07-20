import logging
from datetime import datetime

import uvicorn
from fastapi import FastAPI

from shared.message_queue import MessageQueue, MessageQueueError
from shared.models import AgentMessage, SupportTicket

try:
    from .account_manager import AccountManager
except ImportError:
    from account_manager import AccountManager

logger = logging.getLogger(__name__)

app = FastAPI(title="Account Management Agent")
mq = MessageQueue()
account_manager = AccountManager()


@app.get("/health")
async def health():
    healthy = mq.is_healthy()
    return {"status": "ok" if healthy else "degraded", "queue_connected": healthy}


@app.post("/handle_ticket")
async def handle_ticket(ticket_data: dict):
    ticket = SupportTicket(**ticket_data["ticket"])

    # Process the account request
    ticket_text = f"{ticket.subject} {ticket.description}"
    response_content = account_manager.process_access_request(ticket_text, ticket.department)

    # Check if escalation is needed
    needs_escalation = "Manager Approval Required" in response_content

    if needs_escalation:
        escalation_msg = {
            "ticket": ticket.model_dump(mode="json"),
            "action": "escalate",
            "escalated_by": "account_agent",
            "reason": "Manager approval required for additional licenses",
            "timestamp": datetime.now().isoformat(),
        }
        try:
            mq.send_message("manager_approval_queue", escalation_msg)
        except MessageQueueError as e:
            logger.error("Failed to queue manager approval for ticket %s: %s", ticket.ticket_id, e)

    # Create response message
    response_message = AgentMessage(
        agent_name="account_agent",
        message_type="response",
        content=response_content,
        timestamp=datetime.now(),
        confidence_score=0.95 if not needs_escalation else 0.8
    )

    return {
        "status": "handled",
        "response": response_message.model_dump(mode="json"),
        "escalated": needs_escalation
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
