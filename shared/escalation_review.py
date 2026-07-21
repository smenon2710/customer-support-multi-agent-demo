from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from shared.db.models import Escalation, Ticket, utcnow
from shared.db.repository import record_event


@dataclass
class PendingEscalation:
    escalation_id: int
    ticket_id: str
    department: str
    subject: str
    description: str
    escalated_by: str
    reason: str
    queue_name: str
    created_at: datetime
    draft_response: Optional[str]


def list_pending_escalations(db: Session) -> List[PendingEscalation]:
    """Escalations no human has reviewed yet, oldest first."""
    escalations = (
        db.query(Escalation)
        .filter(Escalation.resolved.is_(False))
        .order_by(Escalation.created_at.asc())
        .all()
    )

    pending = []
    for esc in escalations:
        ticket = db.query(Ticket).filter(Ticket.ticket_id == esc.ticket_id).first()
        pending.append(PendingEscalation(
            escalation_id=esc.id,
            ticket_id=esc.ticket_id,
            department=ticket.department if ticket else "",
            subject=ticket.subject if ticket else "",
            description=ticket.description if ticket else "",
            escalated_by=esc.escalated_by,
            reason=esc.reason,
            queue_name=esc.queue_name,
            created_at=esc.created_at,
            draft_response=ticket.resolution if ticket else None,
        ))
    return pending


def _get_escalation(db: Session, escalation_id: int) -> Escalation:
    escalation = db.query(Escalation).filter(Escalation.id == escalation_id).first()
    if escalation is None:
        raise ValueError(f"Escalation {escalation_id} not found")
    return escalation


def approve_escalation(
    db: Session, escalation_id: int, final_response: str, reviewer: str = "human_reviewer"
) -> None:
    """Send `final_response` (the AI's draft, edited or as-is) as the ticket's resolution."""
    escalation = _get_escalation(db, escalation_id)

    ticket = db.query(Ticket).filter(Ticket.ticket_id == escalation.ticket_id).first()
    if ticket is not None:
        ticket.status = "resolved"
        ticket.resolution = final_response
        ticket.resolved_at = utcnow()
        # ticket.escalated stays True — it's a historical fact (the AI did escalate
        # this), not a "still pending" flag; escalation.resolved tracks that instead.

    escalation.resolved = True
    record_event(db, escalation.ticket_id, reviewer, "human_review",
                 {"decision": "approved", "final_response": final_response})
    db.commit()


def reject_escalation(db: Session, escalation_id: int, note: str, reviewer: str = "human_reviewer") -> None:
    """Decline the AI's draft — the ticket stays escalated for manual handling outside
    the system; this only clears it from the review queue and records why.
    """
    escalation = _get_escalation(db, escalation_id)

    escalation.resolved = True
    record_event(db, escalation.ticket_id, reviewer, "human_review",
                 {"decision": "rejected", "note": note})
    db.commit()
