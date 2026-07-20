from agents.technical_agent.technical_kb import TechnicalKnowledgeBase

kb = TechnicalKnowledgeBase()


def test_matches_dashboard_loading_issue():
    solution = kb.find_solution("My dashboard is slow and keeps loading forever.")
    assert solution is not None
    assert solution["escalate"] is False


def test_matches_database_connection_issue_and_flags_escalation():
    solution = kb.find_solution("Getting a connection timeout error from the Oracle database.")
    assert solution is not None
    assert solution["escalate"] is True


def test_returns_none_for_unmatched_text():
    solution = kb.find_solution("I would like to schedule a training session next week.")
    assert solution is None
