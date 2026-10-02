"""Structured information extracted from evidence (plan §14–§16).

    Evidence ──mentions──► Entity      (P001 person, PH001 phone, V001 vehicle, …)
    Evidence ──generates─► Event       (E001 call made at 20:33, …)
    Entity   ──participates in──► Event (as caller, callee, device, vehicle, …)

Every mention and every event records WHERE it came from (evidence + exact spot in the file),
HOW (assertion kind + extractor) and HOW SURE (confidence), and starts as "pending" review.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.evidence import Evidence
from app.models.investigation import Investigation, _in

ENTITY_TYPES = (
    "person",
    "phone_number",
    "device",
    "vehicle",
    "account",
    "location",
    "organization",
    "digital_artifact",
)
EVENT_TYPES = (
    "call_made",
    "message_sent",
    "transaction_completed",
    "location_recorded",
    "vehicle_detected",
    "person_detected",
    "device_detected",
    "person_entered_location",
    "photo_taken",
    "video_recorded",
    "document_created",
    "communication",
    "digital_artifact_created",
    "other",
)
ASSERTION_KINDS = ("fact", "extracted", "detected", "correlated", "inferred", "user_entered")
REVIEW_STATUSES = ("pending", "confirmed", "rejected")


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint("investigation_id", "reference", name="entity_reference_per_case"),
        # One entity per real-world identifier per case: the same phone number in two files
        # becomes ONE entity with two mentions (that is how evidence gets connected).
        UniqueConstraint(
            "investigation_id", "entity_type", "normalized_key", name="one_per_identifier"
        ),
        CheckConstraint(_in("entity_type", ENTITY_TYPES), name="valid_type"),
        CheckConstraint(_in("review_status", REVIEW_STATUSES), name="valid_review_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), index=True
    )
    reference: Mapped[str] = mapped_column(String(12))  # P001, PH001, V001 …
    entity_type: Mapped[str] = mapped_column(String(30))
    label: Mapped[str] = mapped_column(String(200))  # how it is shown: "+1 202-555-0101"
    normalized_key: Mapped[str] = mapped_column(String(200))  # how it is matched: "+12025550101"
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    review_status: Mapped[str] = mapped_column(String(12), default="pending")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id")
    )  # None = automatic
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    investigation: Mapped[Investigation] = relationship()
    mentions: Mapped[list["EntityMention"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )
    participations: Mapped[list["EventParticipant"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )


class EntityMention(Base):
    """One place where an entity appears in one evidence item."""

    __tablename__ = "entity_mentions"
    __table_args__ = (
        CheckConstraint(_in("assertion_kind", ASSERTION_KINDS), name="valid_assertion"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="valid_confidence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), index=True
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), index=True
    )
    assertion_kind: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[float] = mapped_column(Float)
    extractor: Mapped[str] = mapped_column(
        String(60)
    )  # e.g. "csv:call_records", "spacy:en_core_web_sm"
    source_location: Mapped[str] = mapped_column(String(120), default="")  # "row 3, column caller"
    context: Mapped[str] = mapped_column(Text, default="")  # the surrounding text, for humans
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    entity: Mapped[Entity] = relationship(back_populates="mentions")
    evidence: Mapped[Evidence] = relationship()


class Event(Base):
    """Something that happened, at a time (and maybe a place), supported by one evidence item."""

    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("investigation_id", "reference", name="event_reference_per_case"),
        CheckConstraint(_in("event_type", EVENT_TYPES), name="valid_type"),
        CheckConstraint(_in("assertion_kind", ASSERTION_KINDS), name="valid_assertion"),
        CheckConstraint(_in("review_status", REVIEW_STATUSES), name="valid_review_status"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="valid_confidence"),
        Index("ix_events_case_time", "investigation_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), index=True
    )
    reference: Mapped[str] = mapped_column(String(12))  # E001 …
    event_type: Mapped[str] = mapped_column(String(40))
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    location_text: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), index=True
    )
    assertion_kind: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[float] = mapped_column(Float)
    extractor: Mapped[str] = mapped_column(String(60))
    source_location: Mapped[str] = mapped_column(String(120), default="")
    review_status: Mapped[str] = mapped_column(String(12), default="pending")
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    evidence: Mapped[Evidence] = relationship()
    investigation: Mapped[Investigation] = relationship()
    participants: Mapped[list["EventParticipant"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class EventParticipant(Base):
    __tablename__ = "event_participants"

    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    role: Mapped[str] = mapped_column(String(30), primary_key=True)  # caller, callee, device …

    event: Mapped[Event] = relationship(back_populates="participants")
    entity: Mapped[Entity] = relationship(back_populates="participations")
