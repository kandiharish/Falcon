"""/api/investigations/{case}/reports — investigation reports (plan §24)."""

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Report, User
from app.security.dependencies import require_permission
from app.security.permissions import Permission
from app.services import report_service as service
from app.services.request_context import request_context

router = APIRouter(prefix="/investigations/{case_reference}/reports", tags=["reports"])
Reader = Annotated[User, Depends(require_permission(Permission.INVESTIGATION_READ))]
Author = Annotated[User, Depends(require_permission(Permission.REPORT_GENERATE))]
DB = Annotated[Session, Depends(get_db)]


class ReportSummary(BaseModel):
    reference: str
    title: str
    status: Literal["generating", "ready", "failed"]
    generated_by: str
    created_at: datetime
    completed_at: datetime | None
    content_sha256: str | None
    error_message: str | None


class ReportDetail(ReportSummary):
    content: dict[str, Any] | None
    # Recomputed on every read: does the content still match the fingerprint taken at
    # generation time? False would mean someone altered the stored report.
    intact: bool


class ReportIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    analyst_notes: str = Field("", max_length=10000)
    limitations: str = Field("", max_length=5000)
    include_pending: bool = True


def _summary(r: Report) -> dict[str, Any]:
    return {
        "reference": r.reference,
        "title": r.title,
        "status": r.status,
        "generated_by": r.generated_by.display_name,
        "created_at": r.created_at,
        "completed_at": r.completed_at,
        "content_sha256": r.content_sha256,
        "error_message": r.error_message,
    }


def _detail(r: Report) -> ReportDetail:
    return ReportDetail(**_summary(r), content=r.content, intact=service.verify(r))


@router.get("", response_model=list[ReportSummary])
def list_reports(case_reference: str, user: Reader, db: DB) -> list[ReportSummary]:
    return [ReportSummary(**_summary(r)) for r in service.list_reports(db, user, case_reference)]


@router.post("", response_model=ReportDetail, status_code=status.HTTP_201_CREATED)
def generate(
    case_reference: str, body: ReportIn, request: Request, user: Author, db: DB
) -> ReportDetail:
    report = service.generate(
        db,
        user,
        case_reference,
        service.ReportRequest(
            body.title, body.analyst_notes, body.limitations, body.include_pending
        ),
        request_context(request),
    )
    return _detail(report)


@router.get("/{reference}", response_model=ReportDetail)
def get_report(case_reference: str, reference: str, user: Reader, db: DB) -> ReportDetail:
    return _detail(service.get_report(db, user, case_reference, reference))


@router.get("/{reference}/export")
def export(case_reference: str, reference: str, request: Request, user: Reader, db: DB) -> Response:
    """The report as a JSON file: the exact snapshot whose SHA-256 is shown in the report."""
    report = service.get_report(db, user, case_reference, reference)
    service.record_export(db, user, report, request_context(request))
    body = service.canonical(report.content or {})
    filename = f"{case_reference}_{report.reference}.json"
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-SHA256": report.content_sha256 or "",
        },
    )
