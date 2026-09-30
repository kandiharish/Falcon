"""FastAPI dependencies that protect endpoints.

Usage in a route:
    user: User = Depends(require_permission(Permission.USERS_READ))

Order of checks:  cookie present? → session valid? → role has the permission? → run the route
                        401              401                 403
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import User, UserSession
from app.security.permissions import Permission, permissions_for
from app.services import audit_service, auth_service
from app.services.request_context import request_context

NOT_SIGNED_IN = "Your session has ended or you are not signed in. Sign in to continue."
NOT_ALLOWED = "Your role does not permit this action. Contact your supervisor if you need access."


def current_session(request: Request, db: Annotated[Session, Depends(get_db)]) -> UserSession:
    token = request.cookies.get(get_settings().session_cookie_name)
    session = auth_service.session_for_token(db, token) if token else None
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, NOT_SIGNED_IN)
    return session


def current_user(session: Annotated[UserSession, Depends(current_session)]) -> User:
    return session.user


def require_permission(permission: Permission) -> Callable[..., User]:
    def dependency(
        request: Request,
        session: Annotated[UserSession, Depends(current_session)],
        db: Annotated[Session, Depends(get_db)],
    ) -> User:
        user = session.user
        if permission not in permissions_for(user.role):
            # Denied attempts are security-relevant: record them (plan §26 access monitoring).
            audit_service.record(
                db,
                "access.denied",
                actor=user,
                session_id=session.id,
                note=f"{request.method} {request.url.path} requires {permission}",
                context=request_context(request),
            )
            db.commit()
            raise HTTPException(status.HTTP_403_FORBIDDEN, NOT_ALLOWED)
        return user

    return dependency
