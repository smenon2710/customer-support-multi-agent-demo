import logging
from datetime import datetime

import uvicorn
from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from shared.db.repository import get_or_create_ticket, record_escalation, record_event, record_resolution
from shared.db.session import get_db, init_db, is_db_healthy
from shared.message_queue import MessageQueue, MessageQueueError
from shared.models import AgentMessage, SupportTicket

try:
    from .rag import generate_response
    from .technical_kb import TechnicalKnowledgeBase
except ImportError:
    from rag import generate_response
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

    # Retrieve candidate KB articles, then generate a grounded response (RAG).
    ticket_text = f"{ticket.subject} {ticket.description}"
    kb = TechnicalKnowledgeBase(db)
    articles = kb.retrieve(ticket_text)
    result, method = generate_response(ticket_text, articles)

    if result.escalate:
        reason = result.escalation_reason or "Escalated by technical agent"
        record_escalation(db, ticket.ticket_id, "technical_agent", reason, "escalation_queue")
        _notify_escalation(ticket, reason)

    record_event(db, ticket.ticket_id, "technical_agent", "response", {
        "content": result.response,
        "escalated": result.escalate,
        "method": method,
        "kb_articles_used": result.kb_articles_used,
    })
    record_resolution(db, ticket.ticket_id, result.response, result.escalate)
    db.commit()

    # Create response message
    response_message = AgentMessage(
        agent_name="technical_agent",
        message_type="response",
        content=result.response,
        timestamp=datetime.now(),
        confidence_score=0.9 if not result.escalate else 0.6
    )

    return {
        "status": "handled",
        "response": response_message.model_dump(mode="json"),
        "escalated": result.escalate
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
