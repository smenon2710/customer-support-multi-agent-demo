from enum import Enum
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high" 
    MEDIUM = "medium"
    LOW = "low"

class TicketCategory(str, Enum):
    TECHNICAL = "technical"
    ACCOUNT = "account"
    TRAINING = "training"

class SupportTicket(BaseModel):
    ticket_id: str
    user_email: str
    department: str
    subject: str
    description: str
    category: Optional[TicketCategory] = None
    priority: Optional[Priority] = None
    assigned_agent: Optional[str] = None
    status: str = "open"
    created_at: datetime
    messages: List[dict] = []

class AgentMessage(BaseModel):
    agent_name: str
    message_type: str  # "classification", "response", "escalation"
    content: str
    timestamp: datetime
    confidence_score: Optional[float] = None
