"""/api/admin and /api/audit — administration and the audit trail (permission-protected)."""

import csv
import io
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas import AuditEntry, UserSummary, audit_entry
from app.db.session import get_db
from app.models import AuditLog, User
from app.security.dependencies import require_permission
from app.security.permissions import Permission
from app.services import audit_service, user_admin_service
from app.services.request_context import request_context

router = APIRouter(tags=["administration"])
DB = Annotated[Session, Depends(get_db)]
UserReader = Annotated[User, Depends(require_permission(Permission.USERS_READ))]
UserManager = Annotated[User, Depends(require_permission(Permission.USERS_MANAGE))]
AuditReader = Annotated[User, Depends(require_permission(Permission.AUDIT_READ))]

RoleName = Literal[
    "investigation_officer",
    "forensic_analyst",
    "evidence_analyst",
    "incident_investigator",
    "supervisor",
    "system_admin",
]


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=120)
    role: RoleName
    temporary_password: str = Field(min_length=12, max_length=200)


class UserPatch(BaseModel):
    display_name: str | None = Field(None, min_length=2, max_length=120)
    role: RoleName | None = None
    is_active: bool | None = None


class PasswordReset(BaseModel):
    temporary_password: str = Field(min_length=12, max_length=200)


class AuditPage(BaseModel):
    items: list[AuditEntry]
    total: int


def _summary(u: User) -> UserSummary:
    now = datetime.now(UTC)
    return UserSummary(
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


@router.get("/admin/users", response_model=list[UserSummary])
def list_users(_: UserReader, db: DB) -> list[UserSummary]:
    return [_summary(u) for u in db.scalars(select(User).order_by(User.display_name))]


@router.post("/admin/users", response_model=UserSummary, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, request: Request, admin: UserManager, db: DB) -> UserSummary:
    user = user_admin_service.create_user(
        db,
        admin,
        body.email,
        body.display_name,
        body.role,
        body.temporary_password,
        request_context(request),
    )
    return _summary(user)


@router.patch("/admin/users/{user_id}", response_model=UserSummary)
def update_user(
    user_id: uuid.UUID, body: UserPatch, request: Request, admin: UserManager, db: DB
) -> UserSummary:
    changes = body.model_dump(exclude_unset=True)
    return _summary(
        user_admin_service.update_user(db, admin, user_id, changes, request_context(request))
    )


@router.post("/admin/users/{user_id}/unlock", response_model=UserSummary)
def unlock(user_id: uuid.UUID, request: Request, admin: UserManager, db: DB) -> UserSummary:
    return _summary(user_admin_service.unlock(db, admin, user_id, request_context(request)))


@router.post("/admin/users/{user_id}/password", response_model=UserSummary)
def reset_password(
    user_id: uuid.UUID, body: PasswordReset, request: Request, admin: UserManager, db: DB
) -> UserSummary:
    user = user_admin_service.set_temporary_password(
        db, admin, user_id, body.temporary_password, request_context(request)
    )
    return _summary(user)


# ---------- Audit log -----------------------------------------------------------------------


def _audit_query(
    action: str | None,
    actor: str | None,
    obj: str | None,
    day_from: date | None,
    day_to: date | None,
):
    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action.ilike(f"{action}%"))
    if actor:
        query = query.where(AuditLog.actor_email.ilike(f"%{actor}%"))
    if obj:
        query = query.where(AuditLog.object_id.ilike(f"%{obj}%"))
    if day_from:
        query = query.where(AuditLog.occurred_at >= datetime.combine(day_from, time.min, UTC))
    if day_to:
        query = query.where(
            AuditLog.occurred_at < datetime.combine(day_to + timedelta(days=1), time.min, UTC)
        )
    return query


Filter = Annotated[str | None, Query(max_length=100)]


@router.get("/audit", response_model=AuditPage)
def list_audit_entries(
    _: AuditReader,
    db: DB,
    action: Filter = None,
    actor: Filter = None,
    object: Filter = None,  # noqa: A002 - the API's word for "what was acted on"
    date_from: date | None = None,
    date_to: date | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditPage:
    query = _audit_query(action, actor, object, date_from, date_to)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(AuditLog.id.desc()).limit(limit).offset(offset)).all()
    return AuditPage(items=[audit_entry(r) for r in rows], total=total)


@router.get("/audit/export.csv")
def export_audit(
    request: Request,
    user: AuditReader,
    db: DB,
    action: Filter = None,
    actor: Filter = None,
    object: Filter = None,  # noqa: A002
    date_from: date | None = None,
    date_to: date | None = None,
) -> Response:
    """The filtered audit trail as CSV (max 10,000 rows). Exporting is itself audited."""
    rows = db.scalars(
        _audit_query(action, actor, object, date_from, date_to).order_by(AuditLog.id).limit(10_000)
    ).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["id", "occurred_at", "actor", "action", "object_type", "object_id", "ip", "note"]
    )
    for r in rows:
        entry = audit_entry(r)
        writer.writerow(
            [
                entry.id,
                entry.occurred_at.isoformat(),
                entry.actor_email or "",
                entry.action,
                entry.object_type or "",
                entry.object_id or "",
                entry.ip_address or "",
                entry.note or "",
            ]
        )
    audit_service.record(
        db,
        "audit.exported",
        actor=user,
        new_state={
            "rows": len(rows),
            "filters": {
                "action": action,
                "actor": actor,
                "object": object,
                "date_from": str(date_from) if date_from else None,
                "date_to": str(date_to) if date_to else None,
            },
        },
        context=request_context(request),
    )
    db.commit()
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="falcon-audit.csv"'},
    )
