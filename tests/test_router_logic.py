from datetime import datetime

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
    category, _ = router_logic.classify_ticket(ticket)
    assert category == TicketCategory.TECHNICAL


def test_classifies_account_keywords():
    ticket = _ticket("New user access", "Please add a new user and grant permission.")
    category, _ = router_logic.classify_ticket(ticket)
    assert category == TicketCategory.ACCOUNT


def test_defaults_to_training_with_no_keywords():
    ticket = _ticket(
        "Getting started with Tableau",
        "How to use Tableau for the first time? I would like some guidance.",
    )
    category, priority = router_logic.classify_ticket(ticket)
    assert category == TicketCategory.TRAINING
    assert priority == Priority.LOW


def test_critical_department_floors_priority_at_high():
    ticket = _ticket("Slow dashboard", "The dashboard is slow today.", department="Trading")
    _, priority = router_logic.classify_ticket(ticket)
    assert priority == Priority.HIGH


def test_critical_keyword_overrides_priority():
    ticket = _ticket(
        "Dashboard down", "Trading dashboard is down right now.", department="Marketing"
    )
    _, priority = router_logic.classify_ticket(ticket)
    assert priority == Priority.CRITICAL
