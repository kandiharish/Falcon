"""/api/auth — sign in (with MFA), sign out, who am I, account security."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.schemas import CurrentUserResponse, LoginRequest
from app.core.config import get_settings
from app.db.session import get_db
from app.models import UserSession
from app.security.dependencies import current_session, pending_or_current_session
from app.security.rate_limit import limit
from app.services import auth_service, mfa_service
from app.services.request_context import request_context

router = APIRouter(prefix="/auth", tags=["auth"])
DB = Annotated[Session, Depends(get_db)]
Current = Annotated[UserSession, Depends(current_session)]
PendingOrCurrent = Annotated[UserSession, Depends(pending_or_current_session)]


class LoginResponse(BaseModel):
    """With MFA on, nothing about the account is revealed until the code is verified."""

    mfa_required: bool
    user: CurrentUserResponse | None


class CodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=20)


class MfaSetupOut(BaseModel):
    secret: str
    uri: str
    qr_svg: str  # a data: URI for an <img>


class RecoveryCodesOut(BaseModel):
    recovery_codes: list[str]


class DisableIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=6, max_length=20)


class SessionOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    ip_address: str | None
    user_agent: str | None
    current: bool


def _set_session_cookie(response: Response, token: str, max_age: int | None) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=max_age,  # None = cookie ends when the browser closes
        httponly=True,  # JavaScript cannot read it → XSS cannot steal it
        secure=settings.session_cookie_secure,  # HTTPS only (on in production)
        samesite="lax",  # not sent on cross-site POSTs → CSRF defence
        path="/",
    )


@router.post("/login", response_model=LoginResponse, dependencies=[Depends(limit("login", 10))])
def login(body: LoginRequest, request: Request, response: Response, db: DB) -> LoginResponse:
    try:
        result = auth_service.sign_in(
            db, body.email, body.password, body.remember, request_context(request)
        )
    except auth_service.AuthenticationError as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(error)) from None

    max_age = get_settings().session_remember_days * 86400 if body.remember else None
    _set_session_cookie(response, result.token, max_age)
    if result.session.mfa_pending:
        return LoginResponse(mfa_required=True, user=None)
    return LoginResponse(
        mfa_required=False, user=CurrentUserResponse.build(result.user, result.session.expires_at)
    )


@router.post(
    "/mfa/verify", response_model=CurrentUserResponse, dependencies=[Depends(limit("mfa", 10))]
)
def verify_code(
    body: CodeIn, request: Request, session: PendingOrCurrent, db: DB
) -> CurrentUserResponse:
    """Second step of sign-in: the 6-digit code (or a recovery code)."""
    session = mfa_service.verify_sign_in(db, session, body.code, request_context(request))
    return CurrentUserResponse.build(session.user, session.expires_at)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, session: PendingOrCurrent, db: DB) -> None:
    auth_service.sign_out(db, session, request_context(request))
    response.delete_cookie(get_settings().session_cookie_name, path="/")


@router.get("/me", response_model=CurrentUserResponse)
def me(session: Current) -> CurrentUserResponse:
    return CurrentUserResponse.build(session.user, session.expires_at)


@router.post("/mfa/setup", response_model=MfaSetupOut)
def mfa_setup(request: Request, session: Current, db: DB) -> MfaSetupOut:
    info = mfa_service.start_setup(db, session.user, request_context(request))
    return MfaSetupOut(secret=info.secret, uri=info.uri, qr_svg=info.qr_svg_data_uri)


@router.post("/mfa/confirm", response_model=RecoveryCodesOut)
def mfa_confirm(body: CodeIn, request: Request, session: Current, db: DB) -> RecoveryCodesOut:
    codes = mfa_service.confirm_setup(db, session.user, body.code, request_context(request))
    return RecoveryCodesOut(recovery_codes=codes)


@router.post("/mfa/disable", status_code=status.HTTP_204_NO_CONTENT)
def mfa_disable(body: DisableIn, request: Request, session: Current, db: DB) -> None:
    mfa_service.disable(db, session.user, body.password, body.code, request_context(request))


@router.get("/sessions", response_model=list[SessionOut])
def my_sessions(session: Current, db: DB) -> list[SessionOut]:
    return [
        SessionOut(
            id=s.id,
            created_at=s.created_at,
            last_seen_at=s.last_seen_at,
            expires_at=s.expires_at,
            ip_address=str(s.ip_address) if s.ip_address else None,
            user_agent=s.user_agent,
            current=s.id == session.id,
        )
        for s in auth_service.active_sessions(db, session.user)
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def end_session(session_id: uuid.UUID, request: Request, session: Current, db: DB) -> None:
    try:
        auth_service.revoke_own_session(
            db, session.user, session_id, session, request_context(request)
        )
    except auth_service.AuthenticationError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from None
