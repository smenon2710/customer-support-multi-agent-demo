from agents.account_agent.account_manager import AccountManager
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


def test_process_access_request_add_user_within_capacity(seeded_db):
    manager = AccountManager(SimulatedTableauBackend(seeded_db))
    response = manager.process_access_request("Please add 2 new users", "Trading")
    assert "Access Request Approved" in response


def test_process_access_request_over_capacity_needs_approval(seeded_db):
    manager = AccountManager(SimulatedTableauBackend(seeded_db))
    response = manager.process_access_request("Please add 500 new users", "Trading")
    assert "Manager Approval Required" in response


def test_process_access_request_permission_review(seeded_db):
    manager = AccountManager(SimulatedTableauBackend(seeded_db))
    response = manager.process_access_request("I need to review access permissions", "Finance")
    assert "Permission Review" in response
    assert "Explorer" in response


def test_provision_user_creates_active_user(seeded_db):
    backend = SimulatedTableauBackend(seeded_db)
    before = backend.get_department("Trading").current_users

    assert backend.provision_user("new.hire@fintechanalytics.com", "Trading") is True

    after = backend.get_department("Trading").current_users
    assert after == before + 1


def test_deactivate_user_frees_capacity(seeded_db):
    backend = SimulatedTableauBackend(seeded_db)
    backend.provision_user("temp.contractor@fintechanalytics.com", "Trading")
    before = backend.get_department("Trading").current_users

    assert backend.deactivate_user("temp.contractor@fintechanalytics.com") is True

    after = backend.get_department("Trading").current_users
    assert after == before - 1


def test_deactivate_unknown_user_returns_false(seeded_db):
    backend = SimulatedTableauBackend(seeded_db)
    assert backend.deactivate_user("nobody@fintechanalytics.com") is False
