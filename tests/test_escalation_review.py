from datetime import datetime

import pytest

from shared.db.models import Escalation, Ticket, TicketEvent
from shared.db.repository import get_or_create_ticket, record_escalation, record_resolution
from shared.escalation_review import approve_escalation, list_pending_escalations, reject_escalation
from shared.models import SupportTicket


def _seed_escalated_ticket(db_session, ticket_id="T001"):
    ticket = SupportTicket(
        ticket_id=ticket_id,
        user_email="user@fintechanalytics.com",
        department="Trading",
        subject="Dashboard timeout",
        description="The dashboard keeps timing out.",
        created_at=datetime.now(),
    )
    get_or_create_ticket(db_session, ticket, assigned_agent="technical_agent")
    record_resolution(db_session, ticket_id, "Draft response from the agent.", escalated=True)
    record_escalation(db_session, ticket_id, "technical_agent", "Needs specialist review", "escalation_queue")
    db_session.commit()
    return ticket_id


def test_list_pending_escalations_returns_unresolved(db_session):
    ticket_id = _seed_escalated_ticket(db_session)

    pending = list_pending_escalations(db_session)

    assert len(pending) == 1
    assert pending[0].ticket_id == ticket_id
    assert pending[0].draft_response == "Draft response from the agent."
    assert pending[0].queue_name == "escalation_queue"


def test_list_pending_escalations_excludes_resolved(db_session):
    ticket_id = _seed_escalated_ticket(db_session)
    escalation = db_session.query(Escalation).filter(Escalation.ticket_id == ticket_id).first()
    escalation.resolved = True
    db_session.commit()

    assert list_pending_escalations(db_session) == []


def test_approve_escalation_resolves_ticket_with_given_text(db_session):
    ticket_id = _seed_escalated_ticket(db_session)
    escalation = db_session.query(Escalation).filter(Escalation.ticket_id == ticket_id).first()

    approve_escalation(db_session, escalation.id, "Final approved response.", reviewer="manager@fintechanalytics.com")

    ticket = db_session.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    assert ticket.status == "resolved"
    assert ticket.resolution == "Final approved response."
    assert ticket.resolved_at is not None
    assert ticket.escalated is True  # historical fact — stays true even once reviewed

    refreshed = db_session.query(Escalation).filter(Escalation.id == escalation.id).first()
    assert refreshed.resolved is True

    event = db_session.query(TicketEvent).filter(
        TicketEvent.ticket_id == ticket_id, TicketEvent.action == "human_review"
    ).first()
    assert event is not None
    assert event.payload["decision"] == "approved"
    assert event.payload["final_response"] == "Final approved response."
    assert event.agent == "manager@fintechanalytics.com"

    assert list_pending_escalations(db_session) == []


def test_reject_escalation_leaves_ticket_status_unchanged(db_session):
    ticket_id = _seed_escalated_ticket(db_session)
    escalation = db_session.query(Escalation).filter(Escalation.ticket_id == ticket_id).first()
    ticket_before = db_session.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    resolved_at_before = ticket_before.resolved_at  # set by the agent's own record_resolution call

    reject_escalation(db_session, escalation.id, "Handled manually.", reviewer="manager@fintechanalytics.com")

    ticket = db_session.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    assert ticket.status == "escalated"  # unchanged — set by record_resolution(escalated=True)
    assert ticket.resolved_at == resolved_at_before  # reject doesn't touch it

    refreshed = db_session.query(Escalation).filter(Escalation.id == escalation.id).first()
    assert refreshed.resolved is True

    event = db_session.query(TicketEvent).filter(
        TicketEvent.ticket_id == ticket_id, TicketEvent.action == "human_review"
    ).first()
    assert event is not None
    assert event.payload["decision"] == "rejected"
    assert event.payload["note"] == "Handled manually."

    assert list_pending_escalations(db_session) == []


def test_approve_unknown_escalation_raises(db_session):
    with pytest.raises(ValueError):
        approve_escalation(db_session, 9999, "text")


def test_reject_unknown_escalation_raises(db_session):
    with pytest.raises(ValueError):
        reject_escalation(db_session, 9999, "note")
