import re

from shared.tableau_service import TableauBackend


class AccountManager:
    def __init__(self, backend: TableauBackend):
        self.backend = backend

    def process_access_request(self, ticket_text: str, department: str) -> str:
        text = ticket_text.lower()

        # Extract number of users requested
        numbers = re.findall(r'\d+', text)
        requested_users = int(numbers[0]) if numbers else 1

        if "add" in text or "new user" in text:
            capacity_check = self.backend.check_capacity(department, requested_users)

            if capacity_check.success:
                return f"✅ **Access Request Approved**\n\nI can provision {requested_users} new {capacity_check.license_type} license(s) for {department}.\n\n**Next Steps:**\n1. Please provide the new user email addresses\n2. Specify required dashboard access\n3. Accounts will be created within 2 business hours"
            else:
                if capacity_check.requires_approval:
                    return f"⚠️ **Manager Approval Required**\n\n{capacity_check.reason}\n\nI've escalated this request to your department manager for additional license approval."
                else:
                    return f"❌ **Request Error**\n\n{capacity_check.reason}"

        elif "remove" in text or "disable" in text:
            return f"✅ **User Removal Request**\n\nI can process the user removal for {department}.\n\n**Please confirm:**\n1. User email address to remove\n2. Data retention requirements\n3. Effective date for access termination"

        elif "permission" in text or "access" in text:
            dept_info = self.backend.get_department(department)
            if dept_info is None:
                return f"❌ **Request Error**\n\nDepartment not found"
            return f"🔑 **Permission Review**\n\nI'll review the current access permissions for {department}.\n\n**Current Setup:**\n- License Type: {dept_info.license_type}\n- Active Users: {dept_info.current_users}\n\nPlease specify what permission changes are needed."

        else:
            return "I need more details about this account request. Please specify if you need to add users, remove access, or modify permissions."
