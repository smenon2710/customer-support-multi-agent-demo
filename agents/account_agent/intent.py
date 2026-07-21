import re
from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel
from sqlalchemy.orm import Session

from shared.config import CLASSIFIER_MODEL
from shared.llm_client import complete_json

EMAIL_PATTERN = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')

ACCOUNT_INTENT_SYSTEM_PROMPT = """You extract the intent behind a Tableau account-access \
support ticket for a financial company. Classify what the user is asking for.

action: one of "add_users" (provision new user licenses), "remove_user" (deactivate a \
user), "review_permissions" (check or change existing access), or "unclear" (none of \
these apply).
user_count: how many users this concerns (default 1 if not specified).
reasoning: one sentence explaining the classification.

Respond ONLY with a JSON object: \
{"action": "...", "user_count": <int>, "reasoning": "..."}
"""


class AccountIntent(BaseModel):
    action: Literal["add_users", "remove_user", "review_permissions", "unclear"]
    user_count: int = 1
    target_emails: List[str] = []
    reasoning: str = ""


def extract_intent(ticket_text: str, db: Optional[Session] = None) -> Tuple[AccountIntent, str]:
    """Rules first; falls through to the LLM only when no rule keyword matched.

    Email addresses are always extracted by regex, never left to the LLM — a literal
    email in the text is unambiguous either way, so there's nothing for the model to
    add there. Returns (intent, method) where method is "llm" or "rules".

    `db`, if given, is passed through to `complete_json` for LLM-availability
    logging (see shared/llm_client.py) — optional, purely for observability.
    """
    text = ticket_text.lower()
    emails = EMAIL_PATTERN.findall(ticket_text)
    numbers = re.findall(r'\d+', text)
    requested_users = int(numbers[0]) if numbers else 1

    if "add" in text or "new user" in text:
        action = "add_users"
    elif "remove" in text or "disable" in text:
        action = "remove_user"
    elif "permission" in text or "access" in text:
        action = "review_permissions"
    else:
        action = None

    if action is not None:
        return (
            AccountIntent(
                action=action, user_count=requested_users, target_emails=emails,
                reasoning=f"rule: matched '{action}' keyword",
            ),
            "rules",
        )

    llm_result = complete_json(CLASSIFIER_MODEL, ACCOUNT_INTENT_SYSTEM_PROMPT, ticket_text, AccountIntent, db=db)
    if llm_result is not None:
        if not llm_result.target_emails:
            llm_result.target_emails = emails
        return llm_result, "llm"

    return (
        AccountIntent(
            action="unclear", user_count=requested_users, target_emails=emails,
            reasoning="no rule matched and LLM unavailable",
        ),
        "rules",
    )
