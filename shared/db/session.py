from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from shared.config import DATABASE_URL

# SQLite needs this to allow use across the threads FastAPI's TestClient
# and uvicorn's worker pool may hand a request to.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create all tables if they don't already exist. Idempotent — safe to call at startup."""
    from shared.db import models  # noqa: F401 — import registers the models on Base.metadata
    from shared.db.base import Base

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def is_db_healthy() -> bool:
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            return True
        finally:
            db.close()
    except Exception:
        return False
