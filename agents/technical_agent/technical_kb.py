from typing import Optional

from sqlalchemy.orm import Session

from shared.db.models import KBArticle


class TechnicalKnowledgeBase:
    def __init__(self, db: Session):
        self.db = db

    def find_solution(self, ticket_text: str) -> Optional[dict]:
        text = ticket_text.lower()
        best_match = None
        max_matches = 0

        for article in self.db.query(KBArticle).all():
            matches = sum(1 for symptom in article.symptoms if symptom in text)
            if matches > max_matches:
                max_matches = matches
                best_match = article

        if best_match is None:
            return None
        return {"title": best_match.title, "solution": best_match.body, "escalate": best_match.escalate}
