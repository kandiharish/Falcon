"""Load a case's facts for the insights engine, including matches in OTHER cases.

Matches in other cases follow a hit / no-hit rule, as police databases do: a case the user is
on (or every case, for a supervisor) is named; any other case is only counted, never named,
so a match can be raised with a supervisor without leaking what another team is doing.
"""

import uuid
from zoneinfo import ZoneInfo

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session, selectinload

from app.insights import engine
from app.models import Correlation, Entity, Event, EventParticipant, Investigation, User
from app.services import investigation_service
from app.services.dashboard_service import visible_case_ids

# Identifiers precise enough to mean "the same thing" across cases. Names are not:
# two different people can share a name.
CROSS_CASE_TYPES = ("phone_number", "vehicle", "account", "device")


def build(db: Session, user: User, case_reference: str) -> list[engine.Insight]:
    case = investigation_service.get_investigation(db, user, case_reference)
    facts = engine.CaseFacts(time_zone=ZoneInfo(case.time_zone))

    events = db.scalars(
        select(Event)
        .where(Event.investigation_id == case.id, Event.review_status != "rejected")
        .options(
            selectinload(Event.evidence),
            selectinload(Event.participants).selectinload(EventParticipant.entity),
        )
    ).all()
    for event in events:
        facts.events.append(
            engine.EventInfo(
                reference=event.reference,
                evidence_reference=event.evidence.reference,
                evidence_type=event.evidence.evidence_type,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
                latitude=event.latitude,
                longitude=event.longitude,
                place=event.location_text,
                participants=tuple(
                    _ref(p.entity)
                    for p in event.participants
                    if p.entity.review_status != "rejected"
                ),
            )
        )

    correlations = db.scalars(
        select(Correlation)
        .where(
            Correlation.investigation_id == case.id,
            Correlation.stale.is_(False),
            Correlation.review_status != "rejected",
        )
        .options(selectinload(Correlation.evidence_a), selectinload(Correlation.evidence_b))
        .order_by(Correlation.score.desc())
    ).all()
    facts.correlations = [
        engine.CorrelationInfo(
            c.reference,
            c.level,
            c.review_status,
            c.evidence_a.reference,
            c.evidence_b.reference,
            c.score,
        )
        for c in correlations
    ]
    facts.other_cases = _other_cases(db, user, case.id)
    return engine.analyse(facts)


def _other_cases(db: Session, user: User, case_id: uuid.UUID) -> list[engine.OtherCase]:
    mine = db.scalars(
        select(Entity).where(
            Entity.investigation_id == case_id,
            Entity.entity_type.in_(CROSS_CASE_TYPES),
            Entity.review_status != "rejected",
        )
    ).all()
    if not mine:
        return []
    by_key = {(e.entity_type, e.normalized_key): e for e in mine}
    matches = db.execute(
        select(Entity.entity_type, Entity.normalized_key, Investigation)
        .join(Investigation, Entity.investigation_id == Investigation.id)
        .where(
            tuple_(Entity.entity_type, Entity.normalized_key).in_(list(by_key)),
            Entity.investigation_id != case_id,
            Entity.review_status != "rejected",
        )
        .order_by(Investigation.reference)
    ).all()
    if not matches:
        return []
    visible = set(db.scalars(visible_case_ids(db, user)))
    hits = []
    for entity_type, key, other in matches:
        entity = _ref(by_key[(entity_type, key)])
        if other.id in visible:
            hits.append(engine.OtherCase(entity, other.reference, other.title))
        else:
            hits.append(engine.OtherCase(entity, None, None))
    return hits


def _ref(entity: Entity) -> engine.EntityRef:
    return engine.EntityRef(entity.reference, entity.entity_type, entity.label)
