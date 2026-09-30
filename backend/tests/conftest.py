"""Test setup: a separate database (falcon_test), migrated with the real Alembic migrations.

Tests never touch the development database.
"""

import os
import uuid
from collections.abc import Callable, Iterator

# Must happen before the app is imported: settings read the environment once.
os.environ["POSTGRES_DB"] = "falcon_test"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.security.passwords import hash_password  # noqa: E402

TEST_PASSWORD = "correct horse battery staple"


def _create_test_database() -> None:
    settings = get_settings()
    admin_url = settings.database_url.rsplit("/", 1)[0] + "/postgres"
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = 'falcon_test'"))
        if not exists:
            conn.execute(text("CREATE DATABASE falcon_test"))
    engine.dispose()

    test_engine = create_engine(settings.database_url, isolation_level="AUTOCOMMIT")
    with test_engine.connect() as conn:
        for extension in ("postgis", "vector", "pg_trgm"):
            conn.execute(text(f"CREATE EXTENSION IF NOT EXISTS {extension}"))
    test_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def database() -> None:
    _create_test_database()
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import app

    # The CSRF header is sent by the real frontend on every request; tests do the same.
    with TestClient(app, headers={"X-FALCON-Request": "1"}) as test_client:
        yield test_client


@pytest.fixture
def make_user() -> Callable[..., User]:
    """Create a user with a unique email. Each test gets its own users, so tests don't clash."""

    def _make(role: str = "forensic_analyst", **fields) -> User:
        with SessionLocal() as db:
            user = User(
                email=f"user-{uuid.uuid4().hex[:10]}@test.example",
                display_name="Test User",
                role=role,
                password_hash=hash_password(TEST_PASSWORD),
                **fields,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return user

    return _make
