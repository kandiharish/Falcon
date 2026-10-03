"""Refuse to start in production with unsafe settings ("fail closed").

A forgotten development setting in production is one of the most common security mistakes.
Instead of a checklist someone might skip, the server checks itself at start-up and lists
every problem. ENVIRONMENT=development skips the checks.
"""

from app.core.config import Settings

WEAK_PASSWORDS = {"", "postgres", "password", "falcon", "changeme", "admin"}


def problems(settings: Settings) -> list[str]:
    found: list[str] = []
    if not settings.session_cookie_secure:
        found.append("SESSION_COOKIE_SECURE must be true: production runs behind HTTPS.")
    key = settings.falcon_secret_key.get_secret_value() if settings.falcon_secret_key else ""
    if len(key) < 32:
        found.append("FALCON_SECRET_KEY must be set to at least 32 random characters.")
    db_password = settings.postgres_password.get_secret_value()
    if len(db_password) < 16 or db_password.lower() in WEAK_PASSWORDS:
        found.append("POSTGRES_PASSWORD must be at least 16 characters and not a common word.")
    if settings.demo_password is not None:
        found.append("DEMO_PASSWORD must not be set in production (no demo accounts).")
    return found


def check(settings: Settings) -> None:
    if settings.environment != "production":
        return
    found = problems(settings)
    if found:
        raise RuntimeError(
            "FALCON will not start in production with unsafe settings:\n  - " + "\n  - ".join(found)
        )
