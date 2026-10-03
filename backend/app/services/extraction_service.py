"""Entities and events: browse, open, review, and add by hand (plan §14–§16).

Rules:
  • Seeing them needs evidence:read and access to the case.
  • Reviewing (confirm / reject) needs evidence:verify and team membership — a human decides.
  • Analysts may add entities/events by hand (e.g. "person seen at rear door at 20:30" while
    watching CCTV). Those are USER ENTERED, must point to supporting evidence, and are never
    removed by automatic re-processing.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.extraction.normalize import normalize
from app.extraction.sink import ENTITY_PREFIX
from app.models import (
    Entity,
    EntityMention,
    Event,
    EventParticipant,
    Evidence,
    Investigation,
    User,
)
from app.repositories import reference_counters
from app.security.permissions import Permission, Role, permissions_for
from app.services import audit_service, correlation_service, evidence_service, investigation_service
from app.services.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError
from app.services.request_context import RequestContext


@dataclass(frozen=True)
class EntityStats:
    mention_count: int
    evidence_count: int
    event_count: int
    max_confidence: float | None
    assertion_kinds: list[str]


@dataclass(frozen=True)
class EntityFilters:
    entity_type: str | None = None
    search: str | None = None
    review_status: str | None = None


@dataclass(frozen=True)
class EventFilters:
    event_type: str | None = None
    entity_reference: str | None = None
    evidence_reference: str | None = None
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None
    review_status: str | None = None
    event_types: tuple[str, ...] = ()
    evidence_type: str | None = None
    has_location: bool | None = None
    near: tuple[float, float, float] | None = None  # (latitude, longitude, radius in metres)


@dataclass
class NewEvent:
    evidence_reference: str
    event_type: str
    occurred_at: datetime | None
    description: str
    participants: list[tuple[str, str]] = field(default_factory=list)  # (entity ref, role)
    latitude: float | None = None
    longitude: float | None = None
    location_text: str = ""


def audit_id(case: Investigation, reference: str) -> str:
    return f"{case.reference}/{reference}"


# ---------- Entities ----------------------------------------------------------------------


def list_entities(
    db: Session, user: User, case_reference: str, filters: EntityFilters, limit: int, offset: int
) -> tuple[list[tuple[Entity, EntityStats]], int]:
    case = investigation_service.get_investigation(db, user, case_reference)
    query = select(Entity).where(Entity.investigation_id == case.id)
    if filters.entity_type:
        query = query.where(Entity.entity_type == filters.entity_type)
    if filters.review_status:
        query = query.where(Entity.review_status == filters.review_status)
    if filters.search:
        term = f"%{filters.search.strip()}%"
        query = query.where(
            or_(
                Entity.label.ilike(term),
                Entity.reference.ilike(term),
                Entity.normalized_key.ilike(term),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    entities = list(
        db.scalars(query.order_by(Entity.entity_type, Entity.reference).limit(limit).offset(offset))
    )
    stats = _entity_stats(db, [e.id for e in entities])
    return [(e, stats[e.id]) for e in entities], total


def _entity_stats(db: Session, entity_ids: list[uuid.UUID]) -> dict[uuid.UUID, EntityStats]:
    if not entity_ids:
        return {}
    mention_rows = db.execute(
        select(
            EntityMention.entity_id,
            func.count(),
            func.count(func.distinct(EntityMention.evidence_id)),
            func.max(EntityMention.confidence),
            func.array_agg(func.distinct(EntityMention.assertion_kind)),
        )
        .where(EntityMention.entity_id.in_(entity_ids))
        .group_by(EntityMention.entity_id)
    ).all()
    event_rows = db.execute(
        select(EventParticipant.entity_id, func.count(func.distinct(EventParticipant.event_id)))
        .where(EventParticipant.entity_id.in_(entity_ids))
        .group_by(EventParticipant.entity_id)
    ).all()
    mentions = {row[0]: row[1:] for row in mention_rows}
    events = dict(event_rows)
    result = {}
    for entity_id in entity_ids:
        count, evidence_count, confidence, kinds = mentions.get(entity_id, (0, 0, None, []))
        result[entity_id] = EntityStats(
            mention_count=count,
            evidence_count=evidence_count,
            event_count=events.get(entity_id, 0),
            max_confidence=confidence,
            assertion_kinds=sorted(k for k in kinds if k),
        )
    return result


def get_entity(
    db: Session, user: User, case_reference: str, reference: str
) -> tuple[Entity, EntityStats]:
    case = investigation_service.get_investigation(db, user, case_reference)
    entity = db.scalar(
        select(Entity)
        .where(Entity.investigation_id == case.id, Entity.reference == reference.upper())
        .options(selectinload(Entity.mentions).selectinload(EntityMention.evidence))
        .execution_options(populate_existing=True)
    )
    if entity is None:
        raise NotFoundError("This entity does not exist in this investigation.")
    return entity, _entity_stats(db, [entity.id])[entity.id]


def create_entity(
    db: Session,
    user: User,
    case_reference: str,
    entity_type: str,
    value: str,
    evidence_reference: str,
    note: str,
    context: RequestContext,
) -> Entity:
    case = _require_contributor(db, user, case_reference)
    evidence = evidence_service.get_evidence(db, user, case_reference, evidence_reference)
    normalized = normalize(entity_type, value)
    if normalized is None:
        raise InvalidInputError("This value is not a valid identifier for that entity type.")
    entity = db.scalar(
        select(Entity).where(
            Entity.investigation_id == case.id,
            Entity.entity_type == entity_type,
            Entity.normalized_key == normalized.key,
        )
    )
    if entity is None:
        prefix = ENTITY_PREFIX[entity_type]
        number = reference_counters.next_value(db, case.id, prefix)
        entity = Entity(
            investigation_id=case.id,
            reference=f"{prefix}{number:03d}",
            entity_type=entity_type,
            label=normalized.label,
            normalized_key=normalized.key,
            created_by_id=user.id,
            attributes={},
        )
        db.add(entity)
        db.flush()
    db.add(
        EntityMention(
            entity_id=entity.id,
            evidence_id=evidence.id,
            assertion_kind="user_entered",
            confidence=1.0,
            extractor="analyst",
            source_location="added by analyst",
            context=note,
            created_by_id=user.id,
        )
    )
    audit_service.record(
        db,
        "entity.added_manually",
        actor=user,
        object_type="entity",
        object_id=audit_id(case, entity.reference),
        new_state={
            "entity_type": entity_type,
            "label": entity.label,
            "evidence": evidence.reference,
        },
        note=note or None,
        context=context,
    )
    db.commit()
    correlation_service.request_refresh(db, case.id)  # the worker re-correlates
    return entity


def review_entity(
    db: Session,
    user: User,
    case_reference: str,
    reference: str,
    status: str,
    note: str | None,
    context: RequestContext,
) -> Entity:
    case = _require_reviewer(db, user, case_reference)
    entity, _ = get_entity(db, user, case_reference, reference)
    previous = entity.review_status
    entity.review_status = status
    audit_service.record(
        db,
        "entity.reviewed",
        actor=user,
        object_type="entity",
        object_id=audit_id(case, entity.reference),
        previous_state={"review_status": previous},
        new_state={"review_status": status},
        note=note,
        context=context,
    )
    db.commit()
    correlation_service.request_refresh(db, case.id)  # the worker re-correlates
    return entity


# ---------- Events ------------------------------------------------------------------------


def _event_query(case_id: uuid.UUID) -> Select[tuple[Event]]:
    return (
        select(Event)
        .where(Event.investigation_id == case_id)
        .options(
            selectinload(Event.participants).selectinload(EventParticipant.entity),
            selectinload(Event.evidence),
        )
    )


def list_events(
    db: Session, user: User, case_reference: str, filters: EventFilters, limit: int, offset: int
) -> tuple[list[Event], int]:
    case = investigation_service.get_investigation(db, user, case_reference)
    query = _event_query(case.id)
    if filters.event_type:
        query = query.where(Event.event_type == filters.event_type)
    if filters.review_status:
        query = query.where(Event.review_status == filters.review_status)
    if filters.occurred_from:
        query = query.where(Event.occurred_at >= filters.occurred_from)
    if filters.occurred_to:
        query = query.where(Event.occurred_at <= filters.occurred_to)
    if filters.evidence_reference:
        query = query.where(Event.evidence.has(reference=filters.evidence_reference.upper()))
    if filters.entity_reference:
        query = query.where(
            Event.participants.any(
                EventParticipant.entity.has(reference=filters.entity_reference.upper())
            )
        )
    if filters.event_types:
        query = query.where(Event.event_type.in_(filters.event_types))
    if filters.evidence_type:
        query = query.where(Event.evidence.has(evidence_type=filters.evidence_type))
    if filters.has_location is not None:
        located = Event.latitude.is_not(None) & Event.longitude.is_not(None)
        query = query.where(located if filters.has_location else ~located)
    if filters.near:
        query = query.where(_within_metres(*filters.near))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    events = db.scalars(
        query.order_by(Event.occurred_at.asc().nulls_last(), Event.reference)
        .limit(limit)
        .offset(offset)
    ).all()
    return list(events), total


def _point(latitude: Any, longitude: Any) -> Any:
    """A PostGIS geography point (WGS 84, the system GPS uses). Note: longitude comes first."""
    return func.geography(func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326))


def _within_metres(latitude: float, longitude: float, radius_m: float) -> Any:
    """PostGIS measures the real distance on the Earth's surface, in metres."""
    return func.ST_DWithin(
        _point(Event.latitude, Event.longitude), _point(latitude, longitude), radius_m
    )


def get_event(db: Session, user: User, case_reference: str, reference: str) -> Event:
    case = investigation_service.get_investigation(db, user, case_reference)
    event = db.scalar(
        _event_query(case.id)
        .where(Event.reference == reference.upper())
        .execution_options(populate_existing=True)
    )
    if event is None:
        raise NotFoundError("This event does not exist in this investigation.")
    return event


def events_for_entity(db: Session, entity: Entity) -> list[Event]:
    return list(
        db.scalars(
            _event_query(entity.investigation_id)
            .where(Event.participants.any(EventParticipant.entity_id == entity.id))
            .order_by(Event.occurred_at.asc().nulls_last())
        )
    )


def create_event(
    db: Session, user: User, case_reference: str, data: NewEvent, context: RequestContext
) -> Event:
    case = _require_contributor(db, user, case_reference)
    evidence = evidence_service.get_evidence(db, user, case_reference, data.evidence_reference)
    if (data.latitude is None) != (data.longitude is None):
        raise InvalidInputError("Enter both latitude and longitude, or neither.")
    number = reference_counters.next_value(db, case.id, "E")
    event = Event(
        investigation_id=case.id,
        reference=f"E{number:03d}",
        event_type=data.event_type,
        occurred_at=data.occurred_at,
        latitude=data.latitude,
        longitude=data.longitude,
        location_text=data.location_text.strip(),
        description=data.description.strip(),
        evidence_id=evidence.id,
        assertion_kind="user_entered",
        confidence=1.0,
        extractor="analyst",
        source_location="added by analyst",
        created_by_id=user.id,
        attributes={},
    )
    for entity_reference, role in data.participants:
        entity = db.scalar(
            select(Entity).where(
                Entity.investigation_id == case.id, Entity.reference == entity_reference.upper()
            )
        )
        if entity is None:
            raise InvalidInputError(
                f"Entity {entity_reference} does not exist in this investigation."
            )
        event.participants.append(EventParticipant(entity_id=entity.id, role=role or "involved"))
    db.add(event)
    db.flush()
    audit_service.record(
        db,
        "event.added_manually",
        actor=user,
        object_type="event",
        object_id=audit_id(case, event.reference),
        new_state={
            "event_type": data.event_type,
            "evidence": evidence.reference,
            "occurred_at": data.occurred_at.isoformat() if data.occurred_at else None,
        },
        context=context,
    )
    db.commit()
    correlation_service.request_refresh(db, case.id)  # the worker re-correlates
    return get_event(db, user, case_reference, event.reference)


def review_event(
    db: Session,
    user: User,
    case_reference: str,
    reference: str,
    status: str,
    note: str | None,
    context: RequestContext,
) -> Event:
    case = _require_reviewer(db, user, case_reference)
    event = get_event(db, user, case_reference, reference)
    previous = event.review_status
    event.review_status = status
    audit_service.record(
        db,
        "event.reviewed",
        actor=user,
        object_type="event",
        object_id=audit_id(case, event.reference),
        previous_state={"review_status": previous},
        new_state={"review_status": status},
        note=note,
        context=context,
    )
    db.commit()
    correlation_service.request_refresh(db, case.id)  # the worker re-correlates
    return get_event(db, user, case_reference, reference)


# ---------- Per evidence & per case -------------------------------------------------------


def extracted_from_evidence(
    db: Session, user: User, case_reference: str, evidence_reference: str
) -> tuple[Evidence, list[EntityMention], list[Event]]:
    evidence = evidence_service.get_evidence(db, user, case_reference, evidence_reference)
    mentions = list(
        db.scalars(
            select(EntityMention)
            .where(EntityMention.evidence_id == evidence.id)
            .options(selectinload(EntityMention.entity))
            .order_by(EntityMention.created_at)
        )
    )
    events = list(
        db.scalars(
            _event_query(evidence.investigation_id)
            .where(Event.evidence_id == evidence.id)
            .order_by(Event.occurred_at.asc().nulls_last())
        )
    )
    return evidence, mentions, events


def counts_by_investigation(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, Any]]:
    if not ids:
        return {}
    entity_counts = dict(
        db.execute(
            select(Entity.investigation_id, func.count())
            .where(Entity.investigation_id.in_(ids))
            .group_by(Entity.investigation_id)
        ).all()
    )
    event_counts = dict(
        db.execute(
            select(Event.investigation_id, func.count())
            .where(Event.investigation_id.in_(ids))
            .group_by(Event.investigation_id)
        ).all()
    )
    return {i: {"entities": entity_counts.get(i, 0), "events": event_counts.get(i, 0)} for i in ids}


# ---------- Permissions -------------------------------------------------------------------


def _on_team(db: Session, user: User, case: Investigation) -> bool:
    return user.role == Role.SUPERVISOR or (
        investigation_service.repo.membership(db, case.id, user.id) is not None
    )


def _require_contributor(db: Session, user: User, case_reference: str) -> Investigation:
    case = investigation_service.get_investigation(db, user, case_reference)
    if Permission.EVIDENCE_UPLOAD not in permissions_for(user.role) or not _on_team(db, user, case):
        raise ForbiddenError("Only investigation team members who handle evidence can add this.")
    if case.status in ("closed", "archived"):
        raise ConflictError(f"The investigation is {case.status}; it can no longer be changed.")
    return case


def _require_reviewer(db: Session, user: User, case_reference: str) -> Investigation:
    case = investigation_service.get_investigation(db, user, case_reference)
    if Permission.EVIDENCE_VERIFY not in permissions_for(user.role) or not _on_team(db, user, case):
        raise ForbiddenError("Your role cannot review extracted information for this case.")
    return case
