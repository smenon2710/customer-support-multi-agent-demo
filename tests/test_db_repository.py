from datetime import datetime

from shared.db.models import Escalation, Ticket, TicketEvent
from shared.db.repository import get_or_create_ticket, record_escalation, record_event, record_resolution
from shared.models import Priority, SupportTicket, TicketCategory


def _ticket(**overrides):
    fields = dict(
        ticket_id="T001",
        user_email="user@fintechanalytics.com",
        department="Trading",
        subject="Dashboard down",
        description="The dashboard is down.",
        created_at=datetime.now(),
    )
    fields.update(overrides)
    return SupportTicket(**fields)


def test_get_or_create_ticket_creates_row(db_session):
    ticket = _ticket(category=TicketCategory.TECHNICAL, priority=Priority.CRITICAL)
    db_ticket = get_or_create_ticket(db_session, ticket, assigned_agent="technical_agent")

    assert db_ticket.ticket_id == "T001"
    assert db_ticket.category == "technical"
    assert db_ticket.priority == "critical"
    assert db_ticket.assigned_agent == "technical_agent"
    assert db_ticket.status == "open"


def test_get_or_create_ticket_does_not_overwrite_existing_row(db_session):
    original = _ticket(category=TicketCategory.TECHNICAL, priority=Priority.CRITICAL)
    get_or_create_ticket(db_session, original, assigned_agent="technical_agent")

    # A handling agent calling this with a ticket that has no category/priority set
    # (as happens when /handle_ticket is invoked without a prior /route_ticket) must
    # not clobber the row the router already created.
    bare = _ticket()
    db_ticket = get_or_create_ticket(db_session, bare, assigned_agent="account_agent")

    assert db_ticket.category == "technical"
    assert db_ticket.assigned_agent == "technical_agent"


def test_record_event_and_resolution(db_session):
    ticket = _ticket()
    get_or_create_ticket(db_session, ticket, assigned_agent="technical_agent")

    record_event(db_session, "T001", "technical_agent", "response", {"content": "fixed it"})
    record_resolution(db_session, "T001", "fixed it", escalated=False)
    db_session.commit()

    events = db_session.query(TicketEvent).filter(TicketEvent.ticket_id == "T001").all()
    assert len(events) == 1
    assert events[0].payload == {"content": "fixed it"}

    db_ticket = db_session.query(Ticket).filter(Ticket.ticket_id == "T001").first()
    assert db_ticket.status == "resolved"
    assert db_ticket.resolution == "fixed it"
    assert db_ticket.resolved_at is not None


def test_record_escalation(db_session):
    ticket = _ticket()
    get_or_create_ticket(db_session, ticket, assigned_agent="technical_agent")
    record_escalation(db_session, "T001", "technical_agent", "needs a human", "escalation_queue")
    db_session.commit()

    escalation = db_session.query(Escalation).filter(Escalation.ticket_id == "T001").first()
    assert escalation is not None
    assert escalation.escalated_by == "technical_agent"
    assert escalation.reason == "needs a human"
