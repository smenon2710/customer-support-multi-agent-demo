from typing import List

from sqlalchemy.orm import Session

from shared.db.models import KBArticle


class TechnicalKnowledgeBase:
    def __init__(self, db: Session):
        self.db = db

    def retrieve(self, ticket_text: str, top_n: int = 3) -> List[KBArticle]:
        """Score every article by symptom-keyword overlap with the ticket text and
        return the top `top_n` with at least one match, best match first.

        This is the retrieval half of RAG, deliberately implemented as simple scored
        keyword matching over already-fetched rows rather than a DB-native full-text
        search (e.g. Postgres tsvector) — that would work on Postgres but not the
        SQLite fallback this project also runs on, and at this KB scale (a handful of
        articles) the difference in retrieval quality is negligible.
        """
        text = ticket_text.lower()
        scored = [
            (sum(1 for symptom in article.symptoms if symptom in text), article)
            for article in self.db.query(KBArticle).all()
        ]
        matches = [(score, article) for score, article in scored if score > 0]
        matches.sort(key=lambda pair: pair[0], reverse=True)
        return [article for _, article in matches[:top_n]]
