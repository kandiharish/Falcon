"""Multi-factor authentication (plan §26): set up, confirm, verify at sign-in, turn off.

    SETUP     new secret → stored encrypted as "pending" → QR code shown once
    CONFIRM   first valid code proves the phone has it → MFA on → 8 recovery codes shown once
    SIGN-IN   password ✓ → session "MFA pending" (5 min, can only verify) → code ✓ → full session
    RECOVER   a recovery code works once instead of a phone code
    OFF       needs the password AND a current code (a stolen session alone is not enough)

Wrong codes count towards the same lockout as wrong passwords.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import segno
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import User, UserSession
from app.security import crypto, totp
from app.security.passwords import verify_password
from app.services import audit_service
from app.services.errors import ConflictError, DomainError, InvalidInputError
from app.services.request_context import RequestContext


class MfaUnavailable(DomainError):
    status_code = 503


class CodeRejected(DomainError):
    status_code = 401


@dataclass(frozen=True)
class SetupInfo:
    secret: str  # shown once, for typing in by hand
    uri: str
    qr_svg_data_uri: str


def start_setup(db: Session, user: User, context: RequestContext) -> SetupInfo:
    if user.mfa_enabled:
        raise ConflictError("Multi-factor authentication is already on for your account.")
    secret = totp.new_secret()
    try:
        user.mfa_pending_secret = crypto.encrypt(secret)
    except crypto.CryptoUnavailable as error:
        raise MfaUnavailable(str(error)) from error
    uri = totp.provisioning_uri(secret, user.email)
    # A complete SVG data: URI (with its XML namespace, which an <img> needs).
    data_uri = segno.make(uri, error="m").svg_data_uri(scale=5, dark="#000", light="#fff", border=2)
    audit_service.record(db, "auth.mfa_setup_started", actor=user, context=context)
    db.commit()
    return SetupInfo(secret=secret, uri=uri, qr_svg_data_uri=data_uri)


def confirm_setup(db: Session, user: User, code: str, context: RequestContext) -> list[str]:
    if user.mfa_enabled or not user.mfa_pending_secret:
        raise ConflictError("Start the set-up first.")
    secret = crypto.decrypt(user.mfa_pending_secret)
    step = totp.verify(secret, code, None)
    if step is None:
        raise InvalidInputError(
            "That code is not right. Check the phone's clock and type the newest code."
        )
    recovery = totp.new_recovery_codes()
    user.mfa_secret, user.mfa_pending_secret = user.mfa_pending_secret, None
    user.mfa_last_step = step
    user.mfa_recovery_hashes = [totp.hash_recovery_code(c) for c in recovery]
    user.mfa_enabled = True
    audit_service.record(
        db,
        "auth.mfa_enabled",
        actor=user,
        object_type="user",
        object_id=user.email,
        context=context,
    )
    db.commit()
    return recovery  # shown to the user once; only their hashes are stored


def _check_code(user: User, code: str) -> str | None:
    """'totp' or 'recovery' when the code is valid (and consumes it), else None."""
    secret = crypto.decrypt(user.mfa_secret or "")
    step = totp.verify(secret, code, user.mfa_last_step)
    if step is not None:
        user.mfa_last_step = step
        return "totp"
    hashed = totp.hash_recovery_code(code)
    if hashed in (user.mfa_recovery_hashes or []):
        user.mfa_recovery_hashes = [h for h in user.mfa_recovery_hashes if h != hashed]
        return "recovery"
    return None


def verify_sign_in(
    db: Session, session: UserSession, code: str, context: RequestContext
) -> UserSession:
    settings = get_settings()
    user = session.user
    if not session.mfa_pending:
        return session
    used = _check_code(user, code)
    now = datetime.now(UTC)
    if used is None:
        user.failed_login_count += 1
        note = f"wrong MFA code (failure {user.failed_login_count})"
        if user.failed_login_count >= settings.login_max_failures:
            user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
            user.failed_login_count = 0
            session.revoked_at = now
            note += f"; locked for {settings.login_lockout_minutes} minutes"
        audit_service.record(
            db, "auth.mfa_failed", actor=user, session_id=session.id, note=note, context=context
        )
        db.commit()
        raise CodeRejected("The verification code is not right.")
    user.failed_login_count = 0
    session.mfa_pending = False
    lifetime = (
        timedelta(days=settings.session_remember_days)
        if session.remember
        else timedelta(hours=settings.session_hours)
    )
    session.expires_at = now + lifetime
    left = len(user.mfa_recovery_hashes or [])
    audit_service.record(
        db,
        "auth.mfa_verified",
        actor=user,
        session_id=session.id,
        note=f"recovery code used; {left} left" if used == "recovery" else None,
        context=context,
    )
    db.commit()
    return session


def disable(db: Session, user: User, password: str, code: str, context: RequestContext) -> None:
    if not user.mfa_enabled:
        return
    if not verify_password(user.password_hash, password) or _check_code(user, code) is None:
        db.commit()  # keep a consumed recovery code consumed
        raise CodeRejected("The password or the verification code is not right.")
    clear(user)
    audit_service.record(
        db,
        "auth.mfa_disabled",
        actor=user,
        object_type="user",
        object_id=user.email,
        context=context,
    )
    db.commit()


def clear(user: User) -> None:
    user.mfa_enabled = False
    user.mfa_secret = user.mfa_pending_secret = None
    user.mfa_last_step = None
    user.mfa_recovery_hashes = []
