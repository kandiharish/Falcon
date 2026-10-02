"""Authentication, authorization and audit tests (plan §51)."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.db.session import SessionLocal
from app.models import AuditLog
from tests.helpers import TEST_PASSWORD


def login(client, email, password=TEST_PASSWORD, remember=False):
    return client.post(
        "/api/auth/login", json={"email": email, "password": password, "remember": remember}
    )


def audit_actions(email: str) -> list[str]:
    with SessionLocal() as db:
        rows = db.scalars(
            select(AuditLog.action).where(AuditLog.actor_email == email).order_by(AuditLog.id)
        )
        return list(rows)


# --- Authentication -------------------------------------------------------------------


def test_login_sets_secure_session_cookie_and_returns_permissions(client, make_user):
    user = make_user(role="supervisor")
    response = login(client, user.email)

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == user.email
    assert "audit:read" in body["permissions"]
    cookie = response.headers["set-cookie"]
    assert "falcon_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "password" not in response.text.lower()


def test_email_is_case_insensitive(client, make_user):
    user = make_user()
    assert login(client, user.email.upper()).status_code == 200


def test_wrong_password_and_unknown_email_get_the_same_message(client, make_user):
    user = make_user()
    wrong_password = login(client, user.email, "not-the-password")
    unknown_email = login(client, "nobody@test.example")

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()  # no account enumeration


def test_account_locks_after_repeated_failures(client, make_user):
    user = make_user()
    for _ in range(5):
        login(client, user.email, "wrong")

    # Even the correct password is refused while locked.
    assert login(client, user.email).status_code == 401
    actions = audit_actions(user.email)
    assert "auth.account_locked" in actions
    assert actions[-1] == "auth.login_blocked"


def test_inactive_user_cannot_sign_in(client, make_user):
    user = make_user(is_active=False)
    assert login(client, user.email).status_code == 401


def test_me_requires_a_session(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert "Sign in" in response.json()["detail"]


def test_logout_revokes_the_session(client, make_user):
    user = make_user()
    login(client, user.email)
    assert client.get("/api/auth/me").status_code == 200

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    assert audit_actions(user.email)[-1] == "auth.logout"


def test_stolen_database_token_hash_cannot_be_used_as_cookie(client, make_user):
    user = make_user()
    login(client, user.email)
    with SessionLocal() as db:
        token_hash = db.scalar(
            text("SELECT token_hash FROM user_sessions ORDER BY created_at DESC LIMIT 1")
        )
    client.cookies.clear()
    client.cookies.set("falcon_session", token_hash)
    assert client.get("/api/auth/me").status_code == 401


# --- CSRF -----------------------------------------------------------------------------


def test_state_changing_request_without_csrf_header_is_blocked(make_user):
    from fastapi.testclient import TestClient

    from app.main import app

    user = make_user()
    with TestClient(app) as bare_client:  # no X-FALCON-Request header
        response = login(bare_client, user.email)
    assert response.status_code == 403


# --- Authorization (RBAC) -------------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("system_admin", 200),
        ("supervisor", 200),
        ("forensic_analyst", 403),
        ("evidence_analyst", 403),
        ("investigation_officer", 403),
    ],
)
def test_user_list_requires_users_read_permission(client, make_user, role, expected):
    user = make_user(role=role)
    login(client, user.email)
    response = client.get("/api/admin/users")
    assert response.status_code == expected
    if expected == 403:
        assert audit_actions(user.email)[-1] == "access.denied"
    else:
        assert all("password_hash" not in u for u in response.json())


def test_admin_cannot_read_evidence_least_privilege(client, make_user):
    admin = make_user(role="system_admin")
    body = login(client, admin.email).json()
    assert "evidence:read" not in body["permissions"]
    assert "users:manage" in body["permissions"]


def test_database_rejects_unknown_roles(make_user):
    with pytest.raises(DBAPIError):
        make_user(role="superuser")


# --- Audit log ------------------------------------------------------------------------


def test_audit_log_is_append_only(client, make_user):
    user = make_user()
    login(client, user.email)
    with SessionLocal() as db:
        with pytest.raises(DBAPIError, match="append-only"):
            db.execute(text("UPDATE audit_log SET action = 'tampered'"))
        db.rollback()
        with pytest.raises(DBAPIError, match="append-only"):
            db.execute(text("DELETE FROM audit_log"))
