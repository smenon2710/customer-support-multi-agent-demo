from typing import Optional


class TechnicalKnowledgeBase:
    def __init__(self):
        self.solutions = {
            "dashboard_loading": {
                "symptoms": ["slow", "loading", "timeout", "dashboard"],
                "solution": "1. Check Tableau Server status\n2. Clear browser cache\n3. Reduce dashboard complexity\n4. Contact IT if server issues persist",
                "escalate": False
            },
            "database_connection": {
                "symptoms": ["connection", "database", "timeout", "oracle", "sql"],
                "solution": "1. Verify VPN connection\n2. Check database credentials\n3. Test connection from Tableau Desktop\n4. Contact DBA team if connectivity issues persist",
                "escalate": True
            },
            "data_refresh": {
                "symptoms": ["refresh", "extract", "data", "outdated"],
                "solution": "1. Check data source connection\n2. Verify refresh schedule\n3. Review extract logs\n4. Manually trigger refresh if needed",
                "escalate": False
            },
            "visualization_error": {
                "symptoms": ["chart", "visualization", "error", "display"],
                "solution": "1. Check calculated fields\n2. Verify data types\n3. Review filters and parameters\n4. Recreate visualization if corrupted",
                "escalate": False
            }
        }

    def find_solution(self, ticket_text: str) -> Optional[dict]:
        text = ticket_text.lower()
        best_match = None
        max_matches = 0

        for issue_data in self.solutions.values():
            matches = sum(1 for symptom in issue_data["symptoms"] if symptom in text)
            if matches > max_matches:
                max_matches = matches
                best_match = issue_data

        return best_match if max_matches > 0 else None
