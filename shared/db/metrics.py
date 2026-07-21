import statistics
from dataclasses import dataclass, field
from typing import Dict, Optional

from sqlalchemy.orm import Session

from shared.db.models import Ticket


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
