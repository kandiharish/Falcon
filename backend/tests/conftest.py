"""Test setup: a separate database (falcon_test), migrated with the real Alembic migrations.

Tests never touch the development database.
"""

import os
import tempfile
import uuid
from collections.abc import Callable, Iterator

# Must happen before the app is imported: settings read the environment once.
os.environ["POSTGRES_DB"] = "falcon_test"
# Evidence files written by tests go to a throw-away folder, never the real storage/.
os.environ["STORAGE_DIR"] = tempfile.mkdtemp(prefix="falcon-test-storage-")
# A fixed, test-only key for encrypting MFA secrets (never the real one from .env).
os.environ["FALCON_SECRET_KEY"] = "test-only-key-not-a-real-secret"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.security.passwords import hash_password  # noqa: E402
from tests.helpers import TEST_PASSWORD, create_case, signed_in  # noqa: E402


def _create_test_database() -> None:
    """Start every test run from an empty database, built by the real migrations."""
    settings = get_settings()
    admin_url = settings.database_url.rsplit("/", 1)[0] + "/postgres"
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS falcon_test WITH (FORCE)"))
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


@pytest.fixture
def team(make_user):
    """An officer (lead) with an analyst on the team, and a fresh case."""
    officer_user = make_user("investigation_officer")
    analyst_user = make_user("forensic_analyst")
    officer = signed_in(officer_user)
    case = create_case(officer)["reference"]
    officer.post(f"/api/investigations/{case}/members", json={"email": analyst_user.email})
    return {"officer": officer, "analyst": signed_in(analyst_user), "case": case}


@pytest.fixture(autouse=True)
def offline_ai() -> Iterator[None]:
    """By default tests run as if Ollama were not running: fast, offline, predictable.
    Tests that need AI swap in a FakeProvider (tests/fake_ai.py)."""
    from app.ai import provider
    from tests.fake_ai import OfflineProvider

    provider.use(OfflineProvider())
    yield
    provider.use(None)


@pytest.fixture(autouse=True)
def fresh_rate_limits() -> Iterator[None]:
    """Each test starts with empty rate-limit counters (the suite signs in many times)."""
    from app.security.rate_limit import WINDOW

    WINDOW.reset()
    yield
