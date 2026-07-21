from agents.account_agent.account_manager import AccountManager
from agents.account_agent.intent import AccountIntent, extract_intent
from shared.tableau_service import SimulatedTableauBackend


def test_check_capacity_success(seeded_db):
    backend = SimulatedTableauBackend(seeded_db)
    result = backend.check_capacity("Trading", 10)
    assert result.success is True
    assert result.available_licenses == 50
    assert result.license_type == "Creator"


def test_check_capacity_requires_approval_over_limit(seeded_db):
    backend = SimulatedTableauBackend(seeded_db)
    result = backend.check_capacity("Trading", 100)
    assert result.success is False
    assert result.requires_approval is True


def test_check_capacity_unknown_department(seeded_db):
    backend = SimulatedTableauBackend(seeded_db)
    result = backend.check_capacity("Unknown Dept", 1)
    assert result.success is False
    assert "not found" in result.reason.lower()


def test_extract_intent_add_users_rule():
    intent, method = extract_intent("Please add 2 new users")
    assert method == "rules"
    assert intent.action == "add_users"
    assert intent.user_count == 2


def test_extract_intent_remove_user_with_email():
    intent, method = extract_intent("Please remove jane.doe@fintechanalytics.com from Trading")
    assert method == "rules"
    assert intent.action == "remove_user"
    assert intent.target_emails == ["jane.doe@fintechanalytics.com"]


def test_extract_intent_unclear_falls_back_to_rules_when_llm_unavailable():
    # No OPENROUTER_API_KEY is configured in the test environment.
    intent, method = extract_intent("Something strange is happening with my account setup.")
    assert method == "rules"
    assert intent.action == "unclear"


def test_process_access_request_add_user_within_capacity(seeded_db):
    manager = AccountManager(SimulatedTableauBackend(seeded_db))
    intent, _ = extract_intent("Please add 2 new users")
    response = manager.build_response(intent, "Trading")
    assert "Access Request Approved" in response


def test_process_access_request_over_capacity_needs_approval(seeded_db):
    manager = AccountManager(SimulatedTableauBackend(seeded_db))
    intent, _ = extract_intent("Please add 500 new users")
    response = manager.build_response(intent, "Trading")
    assert "Manager Approval Required" in response


def test_process_access_request_permission_review(seeded_db):
    manager = AccountManager(SimulatedTableauBackend(seeded_db))
    intent, _ = extract_intent("I need to review access permissions")
    response = manager.build_response(intent, "Finance")
    assert "Permission Review" in response
    assert "Explorer" in response


def test_remove_user_with_known_email_deactivates(seeded_db):
    backend = SimulatedTableauBackend(seeded_db)
    manager = AccountManager(backend)
    backend.provision_user("temp.contractor@fintechanalytics.com", "Trading")

    intent, _ = extract_intent("Please remove temp.contractor@fintechanalytics.com")
    response = manager.build_response(intent, "Trading")

    assert "User Removed" in response
    assert backend.deactivate_user("temp.contractor@fintechanalytics.com") is False  # already removed


def test_remove_user_without_email_asks_for_confirmation(seeded_db):
    manager = AccountManager(SimulatedTableauBackend(seeded_db))
    intent, _ = extract_intent("Please remove a user from Trading")
    response = manager.build_response(intent, "Trading")
    assert "User Removal Request" in response
    assert "Please confirm" in response


def test_unclear_intent_asks_for_more_details(seeded_db):
    manager = AccountManager(SimulatedTableauBackend(seeded_db))
    intent = AccountIntent(action="unclear", reasoning="test")
    response = manager.build_response(intent, "Trading")
    assert "need more details" in response


def test_provision_user_creates_active_user(seeded_db):
    backend = SimulatedTableauBackend(seeded_db)
    before = backend.get_department("Trading").current_users

    assert backend.provision_user("new.hire@fintechanalytics.com", "Trading") is True

    after = backend.get_department("Trading").current_users
    assert after == before + 1


def test_deactivate_user_frees_capacity(seeded_db):
    backend = SimulatedTableauBackend(seeded_db)
    backend.provision_user("temp.contractor2@fintechanalytics.com", "Trading")
    before = backend.get_department("Trading").current_users

    assert backend.deactivate_user("temp.contractor2@fintechanalytics.com") is True

    after = backend.get_department("Trading").current_users
    assert after == before - 1


def test_deactivate_unknown_user_returns_false(seeded_db):
    backend = SimulatedTableauBackend(seeded_db)
    assert backend.deactivate_user("nobody@fintechanalytics.com") is False
