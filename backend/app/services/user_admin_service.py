"""User management for administrators (plan §31): create, change, lock out, recover.

Safety rules:
  • every change is audited with before/after values (never the password itself);
  • deactivating, changing role or resetting a password ends ALL of that user's sessions,
    so the change takes effect immediately, not at their next sign-in;
  • an administrator cannot deactivate or demote themselves (no locking yourself out);
  • passwords: at least 12 characters, and not the email address.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import User, UserSession
from app.security.passwords import hash_password
from app.security.permissions import Role
from app.services import audit_service
from app.services.errors import ConflictError, InvalidInputError, NotFoundError
from app.services.request_context import RequestContext

MIN_PASSWORD = 12


def check_password(password: str, email: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise InvalidInputError(f"Use a password of at least {MIN_PASSWORD} characters.")
    if password.strip().lower() == email.strip().lower():
        raise InvalidInputError("The password must not be the email address.")


def revoke_sessions(db: Session, user_id: uuid.UUID) -> int:
    return db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    ).rowcount


def _get(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("No such user.")
    return user


def _state(user: User) -> dict[str, Any]:
    return {
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
        "mfa_enabled": user.mfa_enabled,
    }


def create_user(
    db: Session,
    admin: User,
    email: str,
    display_name: str,
    role: str,
    password: str,
    context: RequestContext,
) -> User:
    email = email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise ConflictError("A user with this email address already exists.")
    if role not in {r.value for r in Role}:
        raise InvalidInputError("Unknown role.")
    check_password(password, email)
    user = User(
        email=email,
        display_name=display_name.strip(),
        role=role,
        password_hash=hash_password(password),
        is_active=True,
    )
    db.add(user)
    db.flush()
    audit_service.record(
        db,
        "user.created",
        actor=admin,
        object_type="user",
        object_id=user.email,
        new_state=_state(user),
        context=context,
    )
    db.commit()
    return user


def update_user(
    db: Session, admin: User, user_id: uuid.UUID, changes: dict[str, Any], context: RequestContext
) -> User:
    user = _get(db, user_id)
    before = _state(user)
    if user.id == admin.id and (
        changes.get("is_active") is False or ("role" in changes and changes["role"] != user.role)
    ):
        raise ConflictError("You cannot deactivate your own account or change your own role.")
    if "role" in changes and changes["role"] not in {r.value for r in Role}:
        raise InvalidInputError("Unknown role.")
    for field in ("display_name", "role", "is_active"):
        if field in changes and changes[field] is not None:
            setattr(
                user, field, changes[field].strip() if field == "display_name" else changes[field]
            )
    after = _state(user)
    changed = {k for k in after if after[k] != before[k]}
    if not changed:
        return user
    ended = 0
    if {"role", "is_active"} & changed:
        ended = revoke_sessions(db, user.id)  # take effect now, not at the next sign-in
    audit_service.record(
        db,
        "user.updated",
        actor=admin,
        object_type="user",
        object_id=user.email,
        previous_state={k: before[k] for k in changed},
        new_state={k: after[k] for k in changed},
        note=f"{ended} session(s) ended" if ended else None,
        context=context,
    )
    db.commit()
    return user


def unlock(db: Session, admin: User, user_id: uuid.UUID, context: RequestContext) -> User:
    user = _get(db, user_id)
    user.locked_until = None
    user.failed_login_count = 0
    audit_service.record(
        db, "user.unlocked", actor=admin, object_type="user", object_id=user.email, context=context
    )
    db.commit()
    return user


def set_temporary_password(
    db: Session, admin: User, user_id: uuid.UUID, password: str, context: RequestContext
) -> User:
    user = _get(db, user_id)
    check_password(password, user.email)
    user.password_hash = hash_password(password)
    user.locked_until, user.failed_login_count = None, 0
    ended = revoke_sessions(db, user.id)
    audit_service.record(
        db,
        "user.password_reset",
        actor=admin,
        object_type="user",
        object_id=user.email,
        note=f"temporary password set; {ended} session(s) ended",
        context=context,
    )
    db.commit()
    return user
