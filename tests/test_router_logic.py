from datetime import datetime

from agents.router_agent import router_logic as router_logic_module
from agents.router_agent.router_logic import RouterLogic
from shared.models import Priority, SupportTicket, TicketCategory

router_logic = RouterLogic()


def _ticket(subject, description, department="Marketing"):
    return SupportTicket(
        ticket_id="T001",
        user_email="user@fintechanalytics.com",
        department=department,
        subject=subject,
        description=description,
        created_at=datetime.now(),
    )


def test_classifies_technical_keywords():
    ticket = _ticket("Dashboard error", "The dashboard is showing a loading error and timeout.")
    category, _, confidence = router_logic.classify_ticket(ticket)
    assert category == TicketCategory.TECHNICAL
    assert confidence > 0.6


def test_classifies_account_keywords():
    ticket = _ticket("New user access", "Please add a new user and grant permission.")
    category, _, _ = router_logic.classify_ticket(ticket)
    assert category == TicketCategory.ACCOUNT


def test_defaults_to_training_with_no_keywords():
    ticket = _ticket(
        "Getting started with Tableau",
        "How to use Tableau for the first time? I would like some guidance.",
    )
    category, priority, confidence = router_logic.classify_ticket(ticket)
    assert category == TicketCategory.TRAINING
    assert priority == Priority.LOW
    assert confidence == 0.3  # zero keyword signal in either direction


def test_critical_department_floors_priority_at_high():
    ticket = _ticket("Slow dashboard", "The dashboard is slow today.", department="Trading")
    _, priority, _ = router_logic.classify_ticket(ticket)
    assert priority == Priority.HIGH


def test_critical_keyword_overrides_priority():
    ticket = _ticket(
        "Dashboard down", "Trading dashboard is down right now.", department="Marketing"
    )
    _, priority, _ = router_logic.classify_ticket(ticket)
    assert priority == Priority.CRITICAL


def test_classify_uses_rules_when_confident():
    ticket = _ticket("Dashboard error", "The dashboard is showing a loading error and timeout.")
    decision = router_logic.classify(ticket)
    assert decision.method == "rules"
    assert decision.category == TicketCategory.TECHNICAL


def test_classify_falls_back_to_rules_when_llm_unavailable_for_ambiguous_ticket():
    # No OPENROUTER_API_KEY is configured in the test environment, so this exercises
    # the real "LLM unavailable" degradation path end to end, not a mock.
    ticket = _ticket("Weird phrasing", "Something is off with my setup, not sure what's going on.")
    decision = router_logic.classify(ticket)
    assert decision.method == "rules"
    assert decision.category == TicketCategory.TRAINING


def test_llm_classification_still_respects_critical_department_floor(monkeypatch):
    def fake_complete_json(model, system, user, schema, **kwargs):
        return router_logic_module.LLMClassification(
            category="training", priority="low", reasoning="looks like a how-to", confidence=0.95
        )

    monkeypatch.setattr(router_logic_module, "complete_json", fake_complete_json)

    ticket = _ticket(
        "Weird phrasing", "Something is off with my setup, not sure what's going on.",
        department="Trading",
    )
    decision = router_logic.classify(ticket)

    assert decision.method == "llm"
    assert decision.category == TicketCategory.TRAINING
    # Trading is a critical department — the floor applies even though the LLM said "low"
    assert decision.priority == Priority.HIGH
