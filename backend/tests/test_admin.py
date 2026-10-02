"""User management and the audit-log reader."""

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import signed_in

TEMP = "a-long-temporary-passphrase"


def _login(email: str, password: str) -> TestClient:
    client = TestClient(app, headers={"X-FALCON-Request": "1"})
    assert (
        client.post("/api/auth/login", json={"email": email, "password": password}).status_code
        == 200
    )
    return client


def test_admin_creates_changes_and_deactivates_users(make_user):
    admin = signed_in(make_user("system_admin"))
    created = admin.post(
        "/api/admin/users",
        json={
            "email": "New.Analyst@Falcon.example",
            "display_name": "New Analyst",
            "role": "evidence_analyst",
            "temporary_password": TEMP,
        },
    )
    assert created.status_code == 201, created.text
    user = created.json()
    assert user["email"] == "new.analyst@falcon.example"
    newcomer = _login("new.analyst@falcon.example", TEMP)
    assert newcomer.get("/api/auth/me").json()["role"] == "evidence_analyst"

    promoted = admin.patch(f"/api/admin/users/{user['id']}", json={"role": "forensic_analyst"})
    assert promoted.json()["role"] == "forensic_analyst"
    assert newcomer.get("/api/auth/me").status_code == 401  # role change ends old sessions

    admin.patch(f"/api/admin/users/{user['id']}", json={"is_active": False})
    login = TestClient(app, headers={"X-FALCON-Request": "1"}).post(
        "/api/auth/login", json={"email": "new.analyst@falcon.example", "password": TEMP}
    )
    assert login.status_code == 401

    duplicate = admin.post(
        "/api/admin/users",
        json={
            "email": "new.analyst@falcon.example",
            "display_name": "Again",
            "role": "evidence_analyst",
            "temporary_password": TEMP,
        },
    )
    assert duplicate.status_code == 409


def test_admin_cannot_lock_themselves_out_and_others_cannot_manage(make_user):
    admin_user = make_user("system_admin")
    admin = signed_in(admin_user)
    me = admin.get("/api/auth/me").json()["id"]
    assert admin.patch(f"/api/admin/users/{me}", json={"is_active": False}).status_code == 409
    assert admin.patch(f"/api/admin/users/{me}", json={"role": "supervisor"}).status_code == 409
    weak = admin.post(f"/api/admin/users/{me}/password", json={"temporary_password": "short"})
    assert weak.status_code == 422

    supervisor = signed_in(make_user("supervisor"))
    assert supervisor.get("/api/admin/users").status_code == 200  # may look…
    body = {
        "email": "x@falcon.example",
        "display_name": "X",
        "role": "supervisor",
        "temporary_password": TEMP,
    }
    assert supervisor.post("/api/admin/users", json=body).status_code == 403  # …not change


def test_password_reset_and_unlock(make_user):
    admin = signed_in(make_user("system_admin"))
    target = make_user("investigation_officer")
    old_session = signed_in(target)
    reset = admin.post(f"/api/admin/users/{target.id}/password", json={"temporary_password": TEMP})
    assert reset.status_code == 200
    assert old_session.get("/api/auth/me").status_code == 401
    _login(target.email, TEMP)
    assert admin.post(f"/api/admin/users/{target.id}/unlock").json()["locked"] is False


def test_audit_log_filters_pages_and_exports(make_user):
    admin = signed_in(make_user("system_admin"))
    admin.post(
        "/api/admin/users",
        json={
            "email": "audited@falcon.example",
            "display_name": "Audited",
            "role": "evidence_analyst",
            "temporary_password": TEMP,
        },
    )
    page = admin.get("/api/audit", params={"action": "user.", "object": "audited@"}).json()
    assert page["total"] == 1 and page["items"][0]["action"] == "user.created"
    assert page["items"][0]["new_state"]["role"] == "evidence_analyst"
    assert "password" not in str(page["items"][0]).lower()  # never the password

    csv = admin.get("/api/audit/export.csv", params={"object": "audited@"})
    assert csv.headers["content-type"].startswith("text/csv")
    assert "user.created" in csv.text
    exported = admin.get("/api/audit", params={"action": "audit.exported"}).json()
    assert exported["total"] >= 1  # exporting the audit log is itself audited

    analyst = signed_in(make_user("forensic_analyst"))
    assert analyst.get("/api/audit").status_code == 403
