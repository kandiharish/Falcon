"""/api/admin and /api/audit — administration and the audit trail (permission-protected)."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import AuditEntry, UserSummary
from app.db.session import get_db
from app.models import AuditLog, User
from app.security.dependencies import require_permission
from app.security.permissions import Permission

router = APIRouter(tags=["administration"])


@router.get("/admin/users", response_model=list[UserSummary])
def list_users(
    _: Annotated[User, Depends(require_permission(Permission.USERS_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> list[UserSummary]:
    now = datetime.now(UTC)
    users = db.scalars(select(User).order_by(User.display_name)).all()
    return [
        UserSummary(
            id=u.id,
            email=u.email,
            display_name=u.display_name,
            role=u.role,
            is_active=u.is_active,
            mfa_enabled=u.mfa_enabled,
            locked=bool(u.locked_until and u.locked_until > now),
            last_login_at=u.last_login_at,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.get("/audit", response_model=list[AuditEntry])
def list_audit_entries(
    _: Annotated[User, Depends(require_permission(Permission.AUDIT_READ))],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AuditEntry]:
    rows = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)).all()
    return [
        AuditEntry(
            id=r.id,
            occurred_at=r.occurred_at,
            actor_email=r.actor_email,
            action=r.action,
            object_type=r.object_type,
            object_id=r.object_id,
            previous_state=r.previous_state,
            new_state=r.new_state,
            note=r.note,
            ip_address=str(r.ip_address) if r.ip_address else None,
        )
        for r in rows
    ]
