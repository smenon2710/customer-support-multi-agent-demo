import logging
from datetime import datetime

import requests

from shared.config import AGENT_ENDPOINTS, INTERNAL_API_TOKEN
from shared.logging_config import configure_logging, set_ticket_id
from shared.models import SupportTicket

configure_logging()
logger = logging.getLogger(__name__)


class AgentOrchestrator:
    def __init__(self):
        self.agent_endpoints = AGENT_ENDPOINTS
        self.headers = {"X-Internal-Token": INTERNAL_API_TOKEN} if INTERNAL_API_TOKEN else {}

    def process_support_ticket(self, ticket: SupportTicket) -> dict:
        set_ticket_id(ticket.ticket_id)
        conversation_log = []

        try:
            # Convert ticket to dictionary with ISO datetime format
            ticket_dict = {
                "ticket_id": ticket.ticket_id,
                "user_email": ticket.user_email,
                "department": ticket.department,
                "subject": ticket.subject,
                "description": ticket.description,
                "created_at": ticket.created_at.isoformat(),
                "messages": ticket.messages
            }

            # Step 1: Route the ticket
            routing_response = requests.post(
                f"{self.agent_endpoints['router']}/route_ticket",
                json=ticket_dict,
                headers=self.headers,
            )
            routing_response.raise_for_status()
            routing_result = routing_response.json()
            conversation_log.append({
                "agent": "router_agent",
                "action": "classification",
                "result": routing_result,
                "timestamp": datetime.now().isoformat()
            })

            # Step 2: Handle with appropriate agent
            assigned_agent = routing_result["assigned_agent"]
            agent_endpoint = self.agent_endpoints[assigned_agent.replace("_agent", "")]

            handling_response = requests.post(
                f"{agent_endpoint}/handle_ticket",
                json={"ticket": ticket_dict},
                headers=self.headers,
            )
            handling_response.raise_for_status()
            handling_result = handling_response.json()
            conversation_log.append({
                "agent": assigned_agent,
                "action": "response",
                "result": handling_result,
                "timestamp": datetime.now().isoformat()
            })

            logger.info("Ticket processed: routed to %s", assigned_agent)
            return {
                "status": "completed",
                "ticket_id": ticket.ticket_id,
                "conversation": conversation_log,
                "final_response": handling_result["response"]["content"],
                "escalated": handling_result.get("escalated", False)
            }

        except Exception as e:
            logger.warning("Ticket processing failed: %s", e)
            return {
                "status": "error",
                "error": str(e),
                "ticket_id": ticket.ticket_id,
                "conversation": conversation_log
            }
