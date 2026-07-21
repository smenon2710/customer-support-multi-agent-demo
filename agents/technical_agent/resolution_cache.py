from typing import Optional

from sqlalchemy.orm import Session

from shared.db.models import Ticket

try:
    from .rag import AgentResponse
except ImportError:
    from rag import AgentResponse


def find_cached_resolution(db: Session, subject: str) -> Optional[AgentResponse]:
    """The most recent already-processed ticket with the exact same subject, if
    one exists — reused verbatim to skip both KB retrieval and the LLM call for
    a repeat issue.

    Trusts the first repeat: no occurrence threshold. The demo UI's subject
    field is mostly drawn from a fixed, frequency-ranked list rather than free
    text (see demo/streamlit_interface.py), so an exact subject match is a
    meaningful signal of the same underlying issue, not a coincidental string
    collision — unlike matching on the free-text description, which would
    rarely repeat verbatim across different tickets.

    Replays whatever the prior ticket's outcome was, escalation included: if a
    subject consistently has no good KB coverage, immediately escalating repeat
    instances is a reasonable outcome, not a bug — re-attempting resolution
    every time would defeat the point of caching.
    """
    prior = (
        db.query(Ticket)
        .filter(Ticket.subject == subject, Ticket.resolution.isnot(None))
        .order_by(Ticket.resolved_at.desc())
        .first()
    )
    if prior is None:
        return None
    return AgentResponse(
        response=prior.resolution,
        escalate=prior.escalated,
        escalation_reason=None,
        kb_articles_used=[],
    )
