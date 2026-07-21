import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.db.base import Base
from shared.db.models import Department, KBArticle, License, User

KB_ARTICLES = [
    {
        "title": "Dashboard Loading Issues",
        "symptoms": ["slow", "loading", "timeout", "dashboard"],
        "solution": "1. Check Tableau Server status\n2. Clear browser cache\n3. Reduce dashboard complexity\n4. Contact IT if server issues persist",
        "escalate": False,
    },
    {
        "title": "Database Connection Errors",
        "symptoms": ["connection", "database", "timeout", "oracle", "sql"],
        "solution": "1. Verify VPN connection\n2. Check database credentials\n3. Test connection from Tableau Desktop\n4. Contact DBA team if connectivity issues persist",
        "escalate": True,
    },
    {
        "title": "Data Refresh Problems",
        "symptoms": ["refresh", "extract", "data", "outdated"],
        "solution": "1. Check data source connection\n2. Verify refresh schedule\n3. Review extract logs\n4. Manually trigger refresh if needed",
        "escalate": False,
    },
    {
        "title": "Visualization Errors",
        "symptoms": ["chart", "visualization", "error", "display"],
        "solution": "1. Check calculated fields\n2. Verify data types\n3. Review filters and parameters\n4. Recreate visualization if corrupted",
        "escalate": False,
    },
]

# Mirrors the department numbers scripts/seed_db.py uses, scoped down to the
# departments the test suite actually exercises.
DEPARTMENTS = {
    "Trading": {"max_users": 900, "current_users": 850, "license": "Creator"},
    "Finance": {"max_users": 700, "current_users": 650, "license": "Explorer"},
}


@pytest.fixture()
def db_session():
    """A fresh, empty, in-memory SQLite database with the full schema applied.

    StaticPool pins every connection to the same underlying SQLite connection —
    without it, a plain `:memory:` engine hands out a brand-new, empty database
    to any connection opened from a different thread, which FastAPI's TestClient
    does via its anyio thread portal.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def seeded_db(db_session):
    """db_session, populated with the departments/users/KB articles tests rely on."""
    licenses = {}
    for name in sorted({info["license"] for info in DEPARTMENTS.values()}):
        lic = License(name=name)
        db_session.add(lic)
        db_session.flush()
        licenses[name] = lic

    for dept_name, info in DEPARTMENTS.items():
        dept = Department(
            name=dept_name,
            max_users=info["max_users"],
            license_id=licenses[info["license"]].id,
        )
        db_session.add(dept)
        db_session.flush()

        for i in range(info["current_users"]):
            db_session.add(User(
                email=f"{dept_name.lower().replace(' ', '')}{i}@fintechanalytics.com",
                department_id=dept.id,
                license_id=licenses[info["license"]].id,
            ))

    for article in KB_ARTICLES:
        db_session.add(KBArticle(
            title=article["title"],
            symptoms=article["symptoms"],
            body=article["solution"],
            escalate=article["escalate"],
        ))

    db_session.commit()
    return db_session
