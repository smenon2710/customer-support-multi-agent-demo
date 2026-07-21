from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from shared.config import CLASSIFIER_MODEL
from shared.llm_client import complete_json
from shared.models import Priority, SupportTicket, TicketCategory

CONFIDENCE_THRESHOLD = 0.6

CLASSIFIER_SYSTEM_PROMPT = """You triage support tickets for a financial company's internal \
Tableau help desk. Classify the ticket below.

category: one of "technical" (dashboards, errors, connections, performance issues), \
"account" (user access, licenses, permissions), or "training" (how-to questions with no \
underlying problem).
priority: one of "critical", "high", "medium", "low" — how urgent this is for the \
business, independent of category.
confidence: your confidence in this classification, from 0 to 1.

Respond ONLY with a JSON object: \
{"category": "...", "priority": "...", "reasoning": "...", "confidence": <float>}
"""


class LLMClassification(BaseModel):
    category: Literal["technical", "account", "training"]
    priority: Literal["critical", "high", "medium", "low"]
    reasoning: str = ""
    confidence: float = 0.5


@dataclass
class RoutingDecision:
    category: TicketCategory
    priority: Priority
    confidence: float
    method: str  # "rules" | "llm"


_PRIORITY_ORDER = {Priority.LOW: 0, Priority.MEDIUM: 1, Priority.HIGH: 2, Priority.CRITICAL: 3}


class RouterLogic:
    def __init__(self):
        # Keywords for classification
        self.technical_keywords = [
            'dashboard', 'connection', 'slow', 'error', 'loading', 'refresh',
            'database', 'server', 'timeout', 'visualization', 'chart', 'performance'
        ]
        self.account_keywords = [
            'access', 'user', 'login', 'permission', 'license', 'account',
            'add user', 'remove', 'department', 'role', 'upgrade'
        ]
        self.critical_departments = ['Trading', 'Risk Management', 'Executive']
        self.critical_keywords = ['trading', 'p&l', 'risk', 'down', 'critical', 'urgent']

    def classify_ticket(self, ticket: SupportTicket) -> tuple[TicketCategory, Priority, float]:
        """Pure rule-based classification — deterministic, no network calls."""
        text = f"{ticket.subject} {ticket.description}".lower()

        # Determine category
        technical_score = sum(1 for word in self.technical_keywords if word in text)
        account_score = sum(1 for word in self.account_keywords if word in text)

        if technical_score > account_score:
            category = TicketCategory.TECHNICAL
        elif account_score > 0:
            category = TicketCategory.ACCOUNT
        else:
            category = TicketCategory.TRAINING

        priority = self._apply_priority_policy(ticket, Priority.MEDIUM)
        confidence = self._confidence(technical_score, account_score)

        return category, priority, confidence

    def classify(self, ticket: SupportTicket) -> RoutingDecision:
        """Rules first; falls through to the LLM only when the rule signal is weak.

        Business-rule priority overrides (critical department, critical keywords) are
        policy, not inference — they apply to an LLM-suggested priority exactly as they
        do to the rules' own default, via the shared `_apply_priority_policy`.
        """
        category, priority, confidence = self.classify_ticket(ticket)

        if confidence < CONFIDENCE_THRESHOLD:
            llm_result = complete_json(
                CLASSIFIER_MODEL,
                CLASSIFIER_SYSTEM_PROMPT,
                f"Department: {ticket.department}\nSubject: {ticket.subject}\nDescription: {ticket.description}",
                LLMClassification,
            )
            if llm_result is not None:
                category = TicketCategory(llm_result.category)
                priority = self._apply_priority_policy(ticket, Priority(llm_result.priority))
                return RoutingDecision(category, priority, llm_result.confidence, "llm")

        return RoutingDecision(category, priority, confidence, "rules")

    def _apply_priority_policy(self, ticket: SupportTicket, base_priority: Priority) -> Priority:
        text = f"{ticket.subject} {ticket.description}".lower()
        priority = base_priority

        if ticket.department in self.critical_departments:
            priority = self._max_priority(priority, Priority.HIGH)

        if any(word in text for word in self.critical_keywords):
            priority = Priority.CRITICAL

        if 'training' in text or 'how to' in text:
            priority = Priority.LOW

        return priority

    @staticmethod
    def _max_priority(a: Priority, b: Priority) -> Priority:
        return a if _PRIORITY_ORDER[a] >= _PRIORITY_ORDER[b] else b

    @staticmethod
    def _confidence(technical_score: int, account_score: int) -> float:
        total = technical_score + account_score
        if total == 0:
            return 0.3
        margin = abs(technical_score - account_score)
        return min(1.0, 0.5 + 0.5 * (margin / total))
