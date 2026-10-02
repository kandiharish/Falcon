"""Evidence tests: upload, integrity, duplicates, file-type checks, permissions, processing."""

import hashlib
import io
import os
import stat
import threading
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from PIL.TiffImagePlugin import IFDRational
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AuditLog, Evidence, ProcessingJob
from app.storage import local as storage
from app.worker import claim_next_job, process_job_by_id, requeue_stale_jobs
from tests.test_investigations import create_case, signed_in

CALLS_CSV = (
    b"caller,callee,started_at,duration_s\n"
    b"+15550100001,+15550100002,2026-09-28T20:33:00,95\n"
    b"+15550100002,+15550100003,2026-09-28T21:02:00,40\n"
)


def jpeg_with_exif(color: str = "navy", utc_offset: str | None = "+05:30") -> bytes:
    image = Image.new("RGB", (64, 48), color)
    exif = Image.Exif()
    exif[0x010F] = "FictionalCam"
    exif.get_ifd(0x8769)[0x9003] = "2026:09:28 20:30:00"  # camera clock (local time)
    if utc_offset:
        exif.get_ifd(0x8769)[0x9011] = utc_offset  # OffsetTimeOriginal
    r = IFDRational
    exif[0x8825] = {1: "N", 2: (r(17), r(23), r(6)), 3: "E", 4: (r(78), r(29), r(1212, 100))}
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", exif=exif)
    return buffer.getvalue()


def upload(client: TestClient, case: str, data: bytes, name: str, evidence_type: str, **fields):
    return client.post(
        f"/api/investigations/{case}/evidence",
        files={"file": (name, data)},
        data={"evidence_type": evidence_type, **fields},
    )


def process_latest_job(case: str, reference: str) -> None:
    with SessionLocal() as db:
        job_id = db.scalar(
            select(ProcessingJob.id)
            .join(Evidence)
            .where(Evidence.reference == reference, ProcessingJob.status == "queued")
            .where(Evidence.investigation.has(reference=case))
        )
    process_job_by_id(job_id)


@pytest.fixture
def team(make_user):
    """An officer (lead) with an analyst on the team, and a fresh case."""
    officer_user = make_user("investigation_officer")
    analyst_user = make_user("forensic_analyst")
    officer = signed_in(officer_user)
    case = create_case(officer)["reference"]
    officer.post(f"/api/investigations/{case}/members", json={"email": analyst_user.email})
    return {"officer": officer, "analyst": signed_in(analyst_user), "case": case}


def test_upload_fingerprints_stores_read_only_and_queues_processing(team):
    data = jpeg_with_exif()
    response = upload(team["officer"], team["case"], data, "scene.JPG", "image", source="Camera 3")
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["reference"] == "IMG-001"
    assert body["sha256"] == hashlib.sha256(data).hexdigest()
    assert body["size_bytes"] == len(data)
    assert body["media_type"] == "image/jpeg"
    assert body["status"] == "uploaded"
    assert body["latest_job"]["status"] == "queued"

    with SessionLocal() as db:
        evidence = db.scalar(
            select(Evidence).where(
                Evidence.sha256 == body["sha256"],
                Evidence.investigation.has(reference=team["case"]),
            )
        )
        path = storage.path_of(evidence.storage_key)
    assert path.read_bytes() == data
    assert not os.access(path, os.W_OK)  # original is read-only
    assert "scene" not in path.name  # stored under our ID, not the uploader's file name


def test_processing_extracts_exif_without_overwriting_user_values(team):
    case = team["case"]
    upload(team["officer"], case, jpeg_with_exif(), "scene.jpg", "image")
    process_latest_job(case, "IMG-001")

    body = team["officer"].get(f"/api/investigations/{case}/evidence/IMG-001").json()
    assert body["status"] == "processed"
    assert body["latitude"] == pytest.approx(17.385)
    assert body["longitude"] == pytest.approx(78.4867)
    # 20:30 local at +05:30 is 15:00 UTC
    assert body["collected_at"].startswith("2026-09-28T15:00:00")
    assert body["file_metadata"]["image"]["provenance"]["latitude"].startswith("extracted")
    assert body["integrity_ok"] is True
    steps = [s["name"] for s in body["latest_job"]["steps"]]
    assert steps == ["integrity", "image_metadata", "image_preview"]
    assert body["latest_job"]["progress"] == 100

    preview = team["officer"].get(f"/api/investigations/{case}/evidence/IMG-001/preview")
    assert preview.status_code == 200 and preview.headers["content-type"] == "image/jpeg"

    # A user-entered location is never replaced by EXIF.
    upload(
        team["officer"],
        case,
        jpeg_with_exif("teal"),
        "b.jpg",
        "image",
        latitude="10",
        longitude="20",
    )
    process_latest_job(case, "IMG-002")
    second = team["officer"].get(f"/api/investigations/{case}/evidence/IMG-002").json()
    assert (second["latitude"], second["longitude"]) == (10, 20)


def test_photo_time_without_zone_is_flagged_for_review(team):
    case = team["case"]
    upload(team["officer"], case, jpeg_with_exif(utc_offset=None), "old_phone.jpg", "image")
    process_latest_job(case, "IMG-001")
    body = team["officer"].get(f"/api/investigations/{case}/evidence/IMG-001").json()
    assert body["status"] == "requires_review"
    assert "no time zone" in body["latest_job"]["error_message"]
    assert "not recorded" in body["file_metadata"]["image"]["provenance"]["collected_at"]


def test_csv_processing_reads_columns_and_rows(team):
    case = team["case"]
    response = upload(team["analyst"], case, CALLS_CSV, "calls.csv", "call_records")
    assert response.json()["reference"] == "CALL-001"
    process_latest_job(case, "CALL-001")
    meta = (
        team["analyst"].get(f"/api/investigations/{case}/evidence/CALL-001").json()["file_metadata"]
    )
    assert meta["text"]["columns"] == ["caller", "callee", "started_at", "duration_s"]
    assert meta["text"]["row_count"] == 2


def test_exact_duplicates_are_rejected_with_the_existing_reference(team):
    case = team["case"]
    upload(team["officer"], case, CALLS_CSV, "calls.csv", "call_records")
    again = upload(team["officer"], case, CALLS_CSV, "renamed.csv", "call_records")
    assert again.status_code == 409
    assert "CALL-001" in again.json()["detail"]


@pytest.mark.parametrize(
    ("data", "name", "evidence_type"),
    [
        (CALLS_CSV, "calls.csv", "image"),  # content does not match the declared type
        (b"MZ\x90\x00" + bytes(200), "tool.exe", "digital_file"),  # a Windows program
        (b"echo hi", "script.ps1", "other"),  # a script
        (b"", "empty.txt", "document"),  # nothing in it
    ],
)
def test_unsafe_or_mismatched_files_are_rejected(team, data, name, evidence_type):
    response = upload(team["officer"], team["case"], data, name, evidence_type)
    assert response.status_code == 422, response.text


def test_files_over_the_size_limit_are_rejected(team, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    big = b"a,b\n" + b"1,2\n" * 300_000  # ~1.2 MB of text
    response = upload(team["officer"], team["case"], big, "big.csv", "financial")
    assert response.status_code == 413


def test_path_traversal_file_names_are_neutralised(team):
    response = upload(team["officer"], team["case"], CALLS_CSV, "..\\..\\evil.csv", "financial")
    assert response.status_code == 201
    assert response.json()["original_filename"] == "evil.csv"


def test_download_returns_the_exact_original_and_is_audited(team):
    data = jpeg_with_exif()
    case = team["case"]
    upload(team["officer"], case, data, "scene.jpg", "image")
    response = team["analyst"].get(f"/api/investigations/{case}/evidence/IMG-001/content")
    assert response.status_code == 200
    assert response.content == data
    assert response.headers["content-disposition"].startswith("attachment;")
    history = team["analyst"].get(f"/api/investigations/{case}/evidence/IMG-001/history").json()
    assert [h["action"] for h in history][:2] == ["evidence.downloaded", "evidence.uploaded"]


def test_tampering_is_detected_and_blocks_verification(team):
    case = team["case"]
    upload(team["officer"], case, CALLS_CSV, "calls.csv", "call_records")
    process_latest_job(case, "CALL-001")

    with SessionLocal() as db:
        evidence = db.scalar(
            select(Evidence)
            .where(Evidence.reference == "CALL-001")
            .where(Evidence.investigation.has(reference=case))
        )
        path = storage.path_of(evidence.storage_key)
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    path.write_bytes(CALLS_CSV + b"+1555,+1556,2026-09-28T22:00:00,5\n")  # someone edits it

    checked = team["analyst"].post(f"/api/investigations/{case}/evidence/CALL-001/verify-integrity")
    assert checked.json()["integrity_ok"] is False
    assert checked.json()["status"] == "requires_review"
    verify = team["analyst"].post(
        f"/api/investigations/{case}/evidence/CALL-001/status", json={"status": "verified"}
    )
    assert verify.status_code == 409


def test_review_status_needs_verify_permission(team):
    case = team["case"]
    upload(team["officer"], case, CALLS_CSV, "calls.csv", "call_records")
    url = f"/api/investigations/{case}/evidence/CALL-001/status"

    early = team["analyst"].post(url, json={"status": "verified"})
    assert early.status_code == 409 and "processing" in early.json()["detail"]

    process_latest_job(case, "CALL-001")
    assert team["officer"].post(url, json={"status": "verified"}).status_code == 403
    ok = team["analyst"].post(url, json={"status": "verified", "note": "Matches carrier export"})
    assert ok.status_code == 200 and ok.json()["status"] == "verified"


def test_non_members_cannot_see_or_upload(team, make_user):
    outsider = signed_in(make_user("investigation_officer"))
    case = team["case"]
    assert outsider.get(f"/api/investigations/{case}/evidence").status_code == 404
    assert upload(outsider, case, CALLS_CSV, "c.csv", "call_records").status_code == 404


def test_closed_investigations_do_not_accept_evidence(team):
    case = team["case"]
    for status in ("active", "closed"):
        team["officer"].patch(f"/api/investigations/{case}", json={"status": status})
    assert upload(team["officer"], case, CALLS_CSV, "c.csv", "call_records").status_code == 409


def test_investigation_reports_real_evidence_count(team):
    case = team["case"]
    upload(team["officer"], case, CALLS_CSV, "c.csv", "call_records")
    upload(team["officer"], case, jpeg_with_exif(), "s.jpg", "image")
    assert team["officer"].get(f"/api/investigations/{case}").json()["counts"]["evidence"] == 2


def test_list_filters_by_type_and_search(team):
    case = team["case"]
    upload(team["officer"], case, CALLS_CSV, "carrier_calls.csv", "call_records")
    upload(team["officer"], case, jpeg_with_exif(), "scene.jpg", "image", source="Gate camera")
    url = f"/api/investigations/{case}/evidence"
    assert team["officer"].get(url, params={"evidence_type": "image"}).json()["total"] == 1
    found = team["officer"].get(url, params={"search": "gate"}).json()
    assert [e["reference"] for e in found["items"]] == ["IMG-001"]


# ---------- Worker / queue --------------------------------------------------------------


def test_two_workers_never_claim_the_same_job(team):
    case = team["case"]
    upload(team["officer"], case, CALLS_CSV, "a.csv", "call_records")
    upload(team["officer"], case, jpeg_with_exif(), "b.jpg", "image")

    claimed: list[uuid.UUID | None] = []
    barrier = threading.Barrier(2)

    def worker():
        with SessionLocal() as db:
            barrier.wait()
            job = claim_next_job(db)
            claimed.append(job.id if job else None)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    real = [c for c in claimed if c is not None]
    assert len(real) == len(set(real))  # no job handed out twice


def test_stale_running_jobs_are_requeued(team):
    from datetime import UTC, datetime, timedelta

    case = team["case"]
    upload(team["officer"], case, CALLS_CSV, "a.csv", "call_records")
    with SessionLocal() as db:
        job = db.scalar(
            select(ProcessingJob).join(Evidence).where(Evidence.investigation.has(reference=case))
        )
        job.status = "running"
        job.attempts = 1
        job.heartbeat_at = datetime.now(UTC) - timedelta(minutes=10)
        db.commit()
        job_id = job.id
        assert requeue_stale_jobs(db) >= 1
        db.expire_all()
        assert db.get(ProcessingJob, job_id).status == "queued"


def test_processing_results_are_audited(team):
    case = team["case"]
    upload(team["officer"], case, CALLS_CSV, "a.csv", "call_records")
    process_latest_job(case, "CALL-001")
    with SessionLocal() as db:
        actions = db.scalars(
            select(AuditLog.action)
            .where(AuditLog.object_id == f"{case}/CALL-001")
            .order_by(AuditLog.id)
        ).all()
    assert list(actions) == ["evidence.uploaded", "evidence.processed"]


def test_reprocess_returns_the_new_queued_job(team):
    case = team["case"]
    upload(team["officer"], case, CALLS_CSV, "a.csv", "call_records")
    url = f"/api/investigations/{case}/evidence/CALL-001/reprocess"
    assert team["officer"].post(url).status_code == 409  # still queued: nothing to restart
    process_latest_job(case, "CALL-001")
    body = team["officer"].post(url).json()
    assert body["latest_job"]["status"] == "queued"
    assert body["status"] == "uploaded"
