"""/api/investigations/{case}/evidence — evidence management (plan §11, §12, §13, §27)."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.schemas import AuditEntry, audit_entry
from app.db.session import get_db
from app.models import Evidence, ProcessingJob, User
from app.security.dependencies import require_permission
from app.security.permissions import Permission
from app.security.rate_limit import limit
from app.services import evidence_service as service
from app.services.errors import NotFoundError
from app.services.request_context import request_context
from app.storage import local as storage

router = APIRouter(prefix="/investigations/{case_reference}/evidence", tags=["evidence"])

EvidenceType = Literal[
    "video",
    "image",
    "document",
    "gps",
    "mobile",
    "call_records",
    "financial",
    "vehicle",
    "witness_statement",
    "digital_file",
    "other",
]
EvidenceStatus = Literal[
    "uploaded", "processing", "processed", "verified", "requires_review", "archived"
]

Reader = Annotated[User, Depends(require_permission(Permission.EVIDENCE_READ))]
Uploader = Annotated[User, Depends(require_permission(Permission.EVIDENCE_UPLOAD))]
Verifier = Annotated[User, Depends(require_permission(Permission.EVIDENCE_VERIFY))]
DB = Annotated[Session, Depends(get_db)]


# ---------- Shapes ----------------------------------------------------------------------


class JobStep(BaseModel):
    name: str
    label: str
    status: str
    summary: str
    duration_ms: int


class JobOut(BaseModel):
    id: uuid.UUID
    status: Literal["queued", "running", "succeeded", "failed"]
    progress: int
    current_step: str | None
    steps: list[JobStep]
    attempts: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class EvidenceOut(BaseModel):
    reference: str
    investigation_reference: str
    evidence_type: EvidenceType
    status: EvidenceStatus
    source: str
    description: str
    collected_at: datetime | None
    location_text: str
    latitude: float | None
    longitude: float | None
    tags: list[str]
    original_filename: str
    media_type: str
    size_bytes: int
    sha256: str
    integrity_checked_at: datetime | None
    integrity_ok: bool | None
    has_preview: bool
    file_metadata: dict[str, Any]
    uploaded_by: str
    created_at: datetime
    latest_job: JobOut | None


class EvidencePage(BaseModel):
    items: list[EvidenceOut]
    total: int
    limit: int
    offset: int


class StatusChange(BaseModel):
    status: Literal["processed", "verified", "requires_review"]
    note: str | None = Field(default=None, max_length=1000)


def _job(job: ProcessingJob | None) -> JobOut | None:
    if job is None:
        return None
    return JobOut(
        id=job.id,
        status=job.status,  # type: ignore[arg-type]
        progress=job.progress,
        current_step=job.current_step,
        steps=[JobStep(**step) for step in job.steps or []],
        attempts=job.attempts,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def _out(e: Evidence) -> EvidenceOut:
    return EvidenceOut(
        reference=e.reference,
        investigation_reference=e.investigation.reference,
        evidence_type=e.evidence_type,  # type: ignore[arg-type]
        status=e.status,  # type: ignore[arg-type]
        source=e.source,
        description=e.description,
        collected_at=e.collected_at,
        location_text=e.location_text,
        latitude=e.latitude,
        longitude=e.longitude,
        tags=e.tags,
        original_filename=e.original_filename,
        media_type=e.media_type,
        size_bytes=e.size_bytes,
        sha256=e.sha256,
        integrity_checked_at=e.integrity_checked_at,
        integrity_ok=e.integrity_ok,
        has_preview=e.preview_key is not None,
        file_metadata=e.file_metadata or {},
        uploaded_by=e.uploaded_by.display_name,
        created_at=e.created_at,
        latest_job=_job(e.jobs[-1] if e.jobs else None),
    )


# ---------- Routes ----------------------------------------------------------------------


@router.get("", response_model=EvidencePage)
def list_evidence(
    case_reference: str,
    user: Reader,
    db: DB,
    search: Annotated[str | None, Query(max_length=100)] = None,
    evidence_type: EvidenceType | None = None,
    status_filter: Annotated[EvidenceStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EvidencePage:
    filters = service.EvidenceFilters(
        search=search or None, evidence_type=evidence_type, status=status_filter
    )
    items, total = service.list_evidence(db, user, case_reference, filters, limit, offset)
    return EvidencePage(items=[_out(e) for e in items], total=total, limit=limit, offset=offset)


@router.post(
    "",
    response_model=EvidenceOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit("upload", 30, by="user"))],
)
def upload_evidence(
    case_reference: str,
    request: Request,
    user: Uploader,
    db: DB,
    file: Annotated[UploadFile, File(description="The evidence file")],
    evidence_type: Annotated[EvidenceType, Form()],
    source: Annotated[str, Form(max_length=200)] = "",
    description: Annotated[str, Form(max_length=5000)] = "",
    collected_at: Annotated[datetime | None, Form()] = None,
    location_text: Annotated[str, Form(max_length=200)] = "",
    latitude: Annotated[float | None, Form()] = None,
    longitude: Annotated[float | None, Form()] = None,
    tags: Annotated[str, Form(max_length=400, description="Comma-separated")] = "",
) -> EvidenceOut:
    upload = service.EvidenceUpload(
        file=file.file,
        filename=file.filename or "unnamed",
        evidence_type=evidence_type,
        source=source,
        description=description,
        collected_at=collected_at,
        location_text=location_text,
        latitude=latitude,
        longitude=longitude,
        tags=[t for t in tags.split(",") if t.strip()],
    )
    evidence = service.upload(db, user, case_reference, upload, request_context(request))
    return _out(evidence)


@router.get("/{evidence_reference}", response_model=EvidenceOut)
def get_evidence(case_reference: str, evidence_reference: str, user: Reader, db: DB) -> EvidenceOut:
    return _out(service.get_evidence(db, user, case_reference, evidence_reference))


@router.get("/{evidence_reference}/content")
def download_original(
    case_reference: str, evidence_reference: str, request: Request, user: Reader, db: DB
) -> StreamingResponse:
    """The original file, always as a download (never rendered by the browser)."""
    evidence = service.get_evidence(db, user, case_reference, evidence_reference)
    service.record_download(db, user, evidence, request_context(request))
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in evidence.original_filename)
    return StreamingResponse(
        storage.iter_file(evidence.storage_key),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{evidence.reference}_{safe_name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.get("/{evidence_reference}/preview")
def preview(case_reference: str, evidence_reference: str, user: Reader, db: DB) -> FileResponse:
    """A derived JPEG preview (images only). The original is never served inline."""
    evidence = service.get_evidence(db, user, case_reference, evidence_reference)
    if not evidence.preview_key or not storage.exists(evidence.preview_key):
        raise NotFoundError("No preview is available for this evidence item.")
    return FileResponse(
        storage.path_of(evidence.preview_key),
        media_type="image/jpeg",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=300"},
    )


@router.post("/{evidence_reference}/verify-integrity", response_model=EvidenceOut)
def verify_integrity(
    case_reference: str, evidence_reference: str, request: Request, user: Reader, db: DB
) -> EvidenceOut:
    return _out(
        service.verify_integrity(
            db, user, case_reference, evidence_reference, request_context(request)
        )
    )


@router.post("/{evidence_reference}/status", response_model=EvidenceOut)
def change_status(
    case_reference: str,
    evidence_reference: str,
    body: StatusChange,
    request: Request,
    user: Verifier,
    db: DB,
) -> EvidenceOut:
    return _out(
        service.change_status(
            db,
            user,
            case_reference,
            evidence_reference,
            body.status,
            body.note,
            request_context(request),
        )
    )


@router.post("/{evidence_reference}/reprocess", response_model=EvidenceOut)
def reprocess(
    case_reference: str, evidence_reference: str, request: Request, user: Uploader, db: DB
) -> EvidenceOut:
    return _out(
        service.reprocess(db, user, case_reference, evidence_reference, request_context(request))
    )


@router.get("/{evidence_reference}/history", response_model=list[AuditEntry])
def evidence_history(
    case_reference: str, evidence_reference: str, user: Reader, db: DB
) -> list[AuditEntry]:
    return [audit_entry(r) for r in service.history(db, user, case_reference, evidence_reference)]
