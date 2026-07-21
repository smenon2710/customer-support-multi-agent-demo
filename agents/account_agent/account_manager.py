from shared.tableau_service import TableauBackend

try:
    from .intent import AccountIntent
except ImportError:
    from intent import AccountIntent


class AccountManager:
    def __init__(self, backend: TableauBackend):
        self.backend = backend

    def build_response(self, intent: AccountIntent, department: str) -> str:
        if intent.action == "add_users":
            capacity_check = self.backend.check_capacity(department, intent.user_count)

            if capacity_check.success:
                return f"✅ **Access Request Approved**\n\nI can provision {intent.user_count} new {capacity_check.license_type} license(s) for {department}.\n\n**Next Steps:**\n1. Please provide the new user email addresses\n2. Specify required dashboard access\n3. Accounts will be created within 2 business hours"
            if capacity_check.requires_approval:
                return f"⚠️ **Manager Approval Required**\n\n{capacity_check.reason}\n\nI've escalated this request to your department manager for additional license approval."
            return f"❌ **Request Error**\n\n{capacity_check.reason}"

        if intent.action == "remove_user":
            if intent.target_emails:
                email = intent.target_emails[0]
                if self.backend.deactivate_user(email):
                    return f"✅ **User Removed**\n\n{email} has been deactivated and their license freed for {department}."
                return f"❌ **Request Error**\n\nNo active user found with email {email}."
            return f"✅ **User Removal Request**\n\nI can process the user removal for {department}.\n\n**Please confirm:**\n1. User email address to remove\n2. Data retention requirements\n3. Effective date for access termination"

        if intent.action == "review_permissions":
            dept_info = self.backend.get_department(department)
            if dept_info is None:
                return "❌ **Request Error**\n\nDepartment not found"
            return f"🔑 **Permission Review**\n\nI'll review the current access permissions for {department}.\n\n**Current Setup:**\n- License Type: {dept_info.license_type}\n- Active Users: {dept_info.current_users}\n\nPlease specify what permission changes are needed."

        return "I need more details about this account request. Please specify if you need to add users, remove access, or modify permissions."
