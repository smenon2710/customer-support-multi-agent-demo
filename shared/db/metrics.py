import statistics
from dataclasses import dataclass, field
from typing import Dict, Optional

from sqlalchemy.orm import Session

from shared.db.models import LLMCallLog, Ticket


@dataclass
class TicketMetrics:
    total_tickets: int
    resolved: int
    escalated: int
    open: int
    resolution_rate: float
    escalation_rate: float
    median_handling_seconds: Optional[float]
    tickets_by_department: Dict[str, int] = field(default_factory=dict)
    tickets_by_priority: Dict[str, int] = field(default_factory=dict)


def compute_ticket_metrics(db: Session) -> TicketMetrics:
    tickets = db.query(Ticket).all()
    total = len(tickets)
    resolved = sum(1 for t in tickets if t.status == "resolved")
    escalated = sum(1 for t in tickets if t.escalated)
    open_count = sum(1 for t in tickets if t.status == "open")

    handling_times = [
        (t.resolved_at - t.created_at).total_seconds()
        for t in tickets
        if t.resolved_at is not None
    ]

    by_department: Dict[str, int] = {}
    by_priority: Dict[str, int] = {}
    for t in tickets:
        by_department[t.department] = by_department.get(t.department, 0) + 1
        if t.priority:
            by_priority[t.priority] = by_priority.get(t.priority, 0) + 1

    return TicketMetrics(
        total_tickets=total,
        resolved=resolved,
        escalated=escalated,
        open=open_count,
        resolution_rate=(resolved / total) if total else 0.0,
        escalation_rate=(escalated / total) if total else 0.0,
        median_handling_seconds=statistics.median(handling_times) if handling_times else None,
        tickets_by_department=by_department,
        tickets_by_priority=by_priority,
    )


@dataclass
class LLMAvailability:
    total_calls: int
    successful: int
    availability_rate: float
    failures_by_reason: Dict[str, int] = field(default_factory=dict)


def compute_llm_availability(db: Session) -> LLMAvailability:
    """Aggregates shared.llm_client.complete_json()'s LLMCallLog rows — how often
    LLM calls actually succeeded, and why they didn't when they failed.
    """
    logs = db.query(LLMCallLog).all()
    total = len(logs)
    successful = sum(1 for log in logs if log.success)

    failures_by_reason: Dict[str, int] = {}
    for log in logs:
        if not log.success:
            failures_by_reason[log.reason] = failures_by_reason.get(log.reason, 0) + 1

    return LLMAvailability(
        total_calls=total,
        successful=successful,
        availability_rate=(successful / total) if total else 0.0,
        failures_by_reason=failures_by_reason,
    )
