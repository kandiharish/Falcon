"""Create (or update) one fictional demo user per role. Development only.

    uv run python -m app.scripts.seed_demo_users

The shared demo password is read from DEMO_PASSWORD in .env — it is never written in code.
"""

import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import User
from app.security.passwords import hash_password
from app.security.permissions import Role
from app.services import audit_service

DEMO_USERS: list[tuple[str, str, Role]] = [
    ("admin@falcon.example", "S. Rao", Role.SYSTEM_ADMIN),
    ("k.iyer@falcon.example", "SI K. Iyer", Role.SUPERVISOR),
    ("r.varma@falcon.example", "Insp. R. Varma", Role.INVESTIGATION_OFFICER),
    ("a.kumar@falcon.example", "A. Kumar", Role.FORENSIC_ANALYST),
    ("m.das@falcon.example", "M. Das", Role.EVIDENCE_ANALYST),
    ("a.menon@falcon.example", "A. Menon", Role.INCIDENT_INVESTIGATOR),
]


def main() -> int:
    settings = get_settings()
    if settings.environment != "development":
        print("Refusing to seed demo users outside development.")
        return 1
    if settings.demo_password is None:
        print("Set DEMO_PASSWORD in .env first.")
        return 1

    password_hash = hash_password(settings.demo_password.get_secret_value())
    with SessionLocal() as db:
        for email, name, role in DEMO_USERS:
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                db.add(User(email=email, display_name=name, role=role, password_hash=password_hash))
                audit_service.record(
                    db,
                    "user.created",
                    actor_email="seed-script",
                    object_type="user",
                    object_id=email,
                    new_state={"role": role, "display_name": name},
                    note="demo user",
                )
                print(f"created  {email:28} {role}")
            else:
                user.display_name, user.role, user.password_hash = name, role, password_hash
                user.failed_login_count, user.locked_until = 0, None
                print(f"updated  {email:28} {role}")
        db.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
