"""Multi-factor authentication: the TOTP maths, encryption at rest, and the sign-in flow."""

import base64

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.main import app
from app.models import User
from app.security import crypto, totp
from tests.helpers import TEST_PASSWORD, signed_in

RFC_SECRET = base64.b32encode(b"12345678901234567890").decode()  # RFC 6238 appendix B


def test_totp_matches_the_rfc_6238_test_vectors():
    # Published SHA-1 vectors (8 digits there; authenticator apps show the last 6).
    assert totp.code_at(RFC_SECRET, 59 // 30) == "287082"
    assert totp.code_at(RFC_SECRET, 1111111109 // 30) == "081804"
    assert totp.code_at(RFC_SECRET, 2000000000 // 30) == "279037"


def test_totp_accepts_clock_drift_but_never_a_replay():
    now = 1_800_000_000.0
    step = totp.current_step(now)
    assert totp.verify(RFC_SECRET, totp.code_at(RFC_SECRET, step - 1), None, now) == step - 1
    assert totp.verify(RFC_SECRET, totp.code_at(RFC_SECRET, step + 1), None, now) == step + 1
    assert totp.verify(RFC_SECRET, totp.code_at(RFC_SECRET, step - 3), None, now) is None
    assert totp.verify(RFC_SECRET, totp.code_at(RFC_SECRET, step), step, now) is None  # used
    assert totp.verify(RFC_SECRET, "12 34", None, now) is None


def test_secrets_are_encrypted_and_tampering_is_detected():
    sealed = crypto.encrypt("JBSWY3DPEHPK3PXP")
    assert sealed.startswith("v1:") and "JBSWY3DP" not in sealed
    assert crypto.encrypt("same") != crypto.encrypt("same")  # random nonce every time
    assert crypto.decrypt(sealed) == "JBSWY3DPEHPK3PXP"
    raw = bytearray(base64.urlsafe_b64decode(sealed[3:]))
    raw[-1] ^= 1
    with pytest.raises(ValueError):
        crypto.decrypt("v1:" + base64.urlsafe_b64encode(bytes(raw)).decode())


@pytest.fixture
def clock(monkeypatch):
    """A controllable clock for TOTP (each test moves time forward explicitly)."""
    now = [1_900_000_000.0]
    monkeypatch.setattr(totp.time, "time", lambda: now[0])
    return now


def _enrol(client: TestClient, clock) -> tuple[str, list[str]]:
    setup = client.post("/api/auth/mfa/setup").json()
    secret = setup["secret"]
    assert setup["uri"].startswith("otpauth://totp/FALCON") and setup["qr_svg"].startswith(
        "data:image/svg+xml"
    )
    wrong = client.post("/api/auth/mfa/confirm", json={"code": "000000"})
    assert wrong.status_code == 422
    codes = client.post(
        "/api/auth/mfa/confirm", json={"code": totp.code_at(secret, totp.current_step())}
    ).json()["recovery_codes"]
    assert len(codes) == 8 and len(set(codes)) == 8
    return secret, codes


def _password_step(email: str) -> TestClient:
    browser = TestClient(app, headers={"X-FALCON-Request": "1"})
    response = browser.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert response.status_code == 200
    assert response.json() == {"mfa_required": True, "user": None}  # nothing revealed yet
    return browser


def test_sign_in_with_mfa(make_user, clock):
    user = make_user("forensic_analyst")
    secret, recovery = _enrol(signed_in(user), clock)
    with SessionLocal() as db:
        stored = db.scalar(select(User).where(User.id == user.id))
        assert stored.mfa_enabled and stored.mfa_secret.startswith("v1:")
        assert secret not in stored.mfa_secret  # never in clear text

    clock[0] += 30  # next 30-second step
    browser = _password_step(user.email)
    assert browser.get("/api/auth/me").status_code == 401  # half signed in: nothing works
    assert browser.get("/api/investigations").status_code == 401
    assert browser.post("/api/auth/mfa/verify", json={"code": "123456"}).status_code == 401
    verified = browser.post(
        "/api/auth/mfa/verify", json={"code": totp.code_at(secret, totp.current_step())}
    )
    assert verified.status_code == 200 and verified.json()["email"] == user.email
    assert browser.get("/api/auth/me").status_code == 200

    # The same code cannot be used again (replay), even on a fresh sign-in.
    again = _password_step(user.email)
    assert (
        again.post(
            "/api/auth/mfa/verify", json={"code": totp.code_at(secret, totp.current_step())}
        ).status_code
        == 401
    )

    # A recovery code works exactly once.
    first = _password_step(user.email)
    assert first.post("/api/auth/mfa/verify", json={"code": recovery[0].upper()}).status_code == 200
    second = _password_step(user.email)
    assert second.post("/api/auth/mfa/verify", json={"code": recovery[0]}).status_code == 401


def test_wrong_codes_lock_the_account(make_user, clock):
    user = make_user("forensic_analyst")
    _enrol(signed_in(user), clock)
    browser = _password_step(user.email)
    for _ in range(5):
        browser.post("/api/auth/mfa/verify", json={"code": "999999"})
    blocked = TestClient(app, headers={"X-FALCON-Request": "1"}).post(
        "/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD}
    )
    assert blocked.status_code == 401  # locked, even with the right password


def test_turning_mfa_off_needs_password_and_code_and_admins_can_reset(make_user, clock):
    user = make_user("forensic_analyst")
    client = signed_in(user)
    secret, _ = _enrol(client, clock)
    clock[0] += 30
    code = totp.code_at(secret, totp.current_step())
    assert (
        client.post(
            "/api/auth/mfa/disable", json={"password": "wrong-password", "code": code}
        ).status_code
        == 401
    )
    clock[0] += 30
    code = totp.code_at(secret, totp.current_step())
    assert (
        client.post(
            "/api/auth/mfa/disable", json={"password": TEST_PASSWORD, "code": code}
        ).status_code
        == 204
    )
    assert client.get("/api/auth/me").json()["mfa_enabled"] is False

    _enrol(client, clock)
    admin = signed_in(make_user("system_admin"))
    reset = admin.post(f"/api/admin/users/{user.id}/reset-mfa")
    assert reset.json()["mfa_enabled"] is False
    assert client.get("/api/auth/me").status_code == 401  # lost-phone reset ends sessions


def test_people_see_and_end_their_own_sessions(make_user):
    user = make_user("forensic_analyst")
    laptop, phone = signed_in(user), signed_in(user)
    sessions = laptop.get("/api/auth/sessions").json()
    assert len(sessions) == 2 and sum(s["current"] for s in sessions) == 1
    other = next(s for s in sessions if not s["current"])
    assert laptop.delete(f"/api/auth/sessions/{other['id']}").status_code == 204
    assert phone.get("/api/auth/me").status_code == 401
    stranger = signed_in(make_user("forensic_analyst"))
    mine = laptop.get("/api/auth/sessions").json()[0]["id"]
    assert stranger.delete(f"/api/auth/sessions/{mine}").status_code == 404  # not yours
