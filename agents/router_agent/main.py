import logging
from datetime import datetime

import uvicorn
from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from shared.db.repository import get_or_create_ticket, record_event
from shared.db.session import get_db, init_db, is_db_healthy
from shared.message_queue import MessageQueue, MessageQueueError
from shared.models import AgentMessage, SupportTicket, TicketCategory

try:
    from .router_logic import RouterLogic
except ImportError:
    from router_logic import RouterLogic

logger = logging.getLogger(__name__)

app = FastAPI(title="Router Agent")
mq = MessageQueue()
router_logic = RouterLogic()
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


@app.post("/route_ticket")
async def route_ticket(ticket: SupportTicket, db: Session = Depends(get_db)):
    # Classify the ticket
    category, priority = router_logic.classify_ticket(ticket)
    ticket.category = category
    ticket.priority = priority

    # Route to appropriate agent
    if category == TicketCategory.TECHNICAL:
        target_agent = "technical_agent"
    elif category == TicketCategory.ACCOUNT:
        target_agent = "account_agent"
    else:
        target_agent = "technical_agent"  # Training goes to technical for now

    ticket.assigned_agent = target_agent

    get_or_create_ticket(db, ticket, assigned_agent=target_agent)
    record_event(db, ticket.ticket_id, "router_agent", "classification", {
        "category": category.value,
        "priority": priority.value,
        "assigned_agent": target_agent,
    })
    db.commit()

    # Record the routing decision. Nothing currently consumes this queue — the
    # actual handoff is the orchestrator's direct HTTP call to /handle_ticket —
    # so a queue failure here is logged, not fatal to routing.
    message = {
        "ticket": ticket.model_dump(mode="json"),
        "action": "handle_ticket",
        "routed_by": "router_agent",
        "timestamp": datetime.now().isoformat(),
    }
    try:
        mq.send_message(f"{target_agent}_queue", message)
    except MessageQueueError as e:
        logger.warning("Failed to record routing decision on the queue: %s", e)

    # Log routing decision
    routing_message = AgentMessage(
        agent_name="router_agent",
        message_type="classification",
        content=f"Classified as {category.value} with {priority.value} priority. Routed to {target_agent}.",
        timestamp=datetime.now(),
        confidence_score=0.85
    )

    return {
        "status": "routed",
        "category": category,
        "priority": priority,
        "assigned_agent": target_agent,
        "routing_message": routing_message.model_dump(mode="json")
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
