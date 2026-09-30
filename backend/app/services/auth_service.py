"""Sign in, sign out and session lookup.

Login flow:
  email + password
    → account locked?            → refuse (same message as a wrong password)
    → password correct?          → no: count failure, maybe lock, audit, refuse
    → create session token       → store only its hash, audit, return token for the cookie
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import User, UserSession
from app.security.passwords import hash_password, needs_rehash, verify_password
from app.security.tokens import hash_token, new_session_token
from app.services import audit_service
from app.services.request_context import RequestContext

# One message for every failure: never reveal whether the email exists or is locked.
INVALID_CREDENTIALS = "The email or password is incorrect, or the account is temporarily locked."


class AuthenticationError(Exception):
    pass


@dataclass(frozen=True)
class SignInResult:
    token: str
    session: UserSession
    user: User


def _now() -> datetime:
    return datetime.now(UTC)


def sign_in(
    db: Session, email: str, password: str, remember: bool, context: RequestContext
) -> SignInResult:
    settings = get_settings()
    email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    now = _now()

    # verify_password runs even for unknown emails, so both paths take the same time.
    password_ok = verify_password(user.password_hash if user else None, password)

    if user is None or not user.is_active:
        audit_service.record(
            db,
            "auth.login_failed",
            actor_email=email,
            note="unknown or inactive account",
            context=context,
        )
        db.commit()
        raise AuthenticationError(INVALID_CREDENTIALS)

    if user.locked_until and user.locked_until > now:
        audit_service.record(
            db, "auth.login_blocked", actor=user, note="account locked", context=context
        )
        db.commit()
        raise AuthenticationError(INVALID_CREDENTIALS)

    if not password_ok:
        user.failed_login_count += 1
        note = f"wrong password (failure {user.failed_login_count})"
        if user.failed_login_count >= settings.login_max_failures:
            user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
            user.failed_login_count = 0
            note += f"; locked for {settings.login_lockout_minutes} minutes"
            audit_service.record(
                db,
                "auth.account_locked",
                actor=user,
                object_type="user",
                object_id=str(user.id),
                context=context,
            )
        audit_service.record(db, "auth.login_failed", actor=user, note=note, context=context)
        db.commit()
        raise AuthenticationError(INVALID_CREDENTIALS)

    # Success
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    token = new_session_token()
    lifetime = (
        timedelta(days=settings.session_remember_days)
        if remember
        else timedelta(hours=settings.session_hours)
    )
    session = UserSession(
        user=user,
        token_hash=hash_token(token),
        expires_at=now + lifetime,
        ip_address=context.ip_address,
        user_agent=context.user_agent,
    )
    db.add(session)
    db.flush()  # assigns session.id for the audit record
    audit_service.record(
        db,
        "auth.login_succeeded",
        actor=user,
        session_id=session.id,
        note="remembered device" if remember else None,
        context=context,
    )
    db.commit()
    return SignInResult(token=token, session=session, user=user)


def session_for_token(db: Session, token: str) -> UserSession | None:
    """A valid, unexpired, unrevoked session for an active user — or None."""
    session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    now = _now()
    if (
        session is None
        or session.revoked_at is not None
        or session.expires_at <= now
        or not session.user.is_active
    ):
        return None
    # Record activity, at most once a minute (avoids a database write on every request).
    if now - session.last_seen_at > timedelta(minutes=1):
        session.last_seen_at = now
        db.commit()
    return session


def sign_out(db: Session, session: UserSession, context: RequestContext) -> None:
    session.revoked_at = _now()
    audit_service.record(
        db, "auth.logout", actor=session.user, session_id=session.id, context=context
    )
    db.commit()
