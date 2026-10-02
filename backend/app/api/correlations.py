"""/api/investigations/{case}/correlations — potential relationships (plan §18–§19)."""

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.extraction import EventOut, event_out
from app.db.session import get_db
from app.models import Correlation, Evidence, User
from app.security.dependencies import require_permission
from app.security.permissions import Permission
from app.services import correlation_service as service
from app.services.request_context import request_context

router = APIRouter(prefix="/investigations/{case_reference}/correlations", tags=["correlations"])

Level = Literal["high", "medium", "low"]
ReviewStatus = Literal["pending", "confirmed", "rejected"]

Reader = Annotated[User, Depends(require_permission(Permission.EVIDENCE_READ))]
Reviewer = Annotated[User, Depends(require_permission(Permission.CORRELATION_REVIEW))]
DB = Annotated[Session, Depends(get_db)]


class EvidenceRef(BaseModel):
    reference: str
    evidence_type: str
    description: str


class FactorOut(BaseModel):
    kind: Literal["entity", "time", "location"]
    score: float
    weight: float
    contribution: float
    explanation: str
    details: dict[str, Any]


class CorrelationOut(BaseModel):
    reference: str
    evidence_a: EvidenceRef
    evidence_b: EvidenceRef
    score: float
    level: Level
    factors: list[FactorOut]
    algorithm: str
    stale: bool
    review_status: ReviewStatus
    review_note: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CorrelationDetail(CorrelationOut):
    supporting_events: list[EventOut]


class CorrelationPage(BaseModel):
    items: list[CorrelationOut]
    total: int


class RunResult(BaseModel):
    created: int
    updated: int
    removed: int
    stale: int
    total: int


class Review(BaseModel):
    review_status: ReviewStatus
    note: str | None = Field(default=None, max_length=1000)


def _evidence(e: Evidence) -> EvidenceRef:
    return EvidenceRef(
        reference=e.reference,
        evidence_type=e.evidence_type,
        description=e.description or e.original_filename,
    )


def _out(c: Correlation) -> dict[str, Any]:
    return {
        "reference": c.reference,
        "evidence_a": _evidence(c.evidence_a),
        "evidence_b": _evidence(c.evidence_b),
        "score": c.score,
        "level": c.level,
        "factors": c.factors,
        "algorithm": c.algorithm,
        "stale": c.stale,
        "review_status": c.review_status,
        "review_note": c.review_note,
        "reviewed_by": c.reviewed_by.display_name if c.reviewed_by else None,
        "reviewed_at": c.reviewed_at,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


def _detail(db: Session, c: Correlation) -> CorrelationDetail:
    return CorrelationDetail(
        **_out(c), supporting_events=[event_out(e) for e in service.supporting_events(db, c)]
    )


@router.post("/run", response_model=RunResult)
def run(case_reference: str, request: Request, user: Reviewer, db: DB) -> RunResult:
    summary = service.run(db, user, case_reference, request_context(request))
    return RunResult(**summary.__dict__)


@router.get("", response_model=CorrelationPage)
def list_correlations(
    case_reference: str,
    user: Reader,
    db: DB,
    level: Level | None = None,
    review_status: ReviewStatus | None = None,
    evidence: Annotated[str | None, Query(max_length=20)] = None,
    include_stale: bool = True,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CorrelationPage:
    filters = service.CorrelationFilters(level, review_status, evidence, include_stale)
    rows, total = service.list_correlations(db, user, case_reference, filters, limit, offset)
    return CorrelationPage(items=[CorrelationOut(**_out(c)) for c in rows], total=total)


@router.get("/{reference}", response_model=CorrelationDetail)
def get_correlation(case_reference: str, reference: str, user: Reader, db: DB) -> CorrelationDetail:
    return _detail(db, service.get_correlation(db, user, case_reference, reference))


@router.post("/{reference}/review", response_model=CorrelationDetail)
def review(
    case_reference: str, reference: str, body: Review, request: Request, user: Reviewer, db: DB
) -> CorrelationDetail:
    correlation = service.review(
        db,
        user,
        case_reference,
        reference,
        body.review_status,
        body.note,
        request_context(request),
    )
    return _detail(db, correlation)
