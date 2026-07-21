import logging
from datetime import datetime

import uvicorn
from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from shared.db.repository import get_or_create_ticket, record_escalation, record_event, record_resolution
from shared.db.session import get_db, init_db, is_db_healthy
from shared.message_queue import MessageQueue, MessageQueueError
from shared.models import AgentMessage, SupportTicket
from shared.tableau_service import SimulatedTableauBackend

try:
    from .account_manager import AccountManager
    from .intent import extract_intent
except ImportError:
    from account_manager import AccountManager
    from intent import extract_intent

logger = logging.getLogger(__name__)

app = FastAPI(title="Account Management Agent")
mq = MessageQueue()
init_db()


@app.get("/health")
async def health():
    queue_healthy = mq.is_healthy()
    db_healthy = is_db_healthy()
    return {
        "status": "ok" if queue_healthy and db_healthy else "degraded",
        "queue_connected": queue_healthy,
        "db_connected": db_healthy,
    }


@app.post("/handle_ticket")
async def handle_ticket(ticket_data: dict, db: Session = Depends(get_db)):
    ticket = SupportTicket(**ticket_data["ticket"])
    get_or_create_ticket(db, ticket, assigned_agent="account_agent")

    # Extract intent — rules first, LLM only for genuinely ambiguous text (see intent.py).
    ticket_text = f"{ticket.subject} {ticket.description}"
    intent, method = extract_intent(ticket_text)

    # Execution is always deterministic — the model never decides whether licenses
    # exist, it only helped parse what the user asked for.
    backend = SimulatedTableauBackend(db)
    account_manager = AccountManager(backend)
    response_content = account_manager.build_response(intent, ticket.department)

    # Check if escalation is needed
    needs_escalation = "Manager Approval Required" in response_content

    if needs_escalation:
        reason = "Manager approval required for additional licenses"
        record_escalation(db, ticket.ticket_id, "account_agent", reason, "manager_approval_queue")

        escalation_msg = {
            "ticket": ticket.model_dump(mode="json"),
            "action": "escalate",
            "escalated_by": "account_agent",
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        }
        try:
            mq.send_message("manager_approval_queue", escalation_msg)
        except MessageQueueError as e:
            logger.error("Failed to queue manager approval for ticket %s: %s", ticket.ticket_id, e)

    record_event(db, ticket.ticket_id, "account_agent", "response", {
        "content": response_content,
        "escalated": needs_escalation,
        "method": method,
        "intent": intent.action,
    })
    record_resolution(db, ticket.ticket_id, response_content, needs_escalation)
    db.commit()

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
