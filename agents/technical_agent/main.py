import logging
from datetime import datetime

import uvicorn
from fastapi import FastAPI

from shared.message_queue import MessageQueue, MessageQueueError
from shared.models import AgentMessage, SupportTicket

try:
    from .technical_kb import TechnicalKnowledgeBase
except ImportError:
    from technical_kb import TechnicalKnowledgeBase

logger = logging.getLogger(__name__)

app = FastAPI(title="Technical Support Agent")
mq = MessageQueue()
kb = TechnicalKnowledgeBase()


@app.get("/health")
async def health():
    healthy = mq.is_healthy()
    return {"status": "ok" if healthy else "degraded", "queue_connected": healthy}


def _escalate(ticket: SupportTicket, reason: str) -> None:
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
async def handle_ticket(ticket_data: dict):
    ticket = SupportTicket(**ticket_data["ticket"])

    # Search knowledge base
    ticket_text = f"{ticket.subject} {ticket.description}"
    solution = kb.find_solution(ticket_text)

    if solution:
        response_content = f"**Technical Solution Found:**\n\n{solution['solution']}"

        if solution['escalate']:
            response_content += "\n\n⚠️ **Escalation Required:** This issue requires specialized database team assistance."
            _escalate(ticket, "Database connectivity issue requiring DBA team")
    else:
        response_content = "I need to research this issue further. A senior technical specialist will follow up within 2 hours."
        _escalate(ticket, "Complex technical issue requiring specialist review")

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
        "response": response_message.model_dump(mode="json"),
        "escalated": solution['escalate'] if solution else True
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
