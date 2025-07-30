from fastapi import FastAPI
from shared.models import SupportTicket, AgentMessage
from shared.message_queue import MessageQueue
from datetime import datetime
import uvicorn

app = FastAPI(title="Account Management Agent")
mq = MessageQueue()

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
        import re
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

account_manager = AccountManager()

@app.post("/handle_ticket")
async def handle_ticket(ticket_data: dict):
    ticket = SupportTicket(**ticket_data["ticket"])
    
    # Process the account request
    ticket_text = f"{ticket.subject} {ticket.description}"
    response_content = account_manager.process_access_request(ticket_text, ticket.department)
    
    # Check if escalation is needed
    needs_escalation = "Manager Approval Required" in response_content
    
    if needs_escalation:
        escalation_msg = {
            "ticket": ticket.dict(),
            "action": "escalate",
            "escalated_by": "account_agent",
            "reason": "Manager approval required for additional licenses",
            "timestamp": datetime.now().isoformat()
        }
        mq.send_message("manager_approval_queue", escalation_msg)
    
    # Create response message
    response_message = AgentMessage(
        agent_name="account_agent",
        message_type="response",
        content=response_content,
        timestamp=datetime.now(),
        confidence_score=0.95 if not needs_escalation else 0.8
    )
    
    return {
        "status": "handled",
        "response": response_message.dict(),
        "escalated": needs_escalation
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
