from agents.account_agent.account_manager import AccountManager

manager = AccountManager()


def test_check_user_capacity_success():
    result = manager.check_user_capacity("Trading", 10)
    assert result["success"] is True
    assert result["available_licenses"] == 50
    assert result["license_type"] == "Creator"


def test_check_user_capacity_requires_approval_over_limit():
    result = manager.check_user_capacity("Trading", 100)
    assert result["success"] is False
    assert result["requires_approval"] is True


def test_check_user_capacity_unknown_department():
    result = manager.check_user_capacity("Unknown Dept", 1)
    assert result["success"] is False
    assert "not found" in result["reason"].lower()


def test_process_access_request_add_user_within_capacity():
    response = manager.process_access_request("Please add 2 new users", "Trading")
    assert "Access Request Approved" in response


def test_process_access_request_over_capacity_needs_approval():
    response = manager.process_access_request("Please add 500 new users", "Trading")
    assert "Manager Approval Required" in response


def test_process_access_request_permission_review():
    response = manager.process_access_request("I need to review access permissions", "Finance")
    assert "Permission Review" in response
