from datetime import timedelta

from agents.technical_agent.resolution_cache import find_cached_resolution
from shared.db.models import Ticket, utcnow


def _make_ticket(ticket_id, subject, resolution, escalated, resolved_at):
    return Ticket(
        ticket_id=ticket_id,
        user_email="user@example.com",
        department="Trading",
        subject=subject,
        description="whatever",
        status="escalated" if escalated else "resolved",
        resolution=resolution,
        escalated=escalated,
        resolved_at=resolved_at,
    )


def test_returns_none_when_no_prior_ticket_with_subject(db_session):
    assert find_cached_resolution(db_session, "Never seen before") is None


def test_returns_prior_resolution_for_matching_subject(db_session):
    db_session.add(_make_ticket("T1", "Dashboard slow", "Clear your cache", False, utcnow()))
    db_session.commit()

    result = find_cached_resolution(db_session, "Dashboard slow")
    assert result is not None
    assert result.response == "Clear your cache"
    assert result.escalate is False


def test_ignores_tickets_without_a_recorded_resolution(db_session):
    db_session.add(Ticket(
        ticket_id="T1", user_email="user@example.com", department="Trading",
        subject="Dashboard slow", description="whatever", status="open",
    ))
    db_session.commit()

    assert find_cached_resolution(db_session, "Dashboard slow") is None


def test_replays_escalation_outcome_too(db_session):
    db_session.add(_make_ticket("T1", "Weird issue", "Escalating for review", True, utcnow()))
    db_session.commit()

    result = find_cached_resolution(db_session, "Weird issue")
    assert result is not None
    assert result.escalate is True


def test_uses_most_recent_when_multiple_prior_tickets_match(db_session):
    db_session.add(_make_ticket("T1", "Dashboard slow", "Old advice", False, utcnow() - timedelta(days=1)))
    db_session.add(_make_ticket("T2", "Dashboard slow", "New advice", False, utcnow()))
    db_session.commit()

    result = find_cached_resolution(db_session, "Dashboard slow")
    assert result.response == "New advice"
