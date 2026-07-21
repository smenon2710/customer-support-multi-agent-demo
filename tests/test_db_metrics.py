from datetime import timedelta

from shared.db.metrics import compute_llm_availability, compute_ticket_metrics
from shared.db.models import LLMCallLog, Ticket, utcnow


def _ticket(ticket_id, department, priority, status, escalated, resolved_after_seconds=None):
    created_at = utcnow()
    resolved_at = (
        created_at + timedelta(seconds=resolved_after_seconds)
        if resolved_after_seconds is not None
        else None
    )
    return Ticket(
        ticket_id=ticket_id,
        user_email="user@fintechanalytics.com",
        department=department,
        subject="subject",
        description="description",
        priority=priority,
        status=status,
        escalated=escalated,
        created_at=created_at,
        resolved_at=resolved_at,
    )


def test_compute_ticket_metrics_on_empty_db(db_session):
    metrics = compute_ticket_metrics(db_session)
    assert metrics.total_tickets == 0
    assert metrics.resolution_rate == 0.0
    assert metrics.escalation_rate == 0.0
    assert metrics.median_handling_seconds is None


def test_compute_ticket_metrics_aggregates_correctly(db_session):
    db_session.add_all([
        _ticket("T1", "Trading", "critical", "resolved", False, resolved_after_seconds=10),
        _ticket("T2", "Trading", "high", "escalated", True, resolved_after_seconds=30),
        _ticket("T3", "Finance", "medium", "open", False),
    ])
    db_session.commit()

    metrics = compute_ticket_metrics(db_session)

    assert metrics.total_tickets == 3
    assert metrics.resolved == 1
    assert metrics.escalated == 1
    assert metrics.open == 1
    assert metrics.resolution_rate == 1 / 3
    assert metrics.escalation_rate == 1 / 3
    assert metrics.median_handling_seconds == 20.0
    assert metrics.tickets_by_department == {"Trading": 2, "Finance": 1}
    assert metrics.tickets_by_priority == {"critical": 1, "high": 1, "medium": 1}


def test_compute_llm_availability_on_empty_db(db_session):
    availability = compute_llm_availability(db_session)
    assert availability.total_calls == 0
    assert availability.availability_rate == 0.0
    assert availability.failures_by_reason == {}


def test_compute_llm_availability_aggregates_correctly(db_session):
    db_session.add_all([
        LLMCallLog(model="m1", success=True, reason="success"),
        LLMCallLog(model="m1", success=True, reason="success"),
        LLMCallLog(model="m1", success=False, reason="rate_limited"),
        LLMCallLog(model="m1", success=False, reason="rate_limited"),
        LLMCallLog(model="m1", success=False, reason="no_api_key"),
    ])
    db_session.commit()

    availability = compute_llm_availability(db_session)

    assert availability.total_calls == 5
    assert availability.successful == 2
    assert availability.availability_rate == 2 / 5
    assert availability.failures_by_reason == {"rate_limited": 2, "no_api_key": 1}
