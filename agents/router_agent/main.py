import logging
import os
from datetime import datetime

import uvicorn
from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from shared.auth import verify_internal_token
from shared.db.repository import get_or_create_ticket, record_event
from shared.db.session import get_db, init_db, is_db_healthy
from shared.logging_config import configure_logging, set_ticket_id
from shared.message_queue import MessageQueue, MessageQueueError
from shared.models import AgentMessage, SupportTicket, TicketCategory

try:
    from .router_logic import RouterLogic
except ImportError:
    from router_logic import RouterLogic

configure_logging()
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


@app.post("/route_ticket", dependencies=[Depends(verify_internal_token)])
async def route_ticket(ticket: SupportTicket, db: Session = Depends(get_db)):
    set_ticket_id(ticket.ticket_id)

    # Classify the ticket — rules first, falling through to the LLM only when the
    # rule signal is weak (see RouterLogic.classify).
    decision = router_logic.classify(ticket, db=db)
    category, priority = decision.category, decision.priority
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
        "method": decision.method,
        "confidence": decision.confidence,
    })
    db.commit()
    logger.info("Routed ticket to %s via %s (priority=%s)", target_agent, decision.method, priority.value)

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
        content=f"Classified as {category.value} with {priority.value} priority "
                f"(via {decision.method}). Routed to {target_agent}.",
        timestamp=datetime.now(),
        confidence_score=decision.confidence
    )

    return {
        "status": "routed",
        "category": category,
        "priority": priority,
        "assigned_agent": target_agent,
        "routing_message": routing_message.model_dump(mode="json")
    }


if __name__ == "__main__":
    # PaaS free tiers (Render, etc.) inject PORT and require binding to it;
    # falls back to the fixed port for local/Docker Compose use.
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8001)))
