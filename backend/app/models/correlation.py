"""Correlations: potential relationships between two evidence items (plan §18–§19).

A correlation is NOT a conclusion. It says: "these two pieces of evidence share an entity,
and/or happened close together in time and place — here is exactly why, and how strongly."
An analyst confirms or rejects it.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.evidence import Evidence
from app.models.investigation import _in
from app.models.user import User

LEVELS = ("high", "medium", "low")
REVIEW_STATUSES = ("pending", "confirmed", "rejected")


class Correlation(Base):
    __tablename__ = "correlations"
    __table_args__ = (
        UniqueConstraint("investigation_id", "reference", name="correlation_reference_per_case"),
        # One correlation per pair of evidence items (stored with evidence_a < evidence_b).
        UniqueConstraint("investigation_id", "evidence_a_id", "evidence_b_id", name="one_per_pair"),
        CheckConstraint("evidence_a_id <> evidence_b_id", name="two_different_items"),
        CheckConstraint(_in("level", LEVELS), name="valid_level"),
        CheckConstraint(_in("review_status", REVIEW_STATUSES), name="valid_review_status"),
        CheckConstraint("score BETWEEN 0 AND 1", name="valid_score"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), index=True
    )
    reference: Mapped[str] = mapped_column(String(12))  # COR-001
    evidence_a_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), index=True
    )
    evidence_b_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), index=True
    )
    score: Mapped[float] = mapped_column(Float)
    level: Mapped[str] = mapped_column(String(10))
    # Every factor with its score, weight, contribution and a plain-language explanation.
    factors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    algorithm: Mapped[str] = mapped_column(String(30))  # version, e.g. "falcon-correlation-v1"
    # True when the latest run no longer finds this relationship (kept because a person reviewed it)
    stale: Mapped[bool] = mapped_column(Boolean, default=False)

    review_status: Mapped[str] = mapped_column(String(12), default="pending")
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    evidence_a: Mapped[Evidence] = relationship(foreign_keys=[evidence_a_id])
    evidence_b: Mapped[Evidence] = relationship(foreign_keys=[evidence_b_id])
    reviewed_by: Mapped[User | None] = relationship()
