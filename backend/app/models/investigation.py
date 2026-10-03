"""Investigations, their teams, and the per-year case-number counter (plan §10)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import User

INVESTIGATION_STATUSES = ("draft", "active", "under_review", "suspended", "closed", "archived")
PRIORITIES = ("low", "medium", "high", "critical")
WORKFLOW_STAGES = (
    "intake",
    "processing",
    "extraction",
    "correlation",
    "review",
    "reporting",
    "closed",
)
MEMBER_ROLES = ("lead", "member")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Investigation(Base):
    __tablename__ = "investigations"
    __table_args__ = (
        CheckConstraint(_in("status", INVESTIGATION_STATUSES), name="valid_status"),
        CheckConstraint(_in("priority", PRIORITIES), name="valid_priority"),
        CheckConstraint(_in("stage", WORKFLOW_STAGES), name="valid_stage"),
        # Fast "contains"/fuzzy title search (pg_trgm). Declared here so Alembic keeps it.
        Index(
            "ix_investigations_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    # Human-readable case number, e.g. CASE-2026-001. Used in URLs and conversation.
    reference: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    case_type: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    priority: Mapped[str] = mapped_column(String(10), default="medium", index=True)
    stage: Mapped[str] = mapped_column(String(20), default="intake")
    location: Mapped[str] = mapped_column(String(200), default="")
    # IANA time zone of the place under investigation (e.g. "Asia/Kolkata"). Times are stored
    # in UTC; this zone is used to show them, and to read times that were written without one.
    time_zone: Mapped[str] = mapped_column(String(64), default="UTC", server_default="UTC")
    # Set when facts changed and correlation should run again; the worker picks it up.
    correlation_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)

    lead_investigator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )

    lead_investigator: Mapped[User] = relationship(foreign_keys=[lead_investigator_id])
    members: Mapped[list["InvestigationMember"]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan"
    )


class InvestigationMember(Base):
    """Who works on a case. Data isolation: only members (and supervisors) can see it."""

    __tablename__ = "investigation_members"
    __table_args__ = (
        UniqueConstraint("investigation_id", "user_id", name="one_membership"),
        CheckConstraint(_in("role_in_case", MEMBER_ROLES), name="valid_role_in_case"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    role_in_case: Mapped[str] = mapped_column(String(10), default="member")
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    investigation: Mapped[Investigation] = relationship(back_populates="members")
    user: Mapped[User] = relationship()


class ReferenceCounter(Base):
    """Last case number used per year. Incremented atomically → no duplicate numbers."""

    __tablename__ = "investigation_reference_counters"

    year: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    last_value: Mapped[int] = mapped_column(Integer, default=0)
