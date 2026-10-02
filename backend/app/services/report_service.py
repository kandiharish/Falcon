"""Investigation reports (plan §24): generate, list, open, export, verify.

    case data ──► build_content() ──► JSON snapshot ──► canonical bytes ──► SHA-256
                                          │
     OBSERVED EVIDENCE          what was found, with provenance (evidence, entities, events)
     ANALYTICAL INTERPRETATION  correlations, relationships, analyst notes — labelled as such
     RECORD                     limitations, audit information, the fingerprint

Rejected items are left out; pending items are included but marked "requires review".
"""

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.graph import builder
from app.models import (
    AuditLog,
    Correlation,
    Event,
    EventParticipant,
    Evidence,
    Investigation,
    InvestigationMember,
    Report,
    Task,
    User,
)
from app.repositories import reference_counters
from app.security.permissions import Permission, Role, permissions_for
from app.services import (
    audit_service,
    extraction_service,
    graph_service,
    investigation_service,
    notification_service,
)
from app.services.errors import ForbiddenError, InvalidInputError, NotFoundError
from app.services.request_context import RequestContext

SCHEMA = "falcon-report-v1"
LOW_CONFIDENCE = 0.7


@dataclass(frozen=True)
class ReportRequest:
    title: str
    analyst_notes: str = ""
    limitations: str = ""
    include_pending: bool = True


def canonical(content: dict[str, Any]) -> bytes:
    """One exact byte form of the content: sorted keys, no spaces. Same content → same hash."""
    return json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def fingerprint(content: dict[str, Any]) -> str:
    return hashlib.sha256(canonical(content)).hexdigest()


# ---------- Generate ----------------------------------------------------------------------


def generate(
    db: Session, user: User, case_reference: str, request: ReportRequest, context: RequestContext
) -> Report:
    case = investigation_service.get_investigation(db, user, case_reference)
    _require_author(db, user, case)
    title = request.title.strip()
    if len(title) < 3:
        raise InvalidInputError("Give the report a title of at least 3 characters.")
    number = reference_counters.next_value(db, case.id, "RPT")
    report = Report(
        investigation_id=case.id,
        reference=f"RPT-{number:03d}",
        title=title[:200],
        status="generating",
        generated_by_id=user.id,
    )
    db.add(report)
    db.flush()
    try:
        content = build_content(db, user, case, report, request)
        report.content = content
        report.content_sha256 = fingerprint(content)
        report.status = "ready"
    except Exception as error:  # a failed report is kept, with the reason, never half-shown
        db.rollback()
        db.add(report)
        report.status, report.error_message = "failed", str(error)[:500]
    report.completed_at = datetime.now(UTC)
    audit_service.record(
        db,
        "report.generated",
        actor=user,
        object_type="report",
        object_id=f"{case.reference}/{report.reference}",
        new_state={"status": report.status, "sha256": report.content_sha256, "title": report.title},
        context=context,
    )
    if report.status == "ready":
        notification_service.notify(
            db,
            case.lead_investigator_id,
            "report_ready",
            f"Report {report.reference} ready for {case.reference}",
            body=f"“{report.title}” by {user.display_name}.",
            link=f"/investigations/{case.reference}/reports/{report.reference}",
            investigation_id=case.id,
            actor=user,
        )
    db.commit()
    return get_report(db, user, case.reference, report.reference)


def build_content(
    db: Session, user: User, case: Investigation, report: Report, request: ReportRequest
) -> dict[str, Any]:
    allowed = ("confirmed", "pending") if request.include_pending else ("confirmed",)
    generated_at = datetime.now(UTC)

    evidence = list(
        db.scalars(
            select(Evidence)
            .where(Evidence.investigation_id == case.id)
            .options(selectinload(Evidence.uploaded_by))
            .order_by(Evidence.reference)
        )
    )
    entity_rows, _ = extraction_service.list_entities(
        db, user, case.reference, extraction_service.EntityFilters(), limit=500, offset=0
    )
    entities = [(e, s) for e, s in entity_rows if e.review_status in allowed]
    events = [
        e
        for e in db.scalars(
            select(Event)
            .where(Event.investigation_id == case.id)
            .options(
                selectinload(Event.participants).selectinload(EventParticipant.entity),
                selectinload(Event.evidence),
            )
            .order_by(Event.occurred_at.asc().nulls_last(), Event.reference)
        )
        if e.review_status in allowed
    ]
    correlations = [
        c
        for c in db.scalars(
            select(Correlation)
            .where(Correlation.investigation_id == case.id, Correlation.stale.is_(False))
            .options(
                selectinload(Correlation.evidence_a),
                selectinload(Correlation.evidence_b),
                selectinload(Correlation.reviewed_by),
            )
            .order_by(Correlation.score.desc())
        )
        if c.review_status in allowed
    ]
    graph = graph_service.graph(db, user, case.reference, builder.Options(include_evidence=False))
    members = list(
        db.scalars(
            select(InvestigationMember)
            .where(InvestigationMember.investigation_id == case.id)
            .options(selectinload(InvestigationMember.user))
        )
    )

    def when(moment: datetime | None) -> str | None:
        return moment.astimezone(UTC).isoformat() if moment else None

    timed = [e.occurred_at for e in events if e.occurred_at]
    important = sorted(
        entities, key=lambda es: (-es[1].evidence_count, -es[1].event_count, es[0].reference)
    )
    return {
        "schema": SCHEMA,
        "report": {
            "reference": report.reference,
            "title": report.title,
            "generated_at": generated_at.isoformat(),
            "generated_by": user.display_name,
            "include_pending": request.include_pending,
        },
        "summary": {
            "reference": case.reference,
            "title": case.title,
            "case_type": case.case_type,
            "status": case.status,
            "priority": case.priority,
            "stage": case.stage,
            "location": case.location,
            "time_zone": case.time_zone,
            "description": case.description,
            "lead": case.lead_investigator.display_name,
            "team": sorted(f"{m.user.display_name} ({m.role_in_case})" for m in members),
            "opened_at": when(case.created_at),
        },
        "scope": {
            "period_from": when(min(timed)) if timed else None,
            "period_to": when(max(timed)) if timed else None,
            "counts": {
                "evidence": len(evidence),
                "entities": len(entities),
                "events": len(events),
                "correlations": len(correlations),
            },
            "included": (
                "Confirmed items, and items still awaiting review (marked as such)."
                if request.include_pending
                else "Only items confirmed by an analyst."
            ),
            "excluded": "Items rejected by an analyst, and relationships no longer found.",
        },
        "evidence": [
            {
                "reference": e.reference,
                "type": e.evidence_type,
                "description": e.description or e.original_filename,
                "source": e.source,
                "collected_at": when(e.collected_at),
                "location": e.location_text,
                "status": e.status,
                "sha256": e.sha256,
                "integrity_ok": e.integrity_ok,
                "integrity_checked_at": when(e.integrity_checked_at),
                "uploaded_by": e.uploaded_by.display_name,
                "uploaded_at": when(e.created_at),
            }
            for e in evidence
        ],
        "sources": dict(sorted(Counter(e.evidence_type for e in evidence).items())),
        "entities": [
            {
                "reference": e.reference,
                "type": e.entity_type,
                "label": e.label,
                "review_status": e.review_status,
                "evidence_count": s.evidence_count,
                "event_count": s.event_count,
                "max_confidence": s.max_confidence,
            }
            for e, s in important[:25]
        ],
        "timeline": [
            {
                "reference": e.reference,
                "occurred_at": when(e.occurred_at),
                "type": e.event_type,
                "description": e.description,
                "location": e.location_text,
                "evidence": e.evidence.reference,
                "assertion": e.assertion_kind,
                "confidence": round(e.confidence, 3),
                "review_status": e.review_status,
                "participants": [f"{p.entity.reference} ({p.role})" for p in e.participants],
            }
            for e in events
        ],
        "correlations": [
            {
                "reference": c.reference,
                "evidence_a": c.evidence_a.reference,
                "evidence_b": c.evidence_b.reference,
                "level": c.level,
                "score": c.score,
                "reasons": [f["explanation"] for f in c.factors],
                "review_status": c.review_status,
                "review_note": c.review_note,
                "reviewed_by": c.reviewed_by.display_name if c.reviewed_by else None,
            }
            for c in correlations
        ],
        "relationships": [
            {
                "from": e.source.split(":")[1],
                "to": e.target.split(":")[1],
                "type": e.type,
                "why": e.why,
                "review_status": e.review_status,
            }
            for e in graph.edges
            if e.type in ("communicated_with", "connected_to") and e.review_status in allowed
        ],
        "analyst_notes": {
            "written": request.analyst_notes.strip(),
            "observations": [
                {
                    "reference": e.reference,
                    "occurred_at": when(e.occurred_at),
                    "description": e.description,
                    "evidence": e.evidence.reference,
                }
                for e in events
                if e.assertion_kind == "user_entered"
            ],
        },
        "limitations": {
            "written": request.limitations.strip(),
            "automatic": _limitations(db, case, evidence, entities, events, correlations),
        },
        "audit": _audit_summary(db, case),
    }


def _limitations(db, case, evidence, entities, events, correlations) -> list[str]:
    notes = []
    pending_entities = sum(1 for e, _ in entities if e.review_status == "pending")
    pending_events = sum(1 for e in events if e.review_status == "pending")
    if pending_entities or pending_events:
        notes.append(
            f"{pending_entities} entities and {pending_events} events have not yet been reviewed "
            "by an analyst; they are machine-extracted and may contain errors."
        )
    pending_cor = sum(1 for c in correlations if c.review_status == "pending")
    if pending_cor:
        notes.append(
            f"{pending_cor} of {len(correlations)} correlations are potential relationships "
            "awaiting analyst review. Correlation indicates association, not proof."
        )
    unverified = [e.reference for e in evidence if e.integrity_ok is not True]
    if unverified:
        notes.append(f"Integrity not verified for: {', '.join(unverified)}.")
    low = [e.reference for e in events if e.confidence < LOW_CONFIDENCE]
    if low:
        notes.append(
            f"{len(low)} events rest on low-confidence readings (below {LOW_CONFIDENCE:.0%}), "
            f"e.g. OCR of scanned paper: {', '.join(low[:8])}{'…' if len(low) > 8 else ''}."
        )
    untimed = [e.reference for e in events if e.occurred_at is None]
    if untimed:
        notes.append(
            f"{len(untimed)} events have no known time and are not placed on the timeline."
        )
    open_tasks = db.scalar(
        select(func.count()).where(Task.investigation_id == case.id, Task.status != "completed")
    )
    if open_tasks:
        notes.append(
            f"{open_tasks} investigation tasks were still open when this report was generated."
        )
    notes.append(
        "AI-assisted search and assistant answers are not part of this report; every statement "
        "here comes from recorded evidence, extraction and analyst review."
    )
    return notes


def _audit_summary(db: Session, case: Investigation) -> dict[str, Any]:
    scope = (AuditLog.object_id == case.reference) | AuditLog.object_id.like(f"{case.reference}/%")
    total = db.scalar(select(func.count()).where(scope)) or 0
    by_action = db.execute(
        select(AuditLog.action, func.count()).where(scope).group_by(AuditLog.action)
    ).all()
    last = db.scalar(select(func.max(AuditLog.occurred_at)).where(scope))
    return {
        "entries": total,
        "by_action": dict(sorted((a, n) for a, n in by_action)),
        "last_activity": last.astimezone(UTC).isoformat() if last else None,
        "note": "The audit log is append-only: entries cannot be edited or deleted through FALCON.",
    }


# ---------- Read ----------------------------------------------------------------------------


def list_reports(db: Session, user: User, case_reference: str) -> list[Report]:
    case = investigation_service.get_investigation(db, user, case_reference)
    return list(
        db.scalars(
            select(Report)
            .where(Report.investigation_id == case.id)
            .options(selectinload(Report.generated_by), selectinload(Report.investigation))
            .order_by(Report.created_at.desc())
        )
    )


def get_report(db: Session, user: User, case_reference: str, reference: str) -> Report:
    case = investigation_service.get_investigation(db, user, case_reference)
    report = db.scalar(
        select(Report)
        .where(Report.investigation_id == case.id, Report.reference == reference.upper())
        .options(selectinload(Report.generated_by), selectinload(Report.investigation))
    )
    if report is None:
        raise NotFoundError("This report does not exist in this investigation.")
    return report


def verify(report: Report) -> bool:
    """Does the stored content still match the fingerprint taken when it was generated?"""
    return bool(report.content and report.content_sha256 == fingerprint(report.content))


def record_export(db: Session, user: User, report: Report, context: RequestContext) -> None:
    audit_service.record(
        db,
        "report.exported",
        actor=user,
        object_type="report",
        object_id=f"{report.investigation.reference}/{report.reference}",
        new_state={"sha256": report.content_sha256},
        context=context,
    )
    db.commit()


def _require_author(db: Session, user: User, case: Investigation) -> None:
    if Permission.REPORT_GENERATE not in permissions_for(user.role):
        raise ForbiddenError("Your role cannot generate reports.")
    if (
        user.role != Role.SUPERVISOR
        and investigation_service.repo.membership(db, case.id, user.id) is None
    ):
        raise ForbiddenError("Only members of the investigation team can generate its reports.")
