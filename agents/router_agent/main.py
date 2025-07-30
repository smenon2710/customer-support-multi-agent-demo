from fastapi import FastAPI
from shared.models import SupportTicket, AgentMessage, TicketCategory, Priority
from shared.message_queue import MessageQueue
import re
from datetime import datetime
import uvicorn

app = FastAPI(title="Router Agent")
mq = MessageQueue()

class RouterLogic:
    def __init__(self):
        # Keywords for classification
        self.technical_keywords = [
            'dashboard', 'connection', 'slow', 'error', 'loading', 'refresh', 
            'database', 'server', 'timeout', 'visualization', 'chart', 'performance'
        ]
        self.account_keywords = [
            'access', 'user', 'login', 'permission', 'license', 'account', 
            'add user', 'remove', 'department', 'role', 'upgrade'
        ]
        self.critical_departments = ['Trading', 'Risk Management', 'Executive']
        self.critical_keywords = ['trading', 'p&l', 'risk', 'down', 'critical', 'urgent']

    def classify_ticket(self, ticket: SupportTicket) -> tuple[TicketCategory, Priority]:
        text = f"{ticket.subject} {ticket.description}".lower()
        
        # Determine category
        technical_score = sum(1 for word in self.technical_keywords if word in text)
        account_score = sum(1 for word in self.account_keywords if word in text)
        
        if technical_score > account_score:
            category = TicketCategory.TECHNICAL
        elif account_score > 0:
            category = TicketCategory.ACCOUNT
        else:
            category = TicketCategory.TRAINING
        
        # Determine priority
        priority = Priority.MEDIUM  # Default
        
        if ticket.department in self.critical_departments:
            priority = Priority.HIGH
        
        if any(word in text for word in self.critical_keywords):
            priority = Priority.CRITICAL
        
        if 'training' in text or 'how to' in text:
            priority = Priority.LOW
            
        return category, priority

router_logic = RouterLogic()

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
    
    # Send to appropriate agent queue
    message = {
        "ticket": ticket.dict(),
        "action": "handle_ticket",
        "routed_by": "router_agent",
        "timestamp": datetime.now().isoformat()
    }
    
    mq.send_message(f"{target_agent}_queue", message)
    
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
        "routing_message": routing_message.dict()
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
