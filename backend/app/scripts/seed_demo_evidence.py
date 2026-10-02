"""Add fictional demonstration evidence to CASE-2026-001. Development only.

    uv run python -m app.scripts.seed_demo_evidence

Every file is generated here (no real data) and uploaded through the real upload service,
so it is fingerprinted, stored read-only and queued for processing like any real upload.
Phone numbers use the reserved fictional range 555-01xx. Safe to run twice.

The story (all fictional): on 28 Sept 2026 around 20:30, a warehouse at Riverside
Industrial Zone (LOC-A) is broken into. A photo, a phone's GPS track, call records, a card
payment at a nearby fuel station (LOC-B) and an incident report are collected.
"""

import io
import sys
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw
from PIL.TiffImagePlugin import IFDRational
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Evidence, Investigation, User
from app.services import evidence_service
from app.services.errors import ConflictError
from app.services.request_context import RequestContext

CASE = "CASE-2026-001"
IST = timezone(timedelta(hours=5, minutes=30))  # the fictional scene's local time zone
LOC_A = (17.43862, 78.39215)  # Riverside warehouse (fictional scene)
LOC_B = (17.44510, 78.38020)  # Fuel station 1.4 km away (fictional)


def _dms(value: float) -> tuple[IFDRational, IFDRational, IFDRational]:
    degrees = int(value)
    minutes_full = (value - degrees) * 60
    minutes = int(minutes_full)
    seconds = round((minutes_full - minutes) * 60 * 100)
    return IFDRational(degrees), IFDRational(minutes), IFDRational(seconds, 100)


def scene_photo() -> bytes:
    image = Image.new("RGB", (960, 640), (28, 38, 58))
    draw = ImageDraw.Draw(image)
    draw.rectangle((120, 260, 840, 600), fill=(70, 78, 92))  # warehouse wall
    draw.rectangle((420, 380, 560, 600), fill=(20, 24, 30))  # forced door
    draw.line((420, 380, 560, 600), fill=(200, 60, 60), width=4)
    draw.text(
        (24, 24), "FICTIONAL DEMO IMAGE - Riverside warehouse, rear door", fill=(220, 230, 240)
    )
    exif = Image.Exif()
    exif[0x010F] = "DemoCam"
    exif[0x0110] = "FX-200"
    exif.get_ifd(0x8769)[0x9003] = "2026:09:28 20:41:12"  # camera clock
    exif.get_ifd(0x8769)[0x9011] = "+05:30"  # OffsetTimeOriginal: the camera recorded its zone
    exif[0x8825] = {1: "N", 2: _dms(LOC_A[0]), 3: "E", 4: _dms(LOC_A[1])}
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=88, exif=exif)
    return buffer.getvalue()


def gps_track() -> bytes:
    rows = [
        ("D001", "2026-09-28T20:18:00+05:30", 17.43120, 78.40110),
        ("D001", "2026-09-28T20:24:00+05:30", 17.43540, 78.39720),
        ("D001", "2026-09-28T20:31:00+05:30", LOC_A[0], LOC_A[1]),
        ("D001", "2026-09-28T20:39:00+05:30", LOC_A[0] + 0.00010, LOC_A[1] - 0.00008),
        ("D001", "2026-09-28T20:44:00+05:30", LOC_B[0], LOC_B[1]),
        ("D001", "2026-09-28T20:58:00+05:30", 17.45230, 78.37110),
    ]
    lines = ["device_id,recorded_at,latitude,longitude"]
    lines += [f"{d},{t},{lat:.5f},{lon:.5f}" for d, t, lat, lon in rows]
    return ("\n".join(lines) + "\n").encode()


def call_records() -> bytes:
    return (
        b"caller,callee,started_at,duration_s,cell_site\n"
        b"+1-555-0101,+1-555-0102,2026-09-28T20:33:00+05:30,95,RIVERSIDE-07\n"
        b"+1-555-0102,+1-555-0101,2026-09-28T20:47:00+05:30,40,DOCKROAD-02\n"
        b"+1-555-0101,+1-555-0177,2026-09-28T21:05:00+05:30,12,DOCKROAD-02\n"
    )


def transactions() -> bytes:
    return (
        b"transaction_id,account,merchant,amount,currency,occurred_at\n"
        b"TX-88213,A001,Dockroad Fuel Station,42.50,USD,2026-09-28T20:45:00Z\n"
        b"TX-88240,A001,Night Mart Riverside,8.20,USD,2026-09-28T21:12:00Z\n"
    )


def incident_report() -> bytes:
    return (
        b"INCIDENT REPORT (FICTIONAL DEMONSTRATION DOCUMENT)\n\n"
        b"Reference: CASE-2026-001\n"
        b"Location: Riverside Industrial Zone, Warehouse 4 (LOC-A)\n"
        b"Reported: 28 September 2026, 22:10\n\n"
        b"The night supervisor found the rear door forced open at approximately 22:00.\n"
        b"Pallets of electronics were missing. A grey van (registration V001 on the gate log)\n"
        b"was seen leaving around 20:37. Staff member P001 was on the rota until 20:00.\n"
    )


ITEMS = [
    (
        "scene_rear_door.jpg",
        "image",
        scene_photo,
        "Rear door, photographed by first responder",
        "Patrol officer phone",
        "Riverside Industrial Zone, Warehouse 4",
        None,
    ),
    (
        "device_D001_track.csv",
        "gps",
        gps_track,
        "Location history of device D001",
        "Carrier location export",
        "",
        None,
    ),
    (
        "calls_2026-09-28.csv",
        "call_records",
        call_records,
        "Call records for +1-555-0101",
        "Carrier call-detail records",
        "",
        None,
    ),
    (
        "account_A001_txns.csv",
        "financial",
        transactions,
        "Card transactions on account A001",
        "Bank disclosure",
        "",
        None,
    ),
    (
        "incident_report.txt",
        "document",
        incident_report,
        "Initial incident report",
        "Site supervisor",
        "Riverside Industrial Zone",
        datetime(2026, 9, 28, 22, 10, tzinfo=IST),
    ),
]


def main() -> int:
    if get_settings().environment != "development":
        print("Refusing to seed demo data outside development.")
        return 1
    context = RequestContext(ip_address=None, user_agent="seed-script")
    with SessionLocal() as db:
        lead = db.scalar(select(User).where(User.email == "r.varma@falcon.example"))
        case = db.scalar(select(Investigation).where(Investigation.reference == CASE))
        if lead is None or case is None:
            print("Run seed_demo_users and seed_demo_investigations first.")
            return 1
        for filename, evidence_type, build, description, source, location, collected in ITEMS:
            upload = evidence_service.EvidenceUpload(
                file=io.BytesIO(build()),
                filename=filename,
                evidence_type=evidence_type,
                source=source,
                description=description,
                location_text=location,
                collected_at=collected,
                tags=["demo"],
            )
            try:
                evidence = evidence_service.upload(db, lead, CASE, upload, context)
                print(f"uploaded {evidence.reference:9} {filename}")
            except ConflictError as exists:
                print(f"exists   {filename}: {exists.message[:60]}…")
        total = db.query(Evidence).filter(Evidence.investigation_id == case.id).count()
        print(f"{CASE} now has {total} evidence items. The worker will process them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
