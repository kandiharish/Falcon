"""Append-only audit trail (plan §25). A database trigger blocks UPDATE and DELETE."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Identity, String, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    # Who (kept as text too, so the record stays readable if the user is ever removed)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID, index=True)
    actor_email: Mapped[str | None] = mapped_column(String(320))
    # What
    action: Mapped[str] = mapped_column(String(80), index=True)  # e.g. "auth.login_succeeded"
    object_type: Mapped[str | None] = mapped_column(String(60))
    object_id: Mapped[str | None] = mapped_column(String(120))
    previous_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    new_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    note: Mapped[str | None] = mapped_column(Text)
    # Session information
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID)
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(String(400))
