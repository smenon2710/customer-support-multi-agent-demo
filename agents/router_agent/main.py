import logging
from datetime import datetime

import uvicorn
from fastapi import FastAPI

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


@app.get("/health")
async def health():
    healthy = mq.is_healthy()
    return {"status": "ok" if healthy else "degraded", "queue_connected": healthy}


@app.post("/route_ticket")
async def route_ticket(ticket: SupportTicket):
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
