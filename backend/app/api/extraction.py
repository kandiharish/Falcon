"""/api/investigations/{case}/entities and /events — structured information (plan §14–§16)."""

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Entity, EntityMention, Event, User
from app.security.dependencies import require_permission
from app.security.permissions import Permission
from app.services import extraction_service as service
from app.services.request_context import request_context

router = APIRouter(prefix="/investigations/{case_reference}", tags=["entities & events"])

EntityType = Literal[
    "person",
    "phone_number",
    "device",
    "vehicle",
    "account",
    "location",
    "organization",
    "digital_artifact",
]
EventType = Literal[
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
]
AssertionKind = Literal["fact", "extracted", "detected", "correlated", "inferred", "user_entered"]
ReviewStatus = Literal["pending", "confirmed", "rejected"]

Reader = Annotated[User, Depends(require_permission(Permission.EVIDENCE_READ))]
Contributor = Annotated[User, Depends(require_permission(Permission.EVIDENCE_UPLOAD))]
Reviewer = Annotated[User, Depends(require_permission(Permission.EVIDENCE_VERIFY))]
DB = Annotated[Session, Depends(get_db)]


# ---------- Shapes ----------------------------------------------------------------------


class EntityRef(BaseModel):
    reference: str
    entity_type: EntityType
    label: str


class Participant(EntityRef):
    role: str


class EventOut(BaseModel):
    reference: str
    event_type: EventType
    occurred_at: datetime | None
    ended_at: datetime | None
    latitude: float | None
    longitude: float | None
    location_text: str
    description: str
    evidence_reference: str
    evidence_type: str
    assertion_kind: AssertionKind
    confidence: float
    extractor: str
    source_location: str
    review_status: ReviewStatus
    attributes: dict[str, Any]
    participants: list[Participant]
    added_manually: bool


class EntitySummary(EntityRef):
    review_status: ReviewStatus
    mention_count: int
    evidence_count: int
    event_count: int
    max_confidence: float | None
    assertion_kinds: list[AssertionKind]
    attributes: dict[str, Any]
    added_manually: bool


class MentionOut(BaseModel):
    evidence_reference: str
    evidence_type: str
    evidence_description: str
    assertion_kind: AssertionKind
    confidence: float
    extractor: str
    source_location: str
    context: str
    created_at: datetime


class EntityDetail(EntitySummary):
    mentions: list[MentionOut]
    events: list[EventOut]


class EntityPage(BaseModel):
    items: list[EntitySummary]
    total: int


class EventPage(BaseModel):
    items: list[EventOut]
    total: int


class EntityMentionOut(BaseModel):
    entity: EntityRef
    assertion_kind: AssertionKind
    confidence: float
    extractor: str
    source_location: str
    context: str


class ExtractedInformation(BaseModel):
    evidence_reference: str
    mentions: list[EntityMentionOut]
    events: list[EventOut]


class Review(BaseModel):
    review_status: ReviewStatus
    note: str | None = Field(default=None, max_length=1000)


class EntityCreate(BaseModel):
    entity_type: EntityType
    value: str = Field(min_length=1, max_length=200)
    evidence_reference: str = Field(min_length=3, max_length=20)
    note: str = Field(default="", max_length=1000)


class ParticipantIn(BaseModel):
    entity_reference: str = Field(min_length=2, max_length=12)
    role: str = Field(default="involved", max_length=30)


class EventCreate(BaseModel):
    evidence_reference: str = Field(min_length=3, max_length=20)
    event_type: EventType
    occurred_at: datetime | None = None
    description: str = Field(min_length=3, max_length=2000)
    participants: list[ParticipantIn] = Field(default_factory=list, max_length=20)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_text: str = Field(default="", max_length=200)


def _ref(entity: Entity) -> dict[str, Any]:
    return {"reference": entity.reference, "entity_type": entity.entity_type, "label": entity.label}


def event_out(e: Event) -> EventOut:
    return EventOut(
        reference=e.reference,
        event_type=e.event_type,  # type: ignore[arg-type]
        occurred_at=e.occurred_at,
        ended_at=e.ended_at,
        latitude=e.latitude,
        longitude=e.longitude,
        location_text=e.location_text,
        description=e.description,
        evidence_reference=e.evidence.reference,
        evidence_type=e.evidence.evidence_type,
        assertion_kind=e.assertion_kind,  # type: ignore[arg-type]
        confidence=e.confidence,
        extractor=e.extractor,
        source_location=e.source_location,
        review_status=e.review_status,  # type: ignore[arg-type]
        attributes=e.attributes or {},
        participants=[Participant(**_ref(p.entity), role=p.role) for p in e.participants],
        added_manually=e.created_by_id is not None,
    )


def _summary(entity: Entity, stats: service.EntityStats) -> dict[str, Any]:
    return {
        **_ref(entity),
        "review_status": entity.review_status,
        "mention_count": stats.mention_count,
        "evidence_count": stats.evidence_count,
        "event_count": stats.event_count,
        "max_confidence": stats.max_confidence,
        "assertion_kinds": stats.assertion_kinds,
        "attributes": entity.attributes or {},
        "added_manually": entity.created_by_id is not None,
    }


def _mention(m: EntityMention) -> MentionOut:
    return MentionOut(
        evidence_reference=m.evidence.reference,
        evidence_type=m.evidence.evidence_type,
        evidence_description=m.evidence.description or m.evidence.original_filename,
        assertion_kind=m.assertion_kind,  # type: ignore[arg-type]
        confidence=m.confidence,
        extractor=m.extractor,
        source_location=m.source_location,
        context=m.context,
        created_at=m.created_at,
    )


def _entity_detail(db: Session, entity: Entity, stats: service.EntityStats) -> EntityDetail:
    mentions = sorted(entity.mentions, key=lambda m: (m.evidence.reference, m.source_location))
    return EntityDetail(
        **_summary(entity, stats),
        mentions=[_mention(m) for m in mentions],
        events=[event_out(e) for e in service.events_for_entity(db, entity)],
    )


# ---------- Entities --------------------------------------------------------------------


@router.get("/entities", response_model=EntityPage)
def list_entities(
    case_reference: str,
    user: Reader,
    db: DB,
    entity_type: EntityType | None = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
    review_status: ReviewStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EntityPage:
    filters = service.EntityFilters(entity_type, search or None, review_status)
    rows, total = service.list_entities(db, user, case_reference, filters, limit, offset)
    return EntityPage(items=[EntitySummary(**_summary(e, s)) for e, s in rows], total=total)


@router.post("/entities", response_model=EntityDetail, status_code=status.HTTP_201_CREATED)
def create_entity(
    case_reference: str, body: EntityCreate, request: Request, user: Contributor, db: DB
) -> EntityDetail:
    entity = service.create_entity(
        db,
        user,
        case_reference,
        body.entity_type,
        body.value,
        body.evidence_reference,
        body.note,
        request_context(request),
    )
    entity, stats = service.get_entity(db, user, case_reference, entity.reference)
    return _entity_detail(db, entity, stats)


@router.get("/entities/{reference}", response_model=EntityDetail)
def get_entity(case_reference: str, reference: str, user: Reader, db: DB) -> EntityDetail:
    entity, stats = service.get_entity(db, user, case_reference, reference)
    return _entity_detail(db, entity, stats)


@router.post("/entities/{reference}/review", response_model=EntityDetail)
def review_entity(
    case_reference: str, reference: str, body: Review, request: Request, user: Reviewer, db: DB
) -> EntityDetail:
    service.review_entity(
        db, user, case_reference, reference, body.review_status, body.note, request_context(request)
    )
    entity, stats = service.get_entity(db, user, case_reference, reference)
    return _entity_detail(db, entity, stats)


# ---------- Events ----------------------------------------------------------------------


@router.get("/events", response_model=EventPage)
def list_events(
    case_reference: str,
    user: Reader,
    db: DB,
    event_type: EventType | None = None,
    entity: Annotated[str | None, Query(max_length=12)] = None,
    evidence: Annotated[str | None, Query(max_length=20)] = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    review_status: ReviewStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EventPage:
    filters = service.EventFilters(
        event_type, entity, evidence, occurred_from, occurred_to, review_status
    )
    events, total = service.list_events(db, user, case_reference, filters, limit, offset)
    return EventPage(items=[event_out(e) for e in events], total=total)


@router.post("/events", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_event(
    case_reference: str, body: EventCreate, request: Request, user: Contributor, db: DB
) -> EventOut:
    data = service.NewEvent(
        evidence_reference=body.evidence_reference,
        event_type=body.event_type,
        occurred_at=body.occurred_at,
        description=body.description,
        participants=[(p.entity_reference, p.role) for p in body.participants],
        latitude=body.latitude,
        longitude=body.longitude,
        location_text=body.location_text,
    )
    return event_out(service.create_event(db, user, case_reference, data, request_context(request)))


@router.get("/events/{reference}", response_model=EventOut)
def get_event(case_reference: str, reference: str, user: Reader, db: DB) -> EventOut:
    return event_out(service.get_event(db, user, case_reference, reference))


@router.post("/events/{reference}/review", response_model=EventOut)
def review_event(
    case_reference: str, reference: str, body: Review, request: Request, user: Reviewer, db: DB
) -> EventOut:
    return event_out(
        service.review_event(
            db,
            user,
            case_reference,
            reference,
            body.review_status,
            body.note,
            request_context(request),
        )
    )


# ---------- Per evidence ----------------------------------------------------------------


@router.get("/evidence/{evidence_reference}/extracted", response_model=ExtractedInformation)
def extracted_information(
    case_reference: str, evidence_reference: str, user: Reader, db: DB
) -> ExtractedInformation:
    evidence, mentions, events = service.extracted_from_evidence(
        db, user, case_reference, evidence_reference
    )
    return ExtractedInformation(
        evidence_reference=evidence.reference,
        mentions=[
            EntityMentionOut(
                entity=EntityRef(**_ref(m.entity)),
                assertion_kind=m.assertion_kind,  # type: ignore[arg-type]
                confidence=m.confidence,
                extractor=m.extractor,
                source_location=m.source_location,
                context=m.context,
            )
            for m in mentions
        ],
        events=[event_out(e) for e in events],
    )
