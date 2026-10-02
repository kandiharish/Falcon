"""Global search (plan §28): one box, every kind of record, only in cases you can see.

Fast enough for typing: each kind is one indexed query (trigram index on investigations;
small per-case tables elsewhere), at most a few rows per kind. For questions in plain
words there is the AI-assisted search on the Analysis page.
"""

from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Correlation, Entity, Event, Evidence, Investigation, Report, Task, User
from app.services.dashboard_service import visible_case_ids

PER_KIND = 5


@dataclass
class Hit:
    kind: str  # investigation | evidence | entity | event | task | report | correlation
    reference: str
    title: str
    subtitle: str
    investigation_reference: str
    link: str


def search(db: Session, user: User, text: str) -> list[Hit]:
    term = text.strip()
    if len(term) < 2:
        return []
    like = f"%{term}%"
    digits = "".join(ch for ch in term if ch.isdigit())
    cases = visible_case_ids(db, user)
    hits: list[Hit] = []

    for i in db.scalars(
        select(Investigation)
        .where(
            Investigation.id.in_(cases),
            or_(
                Investigation.reference.ilike(like),
                Investigation.title.ilike(like),
                Investigation.location.ilike(like),
            ),
        )
        .order_by(Investigation.updated_at.desc())
        .limit(PER_KIND)
    ):
        hits.append(
            Hit(
                "investigation",
                i.reference,
                i.title,
                f"{i.case_type} · {i.status}",
                i.reference,
                f"/investigations/{i.reference}",
            )
        )

    def scoped(model, *conditions):
        return (
            select(model)
            .where(model.investigation_id.in_(cases), or_(*conditions))
            .options(selectinload(model.investigation))
            .limit(PER_KIND)
        )

    for e in db.scalars(
        scoped(
            Evidence,
            Evidence.reference.ilike(like),
            Evidence.description.ilike(like),
            Evidence.original_filename.ilike(like),
            Evidence.source.ilike(like),
            Evidence.location_text.ilike(like),
        )
    ):
        case = e.investigation.reference
        hits.append(
            Hit(
                "evidence",
                e.reference,
                e.description or e.original_filename,
                f"{e.evidence_type.replace('_', ' ')} · {case}",
                case,
                f"/investigations/{case}/evidence/{e.reference}",
            )
        )

    entity_conditions = [Entity.reference.ilike(like), Entity.label.ilike(like)]
    if len(digits) >= 4:  # phone numbers typed with spaces or dashes still match
        entity_conditions.append(Entity.normalized_key.ilike(f"%{digits}%"))
    for e in db.scalars(
        scoped(Entity, *entity_conditions).where(Entity.review_status != "rejected")
    ):
        case = e.investigation.reference
        hits.append(
            Hit(
                "entity",
                e.reference,
                e.label,
                f"{e.entity_type.replace('_', ' ')} · {case}",
                case,
                f"/investigations/{case}/entities/{e.reference}",
            )
        )

    for e in db.scalars(
        scoped(
            Event,
            Event.reference.ilike(like),
            Event.description.ilike(like),
            Event.location_text.ilike(like),
        )
        .where(Event.review_status != "rejected")
        .options(selectinload(Event.evidence))
    ):
        case = e.investigation.reference
        hits.append(
            Hit(
                "event",
                e.reference,
                e.description,
                f"{e.event_type.replace('_', ' ')} · {e.evidence.reference} · {case}",
                case,
                f"/investigations/{case}/evidence/{e.evidence.reference}",
            )
        )

    for t in db.scalars(scoped(Task, Task.reference.ilike(like), Task.title.ilike(like))):
        case = t.investigation.reference
        hits.append(
            Hit(
                "task",
                t.reference,
                t.title,
                f"task · {t.status.replace('_', ' ')} · {case}",
                case,
                f"/tasks?case={case}&task={t.reference}",
            )
        )

    for r in db.scalars(scoped(Report, Report.reference.ilike(like), Report.title.ilike(like))):
        case = r.investigation.reference
        hits.append(
            Hit(
                "report",
                r.reference,
                r.title,
                f"report · {case}",
                case,
                f"/investigations/{case}/reports/{r.reference}",
            )
        )

    if term.upper().startswith("COR"):
        for c in db.scalars(
            scoped(Correlation, Correlation.reference.ilike(like)).options(
                selectinload(Correlation.evidence_a), selectinload(Correlation.evidence_b)
            )
        ):
            case = c.investigation.reference
            hits.append(
                Hit(
                    "correlation",
                    c.reference,
                    f"{c.evidence_a.reference} ⟷ {c.evidence_b.reference}",
                    f"{c.level} potential relationship · {case}",
                    case,
                    f"/investigations/{case}/correlations/{c.reference}",
                )
            )
    return hits
