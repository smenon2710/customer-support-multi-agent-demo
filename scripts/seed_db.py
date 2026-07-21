"""One-time database seed: licenses, departments, a Faker-generated user
population matching the original demo's per-department counts, and the KB
articles from data/kb_articles.json. Safe to re-run — skips if already seeded.
"""
import json
from pathlib import Path

from faker import Faker

from shared.db.base import Base
from shared.db.models import Department, KBArticle, License, User
from shared.db.session import SessionLocal, engine

DEPARTMENTS = {
    "Trading": {"max_users": 900, "current_users": 850, "license": "Creator"},
    "Risk Management": {"max_users": 450, "current_users": 420, "license": "Explorer"},
    "Compliance": {"max_users": 400, "current_users": 380, "license": "Viewer"},
    "Marketing": {"max_users": 300, "current_users": 290, "license": "Explorer"},
    "Operations": {"max_users": 1250, "current_users": 1200, "license": "Viewer"},
    "Finance": {"max_users": 700, "current_users": 650, "license": "Explorer"},
    "Executive": {"max_users": 100, "current_users": 80, "license": "Creator"},
}

KB_ARTICLES_PATH = Path(__file__).resolve().parent.parent / "data" / "kb_articles.json"


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Department).count() > 0:
            print("Database already seeded — skipping. Drop the tables / delete the DB file to reseed.")
            return

        fake = Faker()

        licenses = {}
        for name in sorted({info["license"] for info in DEPARTMENTS.values()}):
            lic = License(name=name)
            db.add(lic)
            db.flush()
            licenses[name] = lic

        total_users = 0
        for dept_name, info in DEPARTMENTS.items():
            dept = Department(
                name=dept_name,
                max_users=info["max_users"],
                license_id=licenses[info["license"]].id,
            )
            db.add(dept)
            db.flush()

            for _ in range(info["current_users"]):
                db.add(User(
                    email=fake.unique.company_email(),
                    department_id=dept.id,
                    license_id=licenses[info["license"]].id,
                ))
            total_users += info["current_users"]

        articles = json.loads(KB_ARTICLES_PATH.read_text())
        for article in articles:
            db.add(KBArticle(
                title=article["title"],
                body=article["solution"],
                symptoms=article["symptoms"],
                escalate=article["escalate"],
            ))

        db.commit()
        print(f"Seeded {len(DEPARTMENTS)} departments, {total_users} users, {len(articles)} KB articles.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
