"""Evidence items and their processing jobs (plan §11, §13, §27).

Integrity principle: the ORIGINAL file is stored once, fingerprinted with SHA-256, made
read-only and never modified. Processing only ever reads it or writes separate derived files.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.investigation import Investigation, _in
from app.models.user import User

EVIDENCE_TYPES = (
    "video",
    "image",
    "document",
    "gps",
    "mobile",
    "call_records",
    "financial",
    "vehicle",
    "witness_statement",
    "digital_file",
    "other",
)
EVIDENCE_STATUSES = (
    "uploaded",
    "processing",
    "processed",
    "verified",
    "requires_review",
    "archived",
)
JOB_STATUSES = ("queued", "running", "succeeded", "failed")


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        UniqueConstraint("investigation_id", "reference", name="reference_per_case"),
        # The same file (same fingerprint) can be stored only once per case.
        UniqueConstraint("investigation_id", "sha256", name="one_copy_per_case"),
        CheckConstraint(_in("evidence_type", EVIDENCE_TYPES), name="valid_type"),
        CheckConstraint(_in("status", EVIDENCE_STATUSES), name="valid_status"),
        CheckConstraint("size_bytes >= 0", name="non_negative_size"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256_hex"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="RESTRICT"), index=True
    )
    reference: Mapped[str] = mapped_column(String(20))  # e.g. IMG-001, unique within a case
    evidence_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="uploaded", index=True)

    # Describing the evidence (entered by the uploader)
    source: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    location_text: Mapped[str] = mapped_column(String(200), default="")
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)

    # The file and its fingerprint (integrity, plan §27)
    original_filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(120))  # detected from content, not the name
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(300), unique=True)
    integrity_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    integrity_ok: Mapped[bool | None] = mapped_column()

    # Results of processing: technical metadata, extracted values, derived files
    file_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    preview_key: Mapped[str | None] = mapped_column(String(300))

    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    investigation: Mapped[Investigation] = relationship()
    uploaded_by: Mapped[User] = relationship()
    jobs: Mapped[list["ProcessingJob"]] = relationship(
        back_populates="evidence", order_by="ProcessingJob.created_at"
    )


class ProcessingJob(Base):
    """One run of the processing pipeline for one evidence item. This table IS the job queue."""

    __tablename__ = "processing_jobs"
    __table_args__ = (
        CheckConstraint(_in("status", JOB_STATUSES), name="valid_status"),
        CheckConstraint("progress BETWEEN 0 AND 100", name="valid_progress"),
        # The worker asks "oldest queued job?" constantly; this small index answers instantly.
        Index(
            "ix_processing_jobs_queue",
            "created_at",
            postgresql_where=text("status = 'queued'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    current_step: Mapped[str | None] = mapped_column(String(80))
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)  # per-step results
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    worker_id: Mapped[str | None] = mapped_column(String(80))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    evidence: Mapped[Evidence] = relationship(back_populates="jobs")


class EvidenceReferenceCounter(Base):
    """Last number used per case and prefix: CASE-2026-001 + "IMG" → IMG-001, IMG-002 …"""

    __tablename__ = "evidence_reference_counters"

    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), primary_key=True
    )
    prefix: Mapped[str] = mapped_column(String(8), primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, default=0)
