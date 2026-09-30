"""Writes audit records. The only code path that touches the audit_log table."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, User
from app.services.request_context import RequestContext


def record(
    db: Session,
    action: str,
    *,
    actor: User | None = None,
    actor_email: str | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
    previous_state: dict[str, Any] | None = None,
    new_state: dict[str, Any] | None = None,
    note: str | None = None,
    session_id: uuid.UUID | None = None,
    context: RequestContext | None = None,
) -> None:
    """Add an audit entry to the current transaction (the caller commits)."""
    db.add(
        AuditLog(
            action=action,
            actor_user_id=actor.id if actor else None,
            actor_email=actor.email if actor else actor_email,
            object_type=object_type,
            object_id=object_id,
            previous_state=previous_state,
            new_state=new_state,
            note=note,
            session_id=session_id,
            ip_address=context.ip_address if context else None,
            user_agent=context.user_agent if context else None,
        )
    )
