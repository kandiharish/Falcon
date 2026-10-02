"""Investigation reports (plan §24): a frozen snapshot of the case at one moment.

A report is never recalculated after it is generated: what was shared stays exactly what it
was. The content is stored as JSON together with its SHA-256 fingerprint, so anyone can
check later that the report was not altered (the same idea as evidence integrity).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.investigation import Investigation, _in
from app.models.user import User

REPORT_STATUSES = ("generating", "ready", "failed")


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("investigation_id", "reference", name="report_reference_per_case"),
        CheckConstraint(_in("status", REPORT_STATUSES), name="valid_status"),
        CheckConstraint(
            "content_sha256 IS NULL OR content_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_hex"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), index=True
    )
    reference: Mapped[str] = mapped_column(String(12))  # RPT-001
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(12), default="generating")
    content: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    content_sha256: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    generated_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    investigation: Mapped[Investigation] = relationship()
    generated_by: Mapped[User] = relationship()
