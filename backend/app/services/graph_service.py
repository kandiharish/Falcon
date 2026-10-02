"""Relationship graph use case: load a case's facts and hand them to the pure builder.

Five queries per request, whatever the size of the case; no N+1 lookups.
"""

from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.graph import builder
from app.models import Correlation, Entity, EntityMention, Event, EventParticipant, Evidence, User
from app.services import investigation_service
from app.services.errors import InvalidInputError


def graph(db: Session, user: User, case_reference: str, options: builder.Options) -> builder.Graph:
    case = investigation_service.get_investigation(db, user, case_reference)
    zone = ZoneInfo(case.time_zone or "UTC")
    if options.focus and not options.focus.startswith(("entity:", "evidence:", "event:")):
        raise InvalidInputError("Focus must look like entity:P001, evidence:IMG-001 or event:E001.")

    entities = db.scalars(select(Entity).where(Entity.investigation_id == case.id)).all()
    evidence = db.scalars(select(Evidence).where(Evidence.investigation_id == case.id)).all()
    by_evidence_id = {e.id: e.reference for e in evidence}
    by_entity_id = {e.id: e.reference for e in entities}

    mentions = db.scalars(
        select(EntityMention)
        .join(Entity, EntityMention.entity_id == Entity.id)
        .where(Entity.investigation_id == case.id)
    ).all()
    events = db.scalars(
        select(Event)
        .where(Event.investigation_id == case.id)
        .options(selectinload(Event.participants))
    ).all()
    correlations = db.scalars(
        select(Correlation).where(Correlation.investigation_id == case.id)
    ).all()

    return builder.build(
        entities=[
            builder.EntityIn(e.reference, e.entity_type, e.label, e.review_status) for e in entities
        ],
        evidence=[
            builder.EvidenceIn(
                e.reference, e.evidence_type, e.description or e.original_filename, e.status
            )
            for e in evidence
        ],
        mentions=[
            builder.MentionIn(
                by_entity_id[m.entity_id],
                by_evidence_id[m.evidence_id],
                m.assertion_kind,
                m.confidence,
                m.source_location,
            )
            for m in mentions
        ],
        events=[
            builder.EventIn(
                reference=e.reference,
                event_type=e.event_type,
                description=e.description,
                occurred_at=e.occurred_at,
                evidence=by_evidence_id[e.evidence_id],
                assertion_kind=e.assertion_kind,
                confidence=e.confidence,
                review_status=e.review_status,
                participants=tuple((by_entity_id[p.entity_id], p.role) for p in _participants(e)),
            )
            for e in events
        ],
        correlations=[
            builder.CorrelationIn(
                reference=c.reference,
                evidence_a=by_evidence_id[c.evidence_a_id],
                evidence_b=by_evidence_id[c.evidence_b_id],
                score=c.score,
                level=c.level,
                factor_kinds=tuple(f["kind"] for f in c.factors),
                review_status=c.review_status,
                stale=c.stale,
            )
            for c in correlations
        ],
        options=options,
        describe_time=lambda t: t.astimezone(zone).strftime("%d %b %H:%M"),
    )


def _participants(event: Event) -> list[EventParticipant]:
    return sorted(event.participants, key=lambda p: p.role)
