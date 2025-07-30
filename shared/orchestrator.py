import requests
from shared.models import SupportTicket
from shared.message_queue import MessageQueue
import json
import time
from datetime import datetime

class AgentOrchestrator:
    def __init__(self):
        self.mq = MessageQueue()
        self.agent_endpoints = {
                "router": "http://router-agent:8001",
    "technical": "http://technical-agent:8002",
    "account": "http://account-agent:8003"
        }
    
    def process_support_ticket(self, ticket: SupportTicket) -> dict:
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
                json=ticket_dict
            )
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
                json={"ticket": ticket_dict}
            )
            handling_result = handling_response.json()
            conversation_log.append({
                "agent": assigned_agent,
                "action": "response",
                "result": handling_result,
                "timestamp": datetime.now().isoformat()
            })
            
            return {
                "status": "completed",
                "ticket_id": ticket.ticket_id,
                "conversation": conversation_log,
                "final_response": handling_result["response"]["content"],
                "escalated": handling_result.get("escalated", False)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "ticket_id": ticket.ticket_id,
                "conversation": conversation_log
            }
