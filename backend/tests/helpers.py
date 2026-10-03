"""Shared test helpers: signed-in clients, cases, uploads, sample files, processing."""

import io

from fastapi.testclient import TestClient
from PIL import Image
from PIL.TiffImagePlugin import IFDRational
from sqlalchemy import select

from app.db.session import SessionLocal
from app.main import app
from app.models import Evidence, ProcessingJob
from app.services import correlation_service
from app.worker import process_job_by_id

TEST_PASSWORD = "correct horse battery staple"

CALLS_CSV = (
    b"caller,callee,started_at,duration_s\n"
    b"+15550100001,+15550100002,2026-09-28T20:33:00,95\n"
    b"+15550100002,+15550100003,2026-09-28T21:02:00,40\n"
)


def signed_in(user) -> TestClient:
    """A separate browser (own cookie jar) signed in as `user`."""
    client = TestClient(app, headers={"X-FALCON-Request": "1"})
    response = client.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert response.status_code == 200
    return client


def create_case(client: TestClient, **fields):
    body = {"title": "Riverside warehouse break-in", "case_type": "Burglary"} | fields
    response = client.post("/api/investigations", json=body)
    assert response.status_code == 201, response.text
    return response.json()


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
    run_requested_correlations()


def run_requested_correlations() -> None:
    """Do what the worker does in the background: re-correlate cases that asked for it."""
    with SessionLocal() as db:
        while correlation_service.run_requested(db, settle_seconds=0):
            pass
