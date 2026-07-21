from typing import List, Optional, Tuple

from pydantic import BaseModel
from sqlalchemy.orm import Session

from shared.config import GENERATION_MODEL
from shared.db.models import KBArticle
from shared.llm_client import complete_json

TECH_AGENT_SYSTEM_PROMPT = """You are a Tableau technical support assistant for a financial \
services company's internal help desk. Answer the ticket below using ONLY the knowledge \
base articles provided — never invent troubleshooting steps that aren't grounded in them. \
If the articles don't actually cover the reported issue, set escalate to true and explain \
what a specialist should look into instead of guessing.

Respond ONLY with a JSON object:
{"response": "<markdown answer for the user>", "escalate": <bool>, \
"escalation_reason": "<string, or null if escalate is false>", \
"kb_articles_used": ["<article title>", ...]}
"""


class AgentResponse(BaseModel):
    response: str
    escalate: bool
    escalation_reason: Optional[str] = None
    kb_articles_used: List[str] = []


def generate_response(
    ticket_text: str, articles: List[KBArticle], db: Optional[Session] = None
) -> Tuple[AgentResponse, str]:
    """Returns (response, method) where method is "llm" or "rules".

    `db`, if given, is passed through to `complete_json` for LLM-availability
    logging (see shared/llm_client.py) — optional, purely for observability.
    """
    if not articles:
        return (
            AgentResponse(
                response="I need to research this issue further. A senior technical "
                         "specialist will follow up within 2 hours.",
                escalate=True,
                escalation_reason="Complex technical issue requiring specialist review",
                kb_articles_used=[],
            ),
            "rules",
        )

    kb_context = "\n\n".join(f"## {a.title}\n{a.body}" for a in articles)
    result = complete_json(
        GENERATION_MODEL,
        TECH_AGENT_SYSTEM_PROMPT,
        f"<knowledge_base>\n{kb_context}\n</knowledge_base>\n\n<ticket>\n{ticket_text}\n</ticket>",
        AgentResponse,
        db=db,
    )
    if result is not None:
        return result, "llm"

    # LLM unavailable/unparseable: fall back to the pre-LLM behavior — serve the
    # best-matched article directly. Its own `escalate` flag (set when the article was
    # authored) decides whether this needs a specialist, exactly as it did before the
    # LLM existed. A missing/rate-limited API key must never turn an already-working
    # autonomous resolution into a forced escalation.
    top = articles[0]
    return (
        AgentResponse(
            response=f"**Technical Solution Found:**\n\n{top.body}",
            escalate=top.escalate,
            escalation_reason=f"{top.title} is flagged for specialist review" if top.escalate else None,
            kb_articles_used=[top.title],
        ),
        "rules",
    )
