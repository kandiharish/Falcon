"""Correlation use cases: run the engine for a case, list, open, review.

Running is safe to repeat:
  • pairs found again are updated (their review stays);
  • new pairs are added as "pending review";
  • pairs no longer found are removed — unless a person reviewed them, then they are kept and
    marked STALE so the reviewer can see the relationship no longer holds.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.correlation import engine
from app.models import (
    Correlation,
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
from app.services import audit_service, investigation_service, notification_service
from app.services.errors import ForbiddenError, InvalidInputError, NotFoundError
from app.services.request_context import RequestContext

log = logging.getLogger("falcon.correlation")


@dataclass(frozen=True)
class RunSummary:
    created: int
    updated: int
    removed: int
    stale: int
    total: int


@dataclass(frozen=True)
class CorrelationFilters:
    level: str | None = None
    review_status: str | None = None
    evidence_reference: str | None = None
    include_stale: bool = True


# ---------- Running the engine ------------------------------------------------------------


def run(
    db: Session, user: User, case_reference: str, context: RequestContext | None = None
) -> RunSummary:
    case = investigation_service.get_investigation(db, user, case_reference)
    _require_reviewer(db, user, case)
    return run_for_case(db, case, actor=user, context=context)


def run_for_case(
    db: Session,
    case: Investigation,
    actor: User | None = None,
    context: RequestContext | None = None,
) -> RunSummary:
    zone = ZoneInfo(case.time_zone or "UTC")
    facts = _load_facts(db, case.id)
    results = engine.correlate(
        list(facts.values()),
        describe_time=lambda t: t.astimezone(zone).strftime("%H:%M:%S") if t else "?",
    )
    existing = {
        (c.evidence_a_id, c.evidence_b_id): c
        for c in db.scalars(select(Correlation).where(Correlation.investigation_id == case.id))
    }
    created = updated = 0
    seen: set[tuple[uuid.UUID, uuid.UUID]] = set()
    for result in results:
        key = (result.evidence_a.id, result.evidence_b.id)
        seen.add(key)
        factors = [f.as_dict() for f in result.factors]
        correlation = existing.get(key)
        if correlation is None:
            number = reference_counters.next_value(db, case.id, "COR")
            db.add(
                Correlation(
                    investigation_id=case.id,
                    reference=f"COR-{number:03d}",
                    evidence_a_id=key[0],
                    evidence_b_id=key[1],
                    score=result.score,
                    level=result.level,
                    factors=factors,
                    algorithm=engine.ALGORITHM,
                    stale=False,
                )
            )
            created += 1
        elif (
            correlation.score != result.score or correlation.factors != factors or correlation.stale
        ):
            correlation.score, correlation.level, correlation.factors = (
                result.score,
                result.level,
                factors,
            )
            correlation.algorithm, correlation.stale = engine.ALGORITHM, False
            updated += 1

    removed = stale = 0
    for key, correlation in existing.items():
        if key in seen:
            continue
        if correlation.review_status == "pending":
            db.delete(correlation)
            removed += 1
        elif not correlation.stale:
            correlation.stale = True
            stale += 1

    total = len(results)
    if created:
        new_levels = [
            r.level for r in results if (r.evidence_a.id, r.evidence_b.id) not in existing
        ]
        strong = sum(1 for level in new_levels if level in ("high", "medium"))
        notification_service.notify(
            db,
            case.lead_investigator_id,
            "correlation_detected",
            f"New potential relationships in {case.reference}",
            body=f"{created} found ({strong} medium or high). They need analyst review.",
            link="/correlations",
            investigation_id=case.id,
            actor=actor,
        )
    audit_service.record(
        db,
        "correlation.run",
        actor=actor,
        actor_email=None if actor else "correlation-engine",
        object_type="investigation",
        object_id=case.reference,
        new_state={
            "created": created,
            "updated": updated,
            "removed": removed,
            "stale": stale,
            "total": total,
            "algorithm": engine.ALGORITHM,
        },
        context=context,
    )
    db.commit()
    return RunSummary(created, updated, removed, stale, total)


def _load_facts(db: Session, case_id: uuid.UUID) -> dict[uuid.UUID, engine.EvidenceFacts]:
    """Turn database rows into the engine's plain input. Rejected facts are left out."""
    evidence = db.scalars(select(Evidence).where(Evidence.investigation_id == case_id)).all()
    facts = {e.id: engine.EvidenceFacts(id=e.id, reference=e.reference) for e in evidence}

    events = db.scalars(
        select(Event)
        .where(Event.investigation_id == case_id, Event.review_status != "rejected")
        .options(selectinload(Event.participants).selectinload(EventParticipant.entity))
    ).all()
    for event in events:
        item = facts[event.evidence_id]
        item.events.append(
            engine.EventFact(
                event.id, event.reference, event.occurred_at, event.latitude, event.longitude
            )
        )
        # Taking part in an event recorded from this evidence = appearing in this evidence.
        for participant in event.participants:
            _remember(item, participant.entity, event.confidence)

    mentions = db.execute(
        select(EntityMention, Entity)
        .join(Entity, EntityMention.entity_id == Entity.id)
        .where(Entity.investigation_id == case_id, Entity.review_status != "rejected")
    ).all()
    for mention, entity in mentions:
        _remember(facts[mention.evidence_id], entity, mention.confidence)
    return facts


def _remember(item: engine.EvidenceFacts, entity: Entity, confidence: float) -> None:
    if entity.review_status == "rejected":
        return
    current = item.entities.get(entity.id)
    if current is None or confidence > current[1]:
        item.entities[entity.id] = (
            engine.EntityFact(entity.id, entity.reference, entity.label),
            confidence,
        )


# ---------- Reading -----------------------------------------------------------------------


def _query(case_id: uuid.UUID):
    return (
        select(Correlation)
        .where(Correlation.investigation_id == case_id)
        .options(
            selectinload(Correlation.evidence_a),
            selectinload(Correlation.evidence_b),
            selectinload(Correlation.reviewed_by),
        )
    )


def list_correlations(
    db: Session,
    user: User,
    case_reference: str,
    filters: CorrelationFilters,
    limit: int,
    offset: int,
) -> tuple[list[Correlation], int]:
    case = investigation_service.get_investigation(db, user, case_reference)
    query = _query(case.id)
    if filters.level:
        query = query.where(Correlation.level == filters.level)
    if filters.review_status:
        query = query.where(Correlation.review_status == filters.review_status)
    if not filters.include_stale:
        query = query.where(Correlation.stale.is_(False))
    if filters.evidence_reference:
        ref = filters.evidence_reference.upper()
        query = query.where(
            or_(
                Correlation.evidence_a.has(reference=ref), Correlation.evidence_b.has(reference=ref)
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(Correlation.stale, Correlation.score.desc(), Correlation.reference)
        .limit(limit)
        .offset(offset)
    ).all()
    return list(rows), total


def get_correlation(db: Session, user: User, case_reference: str, reference: str) -> Correlation:
    case = investigation_service.get_investigation(db, user, case_reference)
    correlation = db.scalar(
        _query(case.id)
        .where(Correlation.reference == reference.upper())
        .execution_options(populate_existing=True)
    )
    if correlation is None:
        raise NotFoundError("This correlation does not exist in this investigation.")
    return correlation


def supporting_events(db: Session, correlation: Correlation) -> list[Event]:
    """The events the time/location factors are based on."""
    references = {
        ref
        for factor in correlation.factors
        for ref in (factor["details"].get("event_a"), factor["details"].get("event_b"))
        if ref
    }
    if not references:
        return []
    return list(
        db.scalars(
            select(Event)
            .where(
                Event.investigation_id == correlation.investigation_id,
                Event.reference.in_(references),
            )
            .options(
                selectinload(Event.participants).selectinload(EventParticipant.entity),
                selectinload(Event.evidence),
            )
            .order_by(Event.occurred_at)
        )
    )


def counts_by_investigation(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not ids:
        return {}
    return dict(
        db.execute(
            select(Correlation.investigation_id, func.count())
            .where(Correlation.investigation_id.in_(ids), Correlation.stale.is_(False))
            .group_by(Correlation.investigation_id)
        ).all()
    )


# ---------- Review ------------------------------------------------------------------------


def review(
    db: Session,
    user: User,
    case_reference: str,
    reference: str,
    status: str,
    note: str | None,
    context: RequestContext,
) -> Correlation:
    case = investigation_service.get_investigation(db, user, case_reference)
    _require_reviewer(db, user, case)
    if status == "rejected" and not (note and note.strip()):
        raise InvalidInputError("Give a short reason when rejecting a potential relationship.")
    correlation = get_correlation(db, user, case_reference, reference)
    previous = correlation.review_status
    correlation.review_status = status
    correlation.review_note = (note or "").strip() or None
    correlation.reviewed_by_id = user.id if status != "pending" else None
    correlation.reviewed_at = datetime.now(UTC) if status != "pending" else None
    audit_service.record(
        db,
        "correlation.reviewed",
        actor=user,
        object_type="correlation",
        object_id=f"{case.reference}/{correlation.reference}",
        previous_state={"review_status": previous},
        new_state={"review_status": status},
        note=note,
        context=context,
    )
    db.commit()
    return get_correlation(db, user, case_reference, reference)


def _require_reviewer(db: Session, user: User, case: Investigation) -> None:
    allowed = Permission.CORRELATION_REVIEW in permissions_for(user.role)
    on_team = user.role == Role.SUPERVISOR or (
        investigation_service.repo.membership(db, case.id, user.id) is not None
    )
    if not (allowed and on_team):
        raise ForbiddenError("Your role cannot run or review correlations for this case.")


def refresh_quietly(db: Session, investigation_id: uuid.UUID) -> None:
    """Re-run correlation after something changed (new evidence processed, a fact reviewed).
    A failure here must never break the action that triggered it, so it is logged instead."""
    try:
        case = db.get(Investigation, investigation_id)
        if case is not None:
            run_for_case(db, case)
    except Exception:
        log.exception("Automatic correlation refresh failed for investigation %s", investigation_id)
        db.rollback()
