"""Natural-language search, step 2: RUN the validated plan with ordinary database queries.

Results therefore are always real records with their IDs. Only the READING of the question
is AI-assisted, and the plan is shown to the user so they can see (and correct) it.
"""

import logging
import time as clock
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai import provider as ai
from app.ai.search_plan import CaseVocabulary, SearchPlan, rules_plan, system_prompt, validate
from app.core.config import get_settings
from app.graph import builder
from app.models import Entity, EntityMention, Event, EventParticipant, Evidence, Investigation, User
from app.services import (
    audit_service,
    extraction_service,
    graph_service,
    investigation_service,
    similarity_service,
)
from app.services.request_context import RequestContext

log = logging.getLogger("falcon.ai")
MAX_RESULTS = 100


@dataclass
class SearchResult:
    question: str
    plan: SearchPlan
    notes: list[str]
    interpreted_by: str  # the model name, or "rules"
    duration_ms: int
    events: list[Event] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    path: list[builder.Edge] = field(default_factory=list)
    nodes: dict[str, builder.Node] = field(default_factory=dict)
    passages: list[similarity_service.SearchHit] = field(default_factory=list)


def vocabulary(db: Session, case: Investigation) -> CaseVocabulary:
    entities = db.scalars(
        select(Entity)
        .where(Entity.investigation_id == case.id, Entity.review_status != "rejected")
        .order_by(Entity.reference)
    )
    evidence = db.scalars(
        select(Evidence).where(Evidence.investigation_id == case.id).order_by(Evidence.reference)
    )
    zone = ZoneInfo(case.time_zone or "UTC")
    return CaseVocabulary(
        entities={e.reference: (e.entity_type, e.label) for e in entities},
        evidence={
            e.reference: (e.evidence_type, e.description or e.original_filename) for e in evidence
        },
        time_zone=case.time_zone or "UTC",
        today=datetime.now(zone).date(),
    )


def interpret(question: str, vocab: CaseVocabulary) -> tuple[SearchPlan, str, list[str]]:
    """Ask the local model to fill in the plan; fall back to rules if AI is unavailable."""
    try:
        reply = ai.current().chat(
            [
                {"role": "system", "content": system_prompt(vocab)},
                {"role": "user", "content": question},
            ],
            schema=SearchPlan.model_json_schema(),
        )
        plan = SearchPlan.model_validate_json(reply.content)
        by = get_settings().ai_chat_model
    except ai.AIUnavailable:
        plan, by = rules_plan(question, vocab), "rules"
    except ValueError:  # the model replied with something that is not a valid plan
        log.warning("AI search plan was not valid JSON; using rules")
        plan, by = rules_plan(question, vocab), "rules"
    clean, notes = validate(plan, vocab, question)
    return clean, by, notes


def search(
    db: Session, user: User, case_reference: str, question: str, context: RequestContext
) -> SearchResult:
    started = clock.monotonic()
    case = investigation_service.get_investigation(db, user, case_reference)
    vocab = vocabulary(db, case)
    plan, by, notes = interpret(question, vocab)
    result = run_plan(db, user, case, plan, question, by, notes)
    result.duration_ms = int((clock.monotonic() - started) * 1000)
    audit_service.record(
        db,
        "ai.search",
        actor=user,
        object_type="investigation",
        object_id=case.reference,
        new_state={"question": question[:500], "plan": plan.model_dump(), "interpreted_by": by},
        context=context,
    )
    db.commit()
    return result


def run_plan(
    db: Session,
    user: User,
    case: Investigation,
    plan: SearchPlan,
    question: str = "",
    interpreted_by: str = "manual",
    notes: list[str] | None = None,
) -> SearchResult:
    result = SearchResult(question, plan, notes or [], interpreted_by, 0)
    if plan.intent == "events":
        result.events = _events(db, user, case, plan)
    elif plan.intent == "evidence":
        result.evidence = _evidence(db, case, plan)
    elif plan.intent == "entities":
        result.entities = _entities(db, case, plan)
    elif plan.intent == "connection":
        _connection(db, user, case, plan, result)
    if plan.text:
        try:
            result.passages = similarity_service.search(db, user, case.reference, plan.text)
        except ai.AIUnavailable:
            result.notes.append("Searching document text by meaning needs the local AI service.")
    return result


def _events(db: Session, user: User, case: Investigation, plan: SearchPlan) -> list[Event]:
    zone = ZoneInfo(case.time_zone or "UTC")
    start = _moment(plan.date_from, time.min, zone)
    end = _moment(plan.date_to, time.max, zone)
    base = extraction_service.EventFilters(
        event_types=tuple(plan.event_types),
        occurred_from=start,
        occurred_to=end,
        evidence_type=plan.evidence_types[0] if len(plan.evidence_types) == 1 else None,
    )
    found: dict[uuid.UUID, Event] = {}
    refs = plan.entity_refs or [None]  # several entities = events involving ANY of them
    for ref in refs:
        filters = extraction_service.EventFilters(**{**base.__dict__, "entity_reference": ref})
        for evidence_ref in plan.evidence_refs or [None]:
            filters = extraction_service.EventFilters(
                **{**filters.__dict__, "evidence_reference": evidence_ref}
            )
            events, _ = extraction_service.list_events(
                db, user, case.reference, filters, limit=500, offset=0
            )
            found.update({e.id: e for e in events if e.review_status != "rejected"})
    events = sorted(
        found.values(),
        key=lambda e: (e.occurred_at or datetime.max.replace(tzinfo=UTC), e.reference),
    )
    if plan.time_from or plan.time_to:
        events = [e for e in events if _in_window(e, plan, zone)]
    return events[:MAX_RESULTS]


def _moment(day: str | None, at: time, zone: ZoneInfo) -> datetime | None:
    return datetime.combine(date.fromisoformat(day), at, zone) if day else None


def _in_window(event: Event, plan: SearchPlan, zone: ZoneInfo) -> bool:
    """Time-of-day window in the case's zone, by whole minutes; "22:00 to 02:00" wraps midnight."""
    if not event.occurred_at:
        return False
    local = event.occurred_at.astimezone(zone)
    minute = local.hour * 60 + local.minute
    start = _minutes(plan.time_from) if plan.time_from else 0
    end = _minutes(plan.time_to) if plan.time_to else 24 * 60 - 1
    return start <= minute <= end if start <= end else minute >= start or minute <= end


def _minutes(clock_time: str) -> int:
    parsed = time.fromisoformat(clock_time)
    return parsed.hour * 60 + parsed.minute


def _evidence(db: Session, case: Investigation, plan: SearchPlan) -> list[Evidence]:
    query = select(Evidence).where(Evidence.investigation_id == case.id)
    if plan.entity_refs:
        refs = [r.upper() for r in plan.entity_refs]
        mentioned = (
            select(EntityMention.evidence_id)
            .join(Entity, EntityMention.entity_id == Entity.id)
            .where(Entity.investigation_id == case.id, Entity.reference.in_(refs))
        )
        involved = (
            select(Event.evidence_id)
            .join(EventParticipant, EventParticipant.event_id == Event.id)
            .join(Entity, EventParticipant.entity_id == Entity.id)
            .where(Entity.investigation_id == case.id, Entity.reference.in_(refs))
        )
        query = query.where(or_(Evidence.id.in_(mentioned), Evidence.id.in_(involved)))
    if plan.evidence_refs:
        query = query.where(Evidence.reference.in_(plan.evidence_refs))
    if plan.evidence_types:
        query = query.where(Evidence.evidence_type.in_(plan.evidence_types))
    return list(db.scalars(query.order_by(Evidence.reference).limit(MAX_RESULTS)))


def _entities(db: Session, case: Investigation, plan: SearchPlan) -> list[Entity]:
    query = select(Entity).where(
        Entity.investigation_id == case.id, Entity.review_status != "rejected"
    )
    if plan.entity_refs:
        query = query.where(Entity.reference.in_(plan.entity_refs))
    if plan.entity_types:
        query = query.where(Entity.entity_type.in_(plan.entity_types))
    if plan.evidence_refs:
        query = query.where(
            Entity.mentions.any(
                EntityMention.evidence.has(Evidence.reference.in_(plan.evidence_refs))
            )
        )
    return list(db.scalars(query.order_by(Entity.entity_type, Entity.reference).limit(MAX_RESULTS)))


def _connection(
    db: Session, user: User, case: Investigation, plan: SearchPlan, result: SearchResult
) -> None:
    ids = [builder.entity_id(r) for r in plan.entity_refs] + [
        builder.evidence_id(r) for r in plan.evidence_refs
    ]
    graph = graph_service.graph(
        db, user, case.reference, builder.Options(include_events=True, max_nodes=1000)
    )
    result.nodes = {n.id: n for n in graph.nodes}
    result.path = builder.shortest_path(graph.edges, ids[0], ids[1])
    if not result.path:
        result.notes.append(
            f"No chain of links was found between {ids[0].split(':')[1]} "
            f"and {ids[1].split(':')[1]}."
        )
