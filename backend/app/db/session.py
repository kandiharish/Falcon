"""Database connection: one shared engine, one session per request."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

# The engine keeps a pool of open connections that requests borrow and return.
# pool_pre_ping checks a connection is still alive before handing it out.
engine = create_engine(get_settings().database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: open a session for one request, always close it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
