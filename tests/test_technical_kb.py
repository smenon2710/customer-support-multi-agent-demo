from agents.technical_agent.technical_kb import TechnicalKnowledgeBase


def test_matches_dashboard_loading_issue(seeded_db):
    kb = TechnicalKnowledgeBase(seeded_db)
    articles = kb.retrieve("My dashboard is slow and keeps loading forever.")
    assert articles
    assert articles[0].title == "Dashboard Loading Issues"
    assert articles[0].escalate is False


def test_matches_database_connection_issue_and_flags_escalation(seeded_db):
    kb = TechnicalKnowledgeBase(seeded_db)
    articles = kb.retrieve("Getting a connection timeout error from the Oracle database.")
    assert articles
    assert articles[0].title == "Database Connection Errors"
    assert articles[0].escalate is True


def test_returns_no_articles_for_unmatched_text(seeded_db):
    kb = TechnicalKnowledgeBase(seeded_db)
    articles = kb.retrieve("I would like to schedule a training session next week.")
    assert articles == []


def test_retrieve_caps_at_top_n(seeded_db):
    kb = TechnicalKnowledgeBase(seeded_db)
    # Matches all 4 seeded articles at least once — verify the cap actually limits results.
    articles = kb.retrieve(
        "dashboard is slow and loading with a timeout, connection to the database failed, "
        "also seeing a chart error and outdated refresh extract data",
        top_n=2,
    )
    assert len(articles) == 2
