"""Request/response shapes shared by API routes. Never expose password hashes or tokens."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.models import AuditLog, User
from app.security.permissions import permissions_for


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)
    remember: bool = False


class CurrentUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: str
    permissions: list[str]
    mfa_enabled: bool
    session_expires_at: datetime

    @classmethod
    def build(cls, user: User, session_expires_at: datetime) -> "CurrentUserResponse":
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            permissions=sorted(permissions_for(user.role)),
            mfa_enabled=user.mfa_enabled,
            session_expires_at=session_expires_at,
        )


class UserSummary(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: str
    is_active: bool
    mfa_enabled: bool
    locked: bool
    last_login_at: datetime | None
    created_at: datetime


class AuditEntry(BaseModel):
    id: int
    occurred_at: datetime
    actor_email: str | None
    action: str
    object_type: str | None
    object_id: str | None
    previous_state: dict[str, Any] | None
    new_state: dict[str, Any] | None
    note: str | None
    ip_address: str | None


def audit_entry(row: AuditLog) -> AuditEntry:
    return AuditEntry(
        id=row.id,
        occurred_at=row.occurred_at,
        actor_email=row.actor_email,
        action=row.action,
        object_type=row.object_type,
        object_id=row.object_id,
        previous_state=row.previous_state,
        new_state=row.new_state,
        note=row.note,
        ip_address=str(row.ip_address) if row.ip_address else None,
    )
