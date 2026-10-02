"""The command-center dashboard (plan §9, §33): real numbers from the cases YOU can see.

Every number is a count of real records, never a decoration. A supervisor sees all cases;
everyone else sees only the cases they are a member of (the same rule as everywhere else).
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import Select, cast, func, or_, select
from sqlalchemy import case as sql_case
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.types import Date

from app.models import (
    AuditLog,
    Correlation,
    Entity,
    Event,
    Evidence,
    Investigation,
    InvestigationMember,
    ProcessingJob,
    Task,
    User,
)
from app.services import investigation_service, task_service

ACTIVITY_DAYS = 14


@dataclass
class Dashboard:
    metrics: dict[str, int]
    evidence_by_type: dict[str, int]
    evidence_by_status: dict[str, int]
    correlations_by_level: dict[str, int]
    event_activity: dict[str, Any]  # {unit: hour|day, buckets: [(start ISO, count)]}
    activity_by_day: list[tuple[str, int]]
    recent_investigations: list[Investigation]
    recent_evidence: list[Evidence]
    pending_correlations: list[Correlation]
    recent_correlations: list[Correlation]
    my_tasks: list[Task]
    alerts: list[dict[str, str]] = field(default_factory=list)
    activity: list[AuditLog] = field(default_factory=list)


def visible_case_ids(db: Session, user: User) -> Select[tuple[uuid.UUID]]:
    if investigation_service.sees_all(user):
        return select(Investigation.id)
    return select(InvestigationMember.investigation_id).where(
        InvestigationMember.user_id == user.id
    )


def build(db: Session, user: User) -> Dashboard:
    cases = visible_case_ids(db, user)

    def count(model, *conditions) -> int:
        return (
            db.scalar(
                select(func.count())
                .select_from(model)
                .where(model.investigation_id.in_(cases), *conditions)
            )
            or 0
        )

    def grouped(column, model, *conditions) -> dict[str, int]:
        rows = db.execute(
            select(column, func.count())
            .where(model.investigation_id.in_(cases), *conditions)
            .group_by(column)
        ).all()
        return {str(k): n for k, n in sorted(rows, key=lambda r: -r[1])}

    processing = (
        db.scalar(
            select(func.count())
            .select_from(ProcessingJob)
            .join(Evidence, ProcessingJob.evidence_id == Evidence.id)
            .where(
                Evidence.investigation_id.in_(cases),
                ProcessingJob.status.in_(("queued", "running")),
            )
        )
        or 0
    )
    pending = (
        count(Entity, Entity.review_status == "pending")
        + count(Event, Event.review_status == "pending")
        + count(Correlation, Correlation.review_status == "pending", Correlation.stale.is_(False))
        + count(Evidence, Evidence.status == "requires_review")
    )
    metrics = {
        "active_investigations": db.scalar(
            select(func.count()).where(
                Investigation.id.in_(cases), Investigation.status == "active"
            )
        )
        or 0,
        "evidence_items": count(Evidence),
        "evidence_processing": processing,
        "entities": count(Entity, Entity.review_status != "rejected"),
        "events": count(Event, Event.review_status != "rejected"),
        "correlations": count(
            Correlation, Correlation.stale.is_(False), Correlation.review_status != "rejected"
        ),
        "requires_review": pending,
        "open_tasks": count(Task, Task.status != "completed"),
    }

    today = datetime.now(UTC).date()
    since = today - timedelta(days=ACTIVITY_DAYS - 1)
    # Audit object ids are "CASE-…" or "CASE-…/ITEM": match both.
    refs = list(db.scalars(select(Investigation.reference).where(Investigation.id.in_(cases))))
    audit_scope = (
        or_(AuditLog.object_id.in_(refs), *[AuditLog.object_id.like(f"{r}/%") for r in refs])
        if refs
        else AuditLog.id < 0
    )

    day = cast(AuditLog.occurred_at, Date)
    activity_rows = dict(
        db.execute(
            select(day, func.count())
            .where(audit_scope, AuditLog.occurred_at >= since)
            .group_by(day)
        ).all()
    )
    event_times = list(
        db.scalars(
            select(Event.occurred_at)
            .where(
                Event.investigation_id.in_(cases),
                Event.occurred_at.is_not(None),
                Event.review_status != "rejected",
            )
            .order_by(Event.occurred_at.desc())
            .limit(5000)
        )
    )

    case_options = (
        selectinload(Correlation.evidence_a),
        selectinload(Correlation.evidence_b),
        selectinload(Correlation.investigation),
    )
    level_rank = sql_case({"high": 0, "medium": 1, "low": 2}, value=Correlation.level)
    return Dashboard(
        metrics=metrics,
        evidence_by_type=grouped(Evidence.evidence_type, Evidence),
        evidence_by_status=grouped(Evidence.status, Evidence),
        correlations_by_level=grouped(
            Correlation.level,
            Correlation,
            Correlation.stale.is_(False),
            Correlation.review_status != "rejected",
        ),
        event_activity=_event_buckets(event_times),
        activity_by_day=_days(since, today, activity_rows),
        recent_investigations=list(
            db.scalars(
                select(Investigation)
                .where(Investigation.id.in_(cases))
                .options(selectinload(Investigation.lead_investigator))
                .order_by(Investigation.updated_at.desc())
                .limit(5)
            )
        ),
        recent_evidence=list(
            db.scalars(
                select(Evidence)
                .where(Evidence.investigation_id.in_(cases))
                .options(selectinload(Evidence.investigation))
                .order_by(Evidence.created_at.desc())
                .limit(6)
            )
        ),
        pending_correlations=list(
            db.scalars(
                select(Correlation)
                .where(
                    Correlation.investigation_id.in_(cases),
                    Correlation.review_status == "pending",
                    Correlation.stale.is_(False),
                )
                .options(*case_options)
                .order_by(level_rank, Correlation.score.desc())
                .limit(5)
            )
        ),
        recent_correlations=list(
            db.scalars(
                select(Correlation)
                .where(Correlation.investigation_id.in_(cases), Correlation.stale.is_(False))
                .options(*case_options)
                .order_by(Correlation.created_at.desc())
                .limit(5)
            )
        ),
        my_tasks=task_service.my_tasks(db, user)[:5],
        alerts=_alerts(db, cases, today),
        activity=list(
            db.scalars(select(AuditLog).where(audit_scope).order_by(AuditLog.id.desc()).limit(10))
        ),
    )


def _event_buckets(times: list[datetime]) -> dict[str, Any]:
    """Events per hour when they span up to 3 days (a single night reads well), else per day."""
    if not times:
        return {"unit": "day", "buckets": []}
    first, last = min(times), max(times)
    unit = "hour" if last - first <= timedelta(days=3) else "day"
    step = timedelta(hours=1) if unit == "hour" else timedelta(days=1)

    def floor(moment: datetime) -> datetime:
        moment = moment.astimezone(UTC)
        if unit == "hour":
            return moment.replace(minute=0, second=0, microsecond=0)
        return moment.replace(hour=0, minute=0, second=0, microsecond=0)

    counts: dict[datetime, int] = {}
    for moment in times:
        counts[floor(moment)] = counts.get(floor(moment), 0) + 1
    start, end = floor(first), floor(last)
    buckets = []
    while start <= end and len(buckets) < 400:
        buckets.append((start.isoformat(), counts.get(start, 0)))
        start += step
    return {"unit": unit, "buckets": buckets[-72:]}


def _days(since: date, today: date, counts: dict[date, int]) -> list[tuple[str, int]]:
    days = (today - since).days + 1
    return [
        ((since + timedelta(d)).isoformat(), counts.get(since + timedelta(d), 0))
        for d in range(days)
    ]


def _alerts(db: Session, cases: Any, today: date) -> list[dict[str, str]]:
    """Things that need attention now — few, specific, each with a link (no overload)."""
    alerts: list[dict[str, str]] = []
    failed = db.scalars(
        select(Evidence)
        .join(ProcessingJob, ProcessingJob.evidence_id == Evidence.id)
        .where(Evidence.investigation_id.in_(cases), ProcessingJob.status == "failed")
        .options(selectinload(Evidence.investigation))
        .distinct()
        .limit(5)
    )
    for e in failed:
        alerts.append(_alert("danger", f"Processing failed for {e.reference}", e))
    mismatched = db.scalars(
        select(Evidence)
        .where(Evidence.investigation_id.in_(cases), Evidence.integrity_ok.is_(False))
        .options(selectinload(Evidence.investigation))
        .limit(5)
    )
    for e in mismatched:
        alerts.append(_alert("danger", f"Integrity check failed for {e.reference}", e))
    overdue = db.scalars(
        select(Task)
        .where(Task.investigation_id.in_(cases), Task.status != "completed", Task.due_date < today)
        .options(selectinload(Task.investigation))
        .order_by(Task.due_date)
        .limit(5)
    )
    for t in overdue:
        alerts.append(
            {
                "tone": "warning",
                "title": f"{t.reference} overdue since {t.due_date.isoformat()}: {t.title}",
                "link": f"/tasks?case={t.investigation.reference}&task={t.reference}",
            }
        )
    return alerts


def _alert(tone: str, title: str, evidence: Evidence) -> dict[str, str]:
    return {
        "tone": tone,
        "title": title,
        "link": f"/investigations/{evidence.investigation.reference}/evidence/{evidence.reference}",
    }
