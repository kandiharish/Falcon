"""Evidence use cases: upload, list, open, download, verify integrity, review status.

Upload flow:
  check case access → sniff real file type → stream to storage while hashing (SHA-256)
  → reject exact duplicates in the same case → assign IMG-001-style reference
  → create evidence row + queued processing job → audit → commit
  If anything fails after the file was stored, the stored file is removed again.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import BinaryIO

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models import (
    AuditLog,
    Evidence,
    EvidenceReferenceCounter,
    Investigation,
    ProcessingJob,
    User,
)
from app.security.permissions import Permission, Role, permissions_for
from app.services import audit_service, investigation_service
from app.services.errors import (
    ConflictError,
    ForbiddenError,
    InvalidInputError,
    NotFoundError,
    PayloadTooLargeError,
)
from app.services.request_context import RequestContext
from app.storage import file_types
from app.storage import local as storage

REFERENCE_PREFIX = {
    "video": "CCTV",
    "image": "IMG",
    "document": "DOC",
    "gps": "GPS",
    "mobile": "MOB",
    "call_records": "CALL",
    "financial": "TXN",
    "vehicle": "VEH",
    "witness_statement": "WIT",
    "digital_file": "FILE",
    "other": "OTH",
}

# Review decisions an analyst may make once processing has finished.
STATUS_TRANSITIONS: dict[str, set[str]] = {
    "processed": {"verified", "requires_review"},
    "requires_review": {"verified", "processed"},
    "verified": {"requires_review"},
}

NOT_FOUND = "This evidence item does not exist in this investigation."


@dataclass
class EvidenceUpload:
    file: BinaryIO
    filename: str
    evidence_type: str
    source: str = ""
    description: str = ""
    collected_at: datetime | None = None
    location_text: str = ""
    latitude: float | None = None
    longitude: float | None = None
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EvidenceFilters:
    search: str | None = None
    evidence_type: str | None = None
    status: str | None = None


def audit_object_id(evidence: Evidence) -> str:
    return f"{evidence.investigation.reference}/{evidence.reference}"


# ---------- Upload ----------------------------------------------------------------------


def upload(
    db: Session, user: User, case_reference: str, data: EvidenceUpload, context: RequestContext
) -> Evidence:
    investigation = investigation_service.get_investigation(db, user, case_reference)
    _require_team_member(db, user, investigation)
    if investigation.status in ("closed", "archived"):
        raise ConflictError(
            f"The investigation is {investigation.status}; new evidence cannot be added."
        )
    _validate_coordinates(data.latitude, data.longitude)

    filename = (data.filename or "unnamed").replace("\\", "/").rsplit("/", 1)[-1][:255]
    head = data.file.read(8192)
    data.file.seek(0)
    media_type = file_types.detect_media_type(head, filename)
    reason = file_types.rejection_reason(media_type, filename, data.evidence_type)
    if reason:
        raise InvalidInputError(reason)
    if not head:
        raise InvalidInputError("The file is empty.")

    evidence_id = uuid.uuid4()
    key = f"originals/{investigation.id}/{evidence_id}{file_types.safe_extension(filename)}"
    max_mb = get_settings().max_upload_mb
    try:
        stored = storage.save_original(data.file, key, max_mb * 1024 * 1024)
    except storage.FileTooLargeError:
        raise PayloadTooLargeError(f"The file is larger than the {max_mb} MB limit.") from None

    try:
        duplicate = db.scalar(
            select(Evidence).where(
                Evidence.investigation_id == investigation.id, Evidence.sha256 == stored.sha256
            )
        )
        if duplicate:
            raise ConflictError(
                f"This exact file is already in the investigation as {duplicate.reference} "
                "(identical SHA-256 fingerprint). Duplicates are not stored twice."
            )
        evidence = Evidence(
            id=evidence_id,
            investigation_id=investigation.id,
            reference=_next_reference(db, investigation.id, data.evidence_type),
            evidence_type=data.evidence_type,
            status="uploaded",
            source=data.source.strip(),
            description=data.description.strip(),
            collected_at=data.collected_at,
            location_text=data.location_text.strip(),
            latitude=data.latitude,
            longitude=data.longitude,
            tags=investigation_service.clean_tags(data.tags),
            original_filename=filename,
            media_type=media_type,
            size_bytes=stored.size_bytes,
            sha256=stored.sha256,
            storage_key=stored.key,
            uploaded_by_id=user.id,
            file_metadata={},
        )
        evidence.investigation = investigation
        db.add(evidence)
        db.add(ProcessingJob(evidence=evidence, status="queued", current_step="Waiting in queue"))
        db.flush()
        audit_service.record(
            db,
            "evidence.uploaded",
            actor=user,
            object_type="evidence",
            object_id=audit_object_id(evidence),
            new_state={
                "reference": evidence.reference,
                "evidence_type": evidence.evidence_type,
                "original_filename": filename,
                "media_type": media_type,
                "size_bytes": stored.size_bytes,
                "sha256": stored.sha256,
            },
            context=context,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        storage.delete(key)
        raise ConflictError(
            "This exact file was just added to the investigation by someone else."
        ) from None
    except BaseException:
        db.rollback()
        storage.delete(key)
        raise
    return get_evidence(db, user, case_reference, evidence.reference)


def _next_reference(db: Session, investigation_id: uuid.UUID, evidence_type: str) -> str:
    prefix = REFERENCE_PREFIX[evidence_type]
    value = db.execute(
        insert(EvidenceReferenceCounter)
        .values(investigation_id=investigation_id, prefix=prefix, last_value=1)
        .on_conflict_do_update(
            index_elements=[
                EvidenceReferenceCounter.investigation_id,
                EvidenceReferenceCounter.prefix,
            ],
            set_={"last_value": EvidenceReferenceCounter.last_value + 1},
        )
        .returning(EvidenceReferenceCounter.last_value)
    ).scalar_one()
    return f"{prefix}-{value:03d}"


def _validate_coordinates(latitude: float | None, longitude: float | None) -> None:
    if (latitude is None) != (longitude is None):
        raise InvalidInputError("Enter both latitude and longitude, or neither.")
    if latitude is not None and not -90 <= latitude <= 90:
        raise InvalidInputError("Latitude must be between -90 and 90.")
    if longitude is not None and not -180 <= longitude <= 180:
        raise InvalidInputError("Longitude must be between -180 and 180.")


def _require_team_member(db: Session, user: User, investigation: Investigation) -> None:
    if user.role == Role.SUPERVISOR:
        return
    if investigation_service.repo.membership(db, investigation.id, user.id) is None:
        raise ForbiddenError("Only members of the investigation team can add or change evidence.")


# ---------- Read ------------------------------------------------------------------------


def list_evidence(
    db: Session,
    user: User,
    case_reference: str,
    filters: EvidenceFilters,
    limit: int,
    offset: int,
) -> tuple[list[Evidence], int]:
    investigation = investigation_service.get_investigation(db, user, case_reference)
    query = select(Evidence).where(Evidence.investigation_id == investigation.id)
    if filters.evidence_type:
        query = query.where(Evidence.evidence_type == filters.evidence_type)
    if filters.status:
        query = query.where(Evidence.status == filters.status)
    if filters.search:
        term = f"%{filters.search.strip()}%"
        query = query.where(
            or_(
                Evidence.reference.ilike(term),
                Evidence.original_filename.ilike(term),
                Evidence.source.ilike(term),
                Evidence.description.ilike(term),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.options(selectinload(Evidence.jobs), selectinload(Evidence.uploaded_by))
        .order_by(Evidence.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    for row in rows:
        row.investigation = investigation
    return list(rows), total


def get_evidence(db: Session, user: User, case_reference: str, evidence_reference: str) -> Evidence:
    investigation = investigation_service.get_investigation(db, user, case_reference)
    evidence = db.scalar(
        select(Evidence)
        .where(
            Evidence.investigation_id == investigation.id,
            Evidence.reference == evidence_reference.upper(),
        )
        .options(selectinload(Evidence.jobs), selectinload(Evidence.uploaded_by))
        # Refresh objects already in this session (e.g. a job list cached before a reprocess).
        .execution_options(populate_existing=True)
    )
    if evidence is None:
        raise NotFoundError(NOT_FOUND)
    evidence.investigation = investigation
    return evidence


def record_download(db: Session, user: User, evidence: Evidence, context: RequestContext) -> None:
    """Viewing the original is a sensitive action (plan §25: "Evidence viewed")."""
    audit_service.record(
        db,
        "evidence.downloaded",
        actor=user,
        object_type="evidence",
        object_id=audit_object_id(evidence),
        context=context,
    )
    db.commit()


def history(
    db: Session, user: User, case_reference: str, evidence_reference: str
) -> list[AuditLog]:
    evidence = get_evidence(db, user, case_reference, evidence_reference)
    return list(
        db.scalars(
            select(AuditLog)
            .where(
                AuditLog.object_type == "evidence", AuditLog.object_id == audit_object_id(evidence)
            )
            .order_by(AuditLog.id.desc())
            .limit(100)
        )
    )


def counts_by_investigation(
    db: Session, investigation_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    if not investigation_ids:
        return {}
    rows = db.execute(
        select(Evidence.investigation_id, func.count())
        .where(Evidence.investigation_id.in_(investigation_ids))
        .group_by(Evidence.investigation_id)
    ).all()
    return {investigation_id: count for investigation_id, count in rows}


# ---------- Integrity & review ----------------------------------------------------------


def verify_integrity(
    db: Session, user: User, case_reference: str, evidence_reference: str, context: RequestContext
) -> Evidence:
    """Re-read the stored original and compare its fingerprint with the one taken at upload."""
    evidence = get_evidence(db, user, case_reference, evidence_reference)
    try:
        current = storage.sha256_of(evidence.storage_key)
    except FileNotFoundError:
        current = None
    ok = current == evidence.sha256
    evidence.integrity_checked_at = datetime.now(UTC)
    evidence.integrity_ok = ok
    if not ok:
        evidence.status = "requires_review"
    audit_service.record(
        db,
        "evidence.integrity_checked",
        actor=user,
        object_type="evidence",
        object_id=audit_object_id(evidence),
        new_state={
            "result": "match" if ok else "MISMATCH",
            "expected": evidence.sha256,
            "actual": current,
        },
        context=context,
    )
    db.commit()
    return get_evidence(db, user, case_reference, evidence_reference)


def change_status(
    db: Session,
    user: User,
    case_reference: str,
    evidence_reference: str,
    new_status: str,
    note: str | None,
    context: RequestContext,
) -> Evidence:
    if Permission.EVIDENCE_VERIFY not in permissions_for(user.role):
        raise ForbiddenError("Your role cannot verify evidence.")
    evidence = get_evidence(db, user, case_reference, evidence_reference)
    _require_team_member(db, user, evidence.investigation)
    allowed = STATUS_TRANSITIONS.get(evidence.status, set())
    if new_status not in allowed:
        raise ConflictError(
            f"Evidence that is '{evidence.status}' cannot be marked '{new_status}'."
            + (
                " Wait until processing has finished."
                if evidence.status in ("uploaded", "processing")
                else ""
            )
        )
    if new_status == "verified" and evidence.integrity_ok is False:
        raise ConflictError("Evidence whose integrity check failed cannot be verified.")
    previous = evidence.status
    evidence.status = new_status
    audit_service.record(
        db,
        "evidence.status_changed",
        actor=user,
        object_type="evidence",
        object_id=audit_object_id(evidence),
        previous_state={"status": previous},
        new_state={"status": new_status},
        note=note,
        context=context,
    )
    db.commit()
    return get_evidence(db, user, case_reference, evidence_reference)


def reprocess(
    db: Session, user: User, case_reference: str, evidence_reference: str, context: RequestContext
) -> Evidence:
    evidence = get_evidence(db, user, case_reference, evidence_reference)
    _require_team_member(db, user, evidence.investigation)
    latest = evidence.jobs[-1] if evidence.jobs else None
    if latest and latest.status in ("queued", "running"):
        raise ConflictError("This evidence is already waiting for or being processed.")
    db.add(ProcessingJob(evidence_id=evidence.id, status="queued", current_step="Waiting in queue"))
    evidence.status = "uploaded"
    audit_service.record(
        db,
        "evidence.reprocess_requested",
        actor=user,
        object_type="evidence",
        object_id=audit_object_id(evidence),
        context=context,
    )
    db.commit()
    return get_evidence(db, user, case_reference, evidence_reference)
