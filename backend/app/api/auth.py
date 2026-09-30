"""/api/auth — sign in, sign out, who am I."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.schemas import CurrentUserResponse, LoginRequest
from app.core.config import get_settings
from app.db.session import get_db
from app.models import UserSession
from app.security.dependencies import current_session
from app.services import auth_service
from app.services.request_context import request_context

router = APIRouter(prefix="/auth", tags=["auth"])


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


@router.post("/login", response_model=CurrentUserResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> CurrentUserResponse:
    try:
        result = auth_service.sign_in(
            db, body.email, body.password, body.remember, request_context(request)
        )
    except auth_service.AuthenticationError as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(error)) from None

    max_age = get_settings().session_remember_days * 86400 if body.remember else None
    _set_session_cookie(response, result.token, max_age)
    return CurrentUserResponse.build(result.user, result.session.expires_at)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    session: Annotated[UserSession, Depends(current_session)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    auth_service.sign_out(db, session, request_context(request))
    response.delete_cookie(get_settings().session_cookie_name, path="/")


@router.get("/me", response_model=CurrentUserResponse)
def me(session: Annotated[UserSession, Depends(current_session)]) -> CurrentUserResponse:
    return CurrentUserResponse.build(session.user, session.expires_at)
