"""/api/dashboard (plan §9) and /api/search (plan §28) — across the cases you can see."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.schemas import AuditEntry, audit_entry
from app.api.work import TaskOut, task_out
from app.db.session import get_db
from app.models import Correlation, User
from app.security.dependencies import require_permission
from app.security.permissions import Permission
from app.services import dashboard_service, search_service

router = APIRouter(tags=["overview"])
Reader = Annotated[User, Depends(require_permission(Permission.INVESTIGATION_READ))]
DB = Annotated[Session, Depends(get_db)]


class CaseBrief(BaseModel):
    reference: str
    title: str
    status: str
    priority: str
    stage: str
    lead: str
    updated_at: datetime


class EvidenceBrief(BaseModel):
    reference: str
    investigation_reference: str
    evidence_type: str
    description: str
    status: str
    created_at: datetime


class CorrelationBrief(BaseModel):
    reference: str
    investigation_reference: str
    evidence_a: str
    evidence_b: str
    level: str
    score: float
    review_status: str
    created_at: datetime


class Alert(BaseModel):
    tone: str
    title: str
    link: str


class Bucket(BaseModel):
    start: str
    count: int


class EventActivity(BaseModel):
    unit: str
    buckets: list[Bucket]


class DashboardOut(BaseModel):
    metrics: dict[str, int]
    evidence_by_type: dict[str, int]
    evidence_by_status: dict[str, int]
    correlations_by_level: dict[str, int]
    event_activity: EventActivity
    activity_by_day: list[Bucket]
    recent_investigations: list[CaseBrief]
    recent_evidence: list[EvidenceBrief]
    pending_correlations: list[CorrelationBrief]
    recent_correlations: list[CorrelationBrief]
    my_tasks: list[TaskOut]
    alerts: list[Alert]
    activity: list[AuditEntry]


class SearchHit(BaseModel):
    kind: str
    reference: str
    title: str
    subtitle: str
    investigation_reference: str
    link: str


def _correlation(c: Correlation) -> CorrelationBrief:
    return CorrelationBrief(
        reference=c.reference,
        investigation_reference=c.investigation.reference,
        evidence_a=c.evidence_a.reference,
        evidence_b=c.evidence_b.reference,
        level=c.level,
        score=c.score,
        review_status=c.review_status,
        created_at=c.created_at,
    )


def _buckets(pairs: list[tuple[str, int]]) -> list[Bucket]:
    return [Bucket(start=start, count=count) for start, count in pairs]


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(user: Reader, db: DB) -> DashboardOut:
    d = dashboard_service.build(db, user)
    activity: dict[str, Any] = d.event_activity
    return DashboardOut(
        metrics=d.metrics,
        evidence_by_type=d.evidence_by_type,
        evidence_by_status=d.evidence_by_status,
        correlations_by_level=d.correlations_by_level,
        event_activity=EventActivity(unit=activity["unit"], buckets=_buckets(activity["buckets"])),
        activity_by_day=_buckets(d.activity_by_day),
        recent_investigations=[
            CaseBrief(
                reference=i.reference,
                title=i.title,
                status=i.status,
                priority=i.priority,
                stage=i.stage,
                lead=i.lead_investigator.display_name,
                updated_at=i.updated_at,
            )
            for i in d.recent_investigations
        ],
        recent_evidence=[
            EvidenceBrief(
                reference=e.reference,
                investigation_reference=e.investigation.reference,
                evidence_type=e.evidence_type,
                description=e.description or e.original_filename,
                status=e.status,
                created_at=e.created_at,
            )
            for e in d.recent_evidence
        ],
        pending_correlations=[_correlation(c) for c in d.pending_correlations],
        recent_correlations=[_correlation(c) for c in d.recent_correlations],
        my_tasks=[task_out(t) for t in d.my_tasks],
        alerts=[Alert(**a) for a in d.alerts],
        activity=[audit_entry(a) for a in d.activity],
    )


@router.get("/search", response_model=list[SearchHit])
def search(
    user: Reader, db: DB, q: Annotated[str, Query(min_length=1, max_length=100)]
) -> list[SearchHit]:
    return [SearchHit(**hit.__dict__) for hit in search_service.search(db, user, q)]
