"""Security hardening: response headers, rate limits, production start-up checks."""

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core import production
from app.core.config import get_settings
from app.main import app
from app.security.rate_limit import SlidingWindow


def test_every_api_response_carries_security_headers(client):
    response = client.get("/api/health")
    h = response.headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert h["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in h["content-security-policy"]
    assert h["cache-control"] == "no-store"
    assert "strict-transport-security" not in h  # only when served over HTTPS
    # Errors get them too.
    assert client.get("/api/does-not-exist").headers["x-frame-options"] == "DENY"


def test_sliding_window():
    window = SlidingWindow()
    assert all(window.hit("k", 3, 60, now=t) == 0 for t in (0, 1, 2))
    assert window.hit("k", 3, 60, now=10) == pytest.approx(50)  # 4th inside the minute: wait
    assert window.hit("k", 3, 60, now=61) == 0  # the first one has left the window
    assert window.hit("other", 3, 60, now=10) == 0  # buckets are separate


def test_sign_in_is_rate_limited_per_address(make_user):
    user = make_user("forensic_analyst")
    browser = TestClient(app, headers={"X-FALCON-Request": "1"})
    codes = [
        browser.post("/api/auth/login", json={"email": user.email, "password": "wrong"}).status_code
        for _ in range(11)
    ]
    assert codes[:10].count(401) == 10 and codes[10] == 429
    blocked = browser.post("/api/auth/login", json={"email": user.email, "password": "wrong"})
    assert int(blocked.headers["retry-after"]) >= 1


def test_production_refuses_unsafe_settings():
    unsafe = get_settings().model_copy(
        update={
            "environment": "production",
            "session_cookie_secure": False,
            "falcon_secret_key": SecretStr("short"),
            "postgres_password": SecretStr("postgres"),
            "demo_password": SecretStr("demo"),
        }
    )
    with pytest.raises(RuntimeError) as error:
        production.check(unsafe)
    message = str(error.value)
    for setting in (
        "SESSION_COOKIE_SECURE",
        "FALCON_SECRET_KEY",
        "POSTGRES_PASSWORD",
        "DEMO_PASSWORD",
    ):
        assert setting in message
    safe = unsafe.model_copy(
        update={
            "session_cookie_secure": True,
            "falcon_secret_key": SecretStr("x" * 40),
            "postgres_password": SecretStr("a-long-database-passphrase"),
            "demo_password": None,
        }
    )
    production.check(safe)  # no exception
    production.check(get_settings())  # development: never blocks
