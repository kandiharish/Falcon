"""Court-ready outputs: Section 63 certificates, requisition letters and the court bundle.

Drafting a document and exporting a bundle are recorded in the audit log: who produced which
paper about which evidence, and when. The bundle re-hashes every original as it is packed, so
it can never claim a fingerprint the stored file no longer has.
"""

import csv
import hashlib
import io
import tempfile
import zipfile
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.documents import certificate, letters
from app.documents.draft import DraftDocument, to_html
from app.models import (
    AuditLog,
    Correlation,
    Entity,
    Event,
    EventParticipant,
    Evidence,
    Investigation,
    User,
)
from app.security.permissions import Permission, permissions_for
from app.services import audit_service, evidence_service, investigation_service
from app.services.errors import ForbiddenError, InvalidInputError, NotFoundError
from app.services.request_context import RequestContext
from app.storage import local as storage

CUSTODY_WORDS = {
    "evidence.uploaded": "received, fingerprinted (SHA-256) and stored read-only",
    "evidence.processed": "processed (original unchanged)",
    "evidence.integrity_checked": "integrity re-checked against the fingerprint",
    "evidence.verified": "marked verified",
    "evidence.viewed": "original viewed",
    "evidence.downloaded": "original downloaded",
    "evidence.reprocessed": "re-processing requested",
    "document.drafted": "certificate or letter drafted",
    "bundle.exported": "included in a court bundle",
}


# ---------- Section 63 certificate ----------------------------------------------------------


def certificate_for(
    db: Session, user: User, case_reference: str, evidence_reference: str, context: RequestContext
) -> DraftDocument:
    evidence = evidence_service.get_evidence(db, user, case_reference, evidence_reference)
    case = evidence.investigation
    _require_team(db, user, case)
    doc = certificate.section_63(_record_facts(db, evidence))
    _audited(
        db, user, "section_63_certificate", evidence_service.audit_object_id(evidence), context
    )
    return doc


def _record_facts(db: Session, evidence: Evidence) -> certificate.RecordFacts:
    case = evidence.investigation
    exif = (evidence.file_metadata.get("image") or {}).get("exif") or {}
    make_model = " ".join(v for v in (exif.get("Make"), exif.get("Model")) if v)
    history = db.scalars(
        select(AuditLog)
        .where(
            AuditLog.object_type == "evidence",
            AuditLog.object_id == evidence_service.audit_object_id(evidence),
        )
        .order_by(AuditLog.id)
        .limit(50)
    ).all()
    return certificate.RecordFacts(
        case_reference=case.reference,
        case_title=case.title,
        time_zone=case.time_zone,
        evidence_reference=evidence.reference,
        evidence_type=evidence.evidence_type,
        description=evidence.description,
        source=evidence.source,
        original_filename=evidence.original_filename,
        media_type=evidence.media_type,
        size_bytes=evidence.size_bytes,
        sha256=evidence.sha256,
        collected_at=evidence.collected_at,
        uploaded_at=evidence.created_at,
        uploaded_by=evidence.uploaded_by.display_name,
        integrity_checked_at=evidence.integrity_checked_at,
        integrity_ok=evidence.integrity_ok,
        make_model=make_model,
        custody=[
            (h.occurred_at, h.actor_email or "system", CUSTODY_WORDS.get(h.action, h.action))
            for h in history
        ],
    )


# ---------- Requisition letters -------------------------------------------------------------


def letter_for(
    db: Session,
    user: User,
    case_reference: str,
    kind: str,
    entity_reference: str,
    context: RequestContext,
    window: tuple[datetime, datetime] | None = None,
    places: tuple[str, ...] = (),
) -> DraftDocument:
    if kind not in letters.LETTER_KINDS:
        raise InvalidInputError(
            f"Unknown letter kind. Use one of: {', '.join(letters.LETTER_KINDS)}."
        )
    case = investigation_service.get_investigation(db, user, case_reference)
    _require_team(db, user, case)
    entity = db.scalar(
        select(Entity).where(
            Entity.investigation_id == case.id, Entity.reference == entity_reference.upper()
        )
    )
    if entity is None:
        raise NotFoundError("Entity not found in this investigation.")
    if window is None:
        times = db.scalars(
            select(Event.occurred_at)
            .join(EventParticipant, EventParticipant.event_id == Event.id)
            .where(EventParticipant.entity_id == entity.id, Event.occurred_at.is_not(None))
        ).all()
        window = (min(times), max(times)) if times else (None, None)
    lead = db.get(User, case.lead_investigator_id)
    doc = letters.requisition(
        letters.LetterFacts(
            kind=kind,
            case_reference=case.reference,
            case_title=case.title,
            case_type=case.case_type,
            case_location=case.location,
            time_zone=case.time_zone,
            officer=lead.display_name if lead else user.display_name,
            entity_reference=entity.reference,
            entity_label=entity.label,
            first_seen=window[0],
            last_seen=window[1],
            places=places,
            today=datetime.now(UTC),
        )
    )
    _audited(db, user, kind, f"{case.reference}/{entity.reference}", context)
    return doc


# ---------- Court bundle --------------------------------------------------------------------


def court_bundle(
    db: Session, user: User, case_reference: str, context: RequestContext
) -> tuple[tempfile.SpooledTemporaryFile, str]:
    """A ZIP a prosecutor or defence expert can check without FALCON (see README.txt inside)."""
    case = investigation_service.get_investigation(db, user, case_reference)
    if Permission.REPORT_GENERATE not in permissions_for(user.role):
        raise ForbiddenError("Your role cannot export court bundles.")
    _require_team(db, user, case)
    zone = ZoneInfo(case.time_zone)
    items = db.scalars(
        select(Evidence)
        .where(Evidence.investigation_id == case.id)
        .options(selectinload(Evidence.uploaded_by))
        .order_by(Evidence.reference)
    ).all()

    out = tempfile.SpooledTemporaryFile(max_size=50 * 1024 * 1024)
    manifest = [
        [
            "reference",
            "type",
            "description",
            "file",
            "bytes",
            "sha256",
            "matches_at_export",
            "collected",
            "received",
            "received_by",
        ]
    ]
    sums, mismatched = [], []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for e in items:
            e.investigation = case
            name = f"originals/{e.reference}_{_safe(e.original_filename)}"
            digest = hashlib.sha256()
            with z.open(name, "w") as target:
                for chunk in storage.iter_file(e.storage_key):
                    digest.update(chunk)
                    target.write(chunk)
            ok = digest.hexdigest() == e.sha256
            if not ok:
                mismatched.append(e.reference)
            sums.append(f"{e.sha256}  {name}")
            manifest.append(
                [
                    e.reference,
                    e.evidence_type,
                    e.description,
                    name,
                    e.size_bytes,
                    e.sha256,
                    "yes" if ok else "NO",
                    _local(e.collected_at, zone),
                    _local(e.created_at, zone),
                    e.uploaded_by.display_name,
                ]
            )
            doc = certificate.section_63(_record_facts(db, e))
            z.writestr(f"certificates/{e.reference}_section63_DRAFT.html", to_html(doc))
        z.writestr("manifest.csv", _csv(manifest))
        z.writestr("SHA256SUMS.txt", "\n".join(sums) + "\n")
        z.writestr("timeline.csv", _timeline_csv(db, case, zone))
        z.writestr("correlations.csv", _correlations_csv(db, case))
        z.writestr("audit_trail.csv", _audit_csv(db, case, zone))
        z.writestr("README.txt", _readme(case, user, len(items), mismatched, zone))
    out.seek(0)
    bundle_hash = hashlib.sha256()
    for chunk in iter(lambda: out.read(1024 * 1024), b""):
        bundle_hash.update(chunk)
    out.seek(0)
    audit_service.record(
        db,
        "bundle.exported",
        actor=user,
        object_type="investigation",
        object_id=case.reference,
        new_state={
            "evidence_items": len(items),
            "mismatched": mismatched,
            "bundle_sha256": bundle_hash.hexdigest(),
        },
        context=context,
    )
    db.commit()
    stamp = datetime.now(zone).strftime("%Y%m%d-%H%M")
    return out, f"{case.reference}_court_bundle_{stamp}.zip"


def _timeline_csv(db: Session, case: Investigation, zone: ZoneInfo) -> str:
    events = db.scalars(
        select(Event)
        .where(Event.investigation_id == case.id, Event.review_status != "rejected")
        .options(selectinload(Event.evidence))
        .order_by(Event.occurred_at.nulls_last(), Event.reference)
    ).all()
    rows = [
        [
            "event",
            f"time ({case.time_zone})",
            "type",
            "description",
            "evidence",
            "place",
            "latitude",
            "longitude",
            "how_known",
            "confidence",
            "review",
        ]
    ]
    rows += [
        [
            ev.reference,
            _local(ev.occurred_at, zone, seconds=True),
            ev.event_type,
            ev.description,
            ev.evidence.reference,
            ev.location_text,
            ev.latitude,
            ev.longitude,
            ev.assertion_kind,
            ev.confidence,
            ev.review_status,
        ]
        for ev in events
    ]
    return _csv(rows)


def _correlations_csv(db: Session, case: Investigation) -> str:
    found = db.scalars(
        select(Correlation)
        .where(Correlation.investigation_id == case.id, Correlation.stale.is_(False))
        .options(selectinload(Correlation.evidence_a), selectinload(Correlation.evidence_b))
        .order_by(Correlation.reference)
    ).all()
    rows = [["correlation", "evidence_a", "evidence_b", "level", "score", "review", "why"]]
    rows += [
        [
            c.reference,
            c.evidence_a.reference,
            c.evidence_b.reference,
            c.level,
            f"{c.score:.2f}",
            c.review_status,
            " | ".join(f["explanation"] for f in c.factors),
        ]
        for c in found
    ]
    return _csv(rows)


def _audit_csv(db: Session, case: Investigation, zone: ZoneInfo) -> str:
    entries = db.scalars(
        select(AuditLog)
        .where(
            or_(
                AuditLog.object_id == case.reference, AuditLog.object_id.like(f"{case.reference}/%")
            )
        )
        .order_by(AuditLog.id)
    ).all()
    rows = [["id", "time", "who", "action", "object", "note"]]
    rows += [
        [
            a.id,
            _local(a.occurred_at, zone, seconds=True),
            a.actor_email,
            a.action,
            a.object_id,
            a.note or "",
        ]
        for a in entries
    ]
    return _csv(rows)


def _readme(case, user, count, mismatched, zone) -> str:
    check = (
        "ALL originals matched their fingerprints when this bundle was made."
        if not mismatched
        else f"WARNING: {', '.join(mismatched)} did NOT match the fingerprint taken at receipt."
    )
    return f"""COURT BUNDLE: {case.reference} {case.title}
Exported {datetime.now(zone):%d/%m/%Y %H:%M} ({case.time_zone}) by {user.display_name} using FALCON.

{check}

Contents
  originals/        the {count} evidence files exactly as received (never modified)
  SHA256SUMS.txt    the SHA-256 fingerprint of every original, taken when it was received
  manifest.csv      what each file is, who received it and when
  certificates/     DRAFT Section 63 (Bharatiya Sakshya Adhiniyam, 2023) certificates, to be
                    completed and signed by the producing officer and the expert
  timeline.csv      every event, in time order, with its source and how it is known
  correlations.csv  potential relationships with the reasons for each (not conclusions)
  audit_trail.csv   every recorded action on this investigation

Check the originals yourself, without FALCON
  Linux / macOS:  sha256sum -c SHA256SUMS.txt
  Windows:        certutil -hashfile originals\\<file> SHA256   (compare with SHA256SUMS.txt)

Correlations are leads produced by fixed rules. They are not findings of fact.
"""


# ---------- Helpers -------------------------------------------------------------------------


def _require_team(db: Session, user: User, case: Investigation) -> None:
    if not investigation_service.sees_all(user) and (
        investigation_service.repo.membership(db, case.id, user.id) is None
    ):
        raise ForbiddenError("Only members of the investigation team can produce its documents.")


def _audited(db: Session, user: User, kind: str, object_id: str, context) -> None:
    audit_service.record(
        db,
        "document.drafted",
        actor=user,
        object_type="document",
        object_id=object_id,
        new_state={"kind": kind},
        context=context,
    )
    db.commit()


def _local(moment, zone: ZoneInfo, seconds: bool = False) -> str:
    if moment is None:
        return ""
    return moment.astimezone(zone).strftime("%d/%m/%Y %H:%M:%S" if seconds else "%d/%m/%Y %H:%M")


def _safe(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name)[:120]


def _csv(rows) -> str:
    buffer = io.StringIO()
    csv.writer(buffer).writerows(rows)
    return buffer.getvalue()
