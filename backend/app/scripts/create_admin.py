"""Create a system administrator — how the FIRST account is made in production.

    python -m app.scripts.create_admin                      (asks for email, name, password)

Or without questions (e.g. automation), from the environment:
    FALCON_ADMIN_EMAIL, FALCON_ADMIN_NAME, FALCON_ADMIN_PASSWORD

The password is typed hidden and never printed or logged. The administrator then creates
everyone else from Administration → Users (and should turn on MFA straight away).
"""

import getpass
import os
import sys

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import User
from app.security.passwords import hash_password
from app.security.permissions import Role
from app.services import audit_service
from app.services.user_admin_service import check_password


def main() -> int:
    email = os.environ.get("FALCON_ADMIN_EMAIL") or input("Administrator email: ")
    name = os.environ.get("FALCON_ADMIN_NAME") or input("Display name: ")
    password = os.environ.get("FALCON_ADMIN_PASSWORD") or getpass.getpass("Password (hidden): ")
    email = email.strip().lower()
    try:
        check_password(password, email)
    except Exception as error:
        print(getattr(error, "message", str(error)))
        return 1
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            print("A user with this email already exists.")
            return 1
        user = User(
            email=email,
            display_name=name.strip() or email,
            role=Role.SYSTEM_ADMIN,
            password_hash=hash_password(password),
            is_active=True,
        )
        db.add(user)
        db.flush()
        audit_service.record(
            db,
            "user.created",
            actor_email="create_admin (server console)",
            object_type="user",
            object_id=email,
            new_state={"role": Role.SYSTEM_ADMIN, "display_name": user.display_name},
        )
        db.commit()
    print(f"Administrator {email} created. Sign in and turn on MFA under Account security.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
