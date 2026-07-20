from shared.models import Priority, SupportTicket, TicketCategory


class RouterLogic:
    def __init__(self):
        self.technical_keywords = [
            'dashboard', 'connection', 'slow', 'error', 'loading', 'refresh',
            'database', 'server', 'timeout', 'visualization', 'chart', 'performance'
        ]
        self.account_keywords = [
            'access', 'user', 'login', 'permission', 'license', 'account',
            'add user', 'remove', 'department', 'role', 'upgrade'
        ]
        self.critical_departments = ['Trading', 'Risk Management', 'Executive']
        self.critical_keywords = ['trading', 'p&l', 'risk', 'down', 'critical', 'urgent']

    def classify_ticket(self, ticket: SupportTicket) -> tuple[TicketCategory, Priority]:
        text = f"{ticket.subject} {ticket.description}".lower()

        technical_score = sum(1 for word in self.technical_keywords if word in text)
        account_score = sum(1 for word in self.account_keywords if word in text)

        if technical_score > account_score:
            category = TicketCategory.TECHNICAL
        elif account_score > 0:
            category = TicketCategory.ACCOUNT
        else:
            category = TicketCategory.TRAINING

        priority = Priority.MEDIUM

        if ticket.department in self.critical_departments:
            priority = Priority.HIGH

        if any(word in text for word in self.critical_keywords):
            priority = Priority.CRITICAL

        if 'training' in text or 'how to' in text:
            priority = Priority.LOW

        return category, priority
