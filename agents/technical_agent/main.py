import logging
from datetime import datetime

import uvicorn
from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from shared.db.repository import record_escalation, record_event, record_resolution, get_or_create_ticket
from shared.db.session import get_db, init_db, is_db_healthy
from shared.message_queue import MessageQueue, MessageQueueError
from shared.models import AgentMessage, SupportTicket

try:
    from .technical_kb import TechnicalKnowledgeBase
except ImportError:
    from technical_kb import TechnicalKnowledgeBase

logger = logging.getLogger(__name__)

app = FastAPI(title="Technical Support Agent")
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


def _notify_escalation(ticket: SupportTicket, reason: str) -> None:
    escalation_msg = {
        "ticket": ticket.model_dump(mode="json"),
        "action": "escalate",
        "escalated_by": "technical_agent",
        "reason": reason,
        "timestamp": datetime.now().isoformat(),
    }
    try:
        mq.send_message("escalation_queue", escalation_msg)
    except MessageQueueError as e:
        logger.error("Failed to queue escalation for ticket %s: %s", ticket.ticket_id, e)


@app.post("/handle_ticket")
async def handle_ticket(ticket_data: dict, db: Session = Depends(get_db)):
    ticket = SupportTicket(**ticket_data["ticket"])
    get_or_create_ticket(db, ticket, assigned_agent="technical_agent")

    # Search knowledge base
    ticket_text = f"{ticket.subject} {ticket.description}"
    kb = TechnicalKnowledgeBase(db)
    solution = kb.find_solution(ticket_text)

    if solution:
        response_content = f"**Technical Solution Found:**\n\n{solution['solution']}"

        if solution['escalate']:
            response_content += "\n\n⚠️ **Escalation Required:** This issue requires specialized database team assistance."
            reason = "Database connectivity issue requiring DBA team"
            record_escalation(db, ticket.ticket_id, "technical_agent", reason, "escalation_queue")
            _notify_escalation(ticket, reason)
    else:
        response_content = "I need to research this issue further. A senior technical specialist will follow up within 2 hours."
        reason = "Complex technical issue requiring specialist review"
        record_escalation(db, ticket.ticket_id, "technical_agent", reason, "escalation_queue")
        _notify_escalation(ticket, reason)

    escalated = solution['escalate'] if solution else True

    # Create response message
    response_message = AgentMessage(
        agent_name="technical_agent",
        message_type="response",
        content=response_content,
        timestamp=datetime.now(),
        confidence_score=0.9 if solution and not solution['escalate'] else 0.6
    )

    record_event(db, ticket.ticket_id, "technical_agent", "response",
                 {"content": response_content, "escalated": escalated})
    record_resolution(db, ticket.ticket_id, response_content, escalated)
    db.commit()

    return {
        "status": "handled",
        "response": response_message.model_dump(mode="json"),
        "escalated": escalated
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
