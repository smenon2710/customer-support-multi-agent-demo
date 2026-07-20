import re


class AccountManager:
    def __init__(self):
        self.user_database = {
            "departments": {
                "Trading": {"max_users": 900, "current_users": 850, "licenses": "Creator"},
                "Risk Management": {"max_users": 450, "current_users": 420, "licenses": "Explorer"},
                "Compliance": {"max_users": 400, "current_users": 380, "licenses": "Viewer"},
                "Marketing": {"max_users": 300, "current_users": 290, "licenses": "Explorer"},
                "Operations": {"max_users": 1250, "current_users": 1200, "licenses": "Viewer"},
                "Finance": {"max_users": 700, "current_users": 650, "licenses": "Explorer"},
                "Executive": {"max_users": 100, "current_users": 80, "licenses": "Creator"}
            }
        }

    def check_user_capacity(self, department: str, requested_users: int) -> dict:
        if department not in self.user_database["departments"]:
            return {"success": False, "reason": "Department not found"}

        dept_info = self.user_database["departments"][department]
        available = dept_info["max_users"] - dept_info["current_users"]

        if requested_users <= available:
            return {
                "success": True,
                "available_licenses": available,
                "license_type": dept_info["licenses"]
            }
        else:
            return {
                "success": False,
                "reason": f"Insufficient licenses. Requested: {requested_users}, Available: {available}",
                "requires_approval": True
            }

    def process_access_request(self, ticket_text: str, department: str) -> str:
        text = ticket_text.lower()

        # Extract number of users requested
        numbers = re.findall(r'\d+', text)
        requested_users = int(numbers[0]) if numbers else 1

        if "add" in text or "new user" in text:
            capacity_check = self.check_user_capacity(department, requested_users)

            if capacity_check["success"]:
                return f"✅ **Access Request Approved**\n\nI can provision {requested_users} new {capacity_check['license_type']} license(s) for {department}.\n\n**Next Steps:**\n1. Please provide the new user email addresses\n2. Specify required dashboard access\n3. Accounts will be created within 2 business hours"
            else:
                if capacity_check.get("requires_approval"):
                    return f"⚠️ **Manager Approval Required**\n\n{capacity_check['reason']}\n\nI've escalated this request to your department manager for additional license approval."
                else:
                    return f"❌ **Request Error**\n\n{capacity_check['reason']}"

        elif "remove" in text or "disable" in text:
            return f"✅ **User Removal Request**\n\nI can process the user removal for {department}.\n\n**Please confirm:**\n1. User email address to remove\n2. Data retention requirements\n3. Effective date for access termination"

        elif "permission" in text or "access" in text:
            return f"🔑 **Permission Review**\n\nI'll review the current access permissions for {department}.\n\n**Current Setup:**\n- License Type: {self.user_database['departments'][department]['licenses']}\n- Active Users: {self.user_database['departments'][department]['current_users']}\n\nPlease specify what permission changes are needed."

        else:
            return "I need more details about this account request. Please specify if you need to add users, remove access, or modify permissions."
