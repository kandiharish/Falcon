"""Investigation work: tasks for the team (plan §30) and notifications for people (plan §29)."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.evidence import Evidence
from app.models.investigation import PRIORITIES, Investigation, _in
from app.models.user import User

TASK_STATUSES = ("todo", "in_progress", "review", "completed")
NOTIFICATION_KINDS = (
    "processing_completed",
    "processing_failed",
    "requires_review",
    "correlation_detected",
    "task_assigned",
    "investigation_assigned",
    "report_ready",
)

# Which evidence a task is about (many-to-many: a task can cover several items).
task_evidence = Table(
    "task_evidence",
    Base.metadata,
    Column("task_id", ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("evidence_id", ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True),
)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("investigation_id", "reference", name="task_reference_per_case"),
        CheckConstraint(_in("status", TASK_STATUSES), name="valid_status"),
        CheckConstraint(_in("priority", PRIORITIES), name="valid_priority"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), index=True
    )
    reference: Mapped[str] = mapped_column(String(12))  # T-001
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(12), default="todo")
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    due_date: Mapped[date | None] = mapped_column(Date)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    investigation: Mapped[Investigation] = relationship()
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id])
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])
    evidence: Mapped[list[Evidence]] = relationship(
        secondary=task_evidence, order_by=Evidence.reference
    )


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(_in("kind", NOTIFICATION_KINDS), name="valid_kind"),
        # The bell asks "my unread, newest first" every 30 s: one index answers it.
        Index("ix_notifications_user_unread", "user_id", "read_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str] = mapped_column(
        String(300), default=""
    )  # a page in FALCON, e.g. /investigations/…
    investigation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
