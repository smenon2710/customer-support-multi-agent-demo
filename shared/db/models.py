from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from shared.db.base import Base


def utcnow() -> datetime:
    # datetime.utcnow() is deprecated (Python 3.12+); this keeps the same naive-UTC
    # value our DateTime columns (no timezone=True) expect.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class License(Base):
    __tablename__ = "licenses"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)  # Viewer / Explorer / Creator


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    max_users = Column(Integer, nullable=False)
    license_id = Column(Integer, ForeignKey("licenses.id"), nullable=False)

    license = relationship("License")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    license_id = Column(Integer, ForeignKey("licenses.id"), nullable=False)
    status = Column(String(20), nullable=False, default="active")  # active | removed
    created_at = Column(DateTime, nullable=False, default=utcnow)

    department = relationship("Department")
    license = relationship("License")


class KBArticle(Base):
    __tablename__ = "kb_articles"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    symptoms = Column(JSON, nullable=False)  # list[str]
    escalate = Column(Boolean, nullable=False, default=False)


class Ticket(Base):
    __tablename__ = "tickets"

    ticket_id = Column(String(20), primary_key=True)
    user_email = Column(String(255), nullable=False)
    department = Column(String(100), nullable=False)
    subject = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(20))
    priority = Column(String(20))
    assigned_agent = Column(String(50))
    status = Column(String(20), nullable=False, default="open")  # open | resolved | escalated
    resolution = Column(Text)
    escalated = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    resolved_at = Column(DateTime)

    events = relationship("TicketEvent", back_populates="ticket", cascade="all, delete-orphan")


class TicketEvent(Base):
    __tablename__ = "ticket_events"

    id = Column(Integer, primary_key=True)
    ticket_id = Column(String(20), ForeignKey("tickets.ticket_id"), nullable=False)
    agent = Column(String(50), nullable=False)
    action = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=utcnow)

    ticket = relationship("Ticket", back_populates="events")


class Escalation(Base):
    __tablename__ = "escalations"

    id = Column(Integer, primary_key=True)
    ticket_id = Column(String(20), ForeignKey("tickets.ticket_id"), nullable=False)
    escalated_by = Column(String(50), nullable=False)
    reason = Column(Text, nullable=False)
    queue_name = Column(String(50), nullable=False)
    resolved = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    ticket = relationship("Ticket")


class LLMCallLog(Base):
    """One row per shared.llm_client.complete_json() attempt — backs the dashboard's
    LLM availability metric. Not tied to a ticket: some attempts may not resolve to
    one (e.g. a call made outside a ticket-handling request), and a ticket can trigger
    zero, one, or several attempts (retries).
    """
    __tablename__ = "llm_call_log"

    id = Column(Integer, primary_key=True)
    model = Column(String(100), nullable=False)
    success = Column(Boolean, nullable=False)
    reason = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)
