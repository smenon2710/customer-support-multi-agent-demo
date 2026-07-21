from typing import Optional

from sqlalchemy.orm import Session

from shared.db.models import Escalation, Ticket, TicketEvent, utcnow
from shared.models import SupportTicket


def get_or_create_ticket(
    db: Session, ticket: SupportTicket, assigned_agent: Optional[str] = None
) -> Ticket:
    """Look up the ticket by ID, or create it if this is the first agent to see it.

    Existing rows are never overwritten here — the router agent is normally the
    first to create the row (with category/priority/assigned_agent already set),
    and a handling agent calling this afterwards just wants the existing row. It
    only builds a fresh row when nothing exists yet, e.g. a handling agent's
    endpoint invoked directly, without a prior routing step.
    """
    db_ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket.ticket_id).first()
    if db_ticket is not None:
        return db_ticket

    db_ticket = Ticket(
        ticket_id=ticket.ticket_id,
        user_email=ticket.user_email,
        department=ticket.department,
        subject=ticket.subject,
        description=ticket.description,
        category=ticket.category.value if ticket.category else None,
        priority=ticket.priority.value if ticket.priority else None,
        assigned_agent=assigned_agent,
        status="open",
    )
    db.add(db_ticket)
    db.flush()
    return db_ticket


def record_event(db: Session, ticket_id: str, agent: str, action: str, payload: dict) -> None:
    db.add(TicketEvent(ticket_id=ticket_id, agent=agent, action=action, payload=payload))


def record_resolution(db: Session, ticket_id: str, resolution: str, escalated: bool) -> None:
    db_ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if db_ticket is not None:
        db_ticket.status = "escalated" if escalated else "resolved"
        db_ticket.resolution = resolution
        db_ticket.escalated = escalated
        db_ticket.resolved_at = utcnow()


def record_escalation(
    db: Session, ticket_id: str, escalated_by: str, reason: str, queue_name: str
) -> None:
    db.add(Escalation(
        ticket_id=ticket_id,
        escalated_by=escalated_by,
        reason=reason,
        queue_name=queue_name,
    ))
