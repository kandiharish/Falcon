"""Add fictional demonstration evidence to CASE-2026-001. Development only.

    uv run python -m app.scripts.seed_demo_evidence

Every file is generated here (no real data) and uploaded through the real upload service,
so it is fingerprinted, stored read-only and processed like any real upload.
Phone numbers use the fictional 555-01xx range; the plate uses the non-existent state code
"ZZ"; names are invented. Safe to run twice.

The story (all fictional), 28 Sept 2026, India time (+05:30):
  20:30  rear-door camera of Warehouse 4 records a person at the door        CCTV-001
  20:31  phone DEVICE-A7 is at the warehouse                                 GPS-001
  20:33  +1 202-555-0101 calls +1 202-555-0102 (cell RIVERSIDE-07)            CALL-001
  20:37  grey van ZZ99 ZZ 0001 passes gate camera                           VEH-001, CCTV-001
  20:41  photo of the forced door                                            IMG-001
  20:44  DEVICE-A7 at Dockroad Fuel Station; 20:45 card A-4421-0098 pays     GPS-001, TXN-001
  22:10  incident report written (names staff member Ravi Kumar)             DOC-001
  next day: witness Anita Shah's statement, scanned on paper                  WIT-001
"""

import io
import sys
from datetime import datetime, timedelta, timezone

import av
from PIL import Image, ImageDraw, ImageFont
from PIL.TiffImagePlugin import IFDRational
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Evidence, Investigation, User
from app.services import evidence_service, extraction_service
from app.services.errors import ConflictError
from app.services.request_context import RequestContext

CASE = "CASE-2026-001"
IST = timezone(timedelta(hours=5, minutes=30))  # the fictional scene's local time zone
LOC_A = (17.43862, 78.39215)  # Riverside Industrial Zone, Warehouse 4 (fictional scene)
LOC_B = (17.44510, 78.38020)  # Dockroad Fuel Station, 1.4 km away (fictional)
PLATE = "ZZ99 ZZ 0001"


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default(size)


def _dms(value: float) -> tuple[IFDRational, IFDRational, IFDRational]:
    degrees = int(value)
    minutes_full = (value - degrees) * 60
    minutes = int(minutes_full)
    seconds = round((minutes_full - minutes) * 60 * 100)
    return IFDRational(degrees), IFDRational(minutes), IFDRational(seconds, 100)


def cctv_video() -> bytes:
    """10 seconds of a dark rear-door scene, with the camera's recording time inside."""
    buffer = io.BytesIO()
    with av.open(buffer, mode="w", format="mp4") as out:
        out.metadata["creation_time"] = "2026-09-28T15:00:00.000000Z"  # 20:30 IST
        stream = out.add_stream("mpeg4", rate=5)
        stream.width, stream.height, stream.pix_fmt = 320, 240, "yuv420p"
        for i in range(50):
            frame = Image.new("RGB", (320, 240), (22, 28, 40))
            draw = ImageDraw.Draw(frame)
            draw.rectangle((110, 60, 210, 230), fill=(48, 52, 60))  # door
            draw.text((8, 8), f"CAM-RD4  2026-09-28 20:30:{i // 5:02d}  DEMO", fill=(200, 200, 200))
            if 10 <= i < 35:  # a figure at the door for a few seconds
                draw.rectangle((140, 110, 170, 220), fill=(90, 90, 100))
            for packet in stream.encode(av.VideoFrame.from_image(frame)):
                out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)
    return buffer.getvalue()


def scene_photo() -> bytes:
    image = Image.new("RGB", (960, 640), (28, 38, 58))
    draw = ImageDraw.Draw(image)
    draw.rectangle((120, 260, 840, 600), fill=(70, 78, 92))  # warehouse wall
    draw.rectangle((420, 380, 560, 600), fill=(20, 24, 30))  # forced door
    draw.line((420, 380, 560, 600), fill=(200, 60, 60), width=4)
    draw.text((24, 24), "FICTIONAL DEMO IMAGE - Warehouse 4, rear door", fill=(220, 230, 240))
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
        ("20:18", 17.43120, 78.40110),
        ("20:24", 17.43540, 78.39720),
        ("20:31", LOC_A[0], LOC_A[1]),
        ("20:39", LOC_A[0] + 0.00010, LOC_A[1] - 0.00008),
        ("20:44", LOC_B[0], LOC_B[1]),
        ("20:58", 17.45230, 78.37110),
    ]
    lines = ["device_id,recorded_at,latitude,longitude"]
    lines += [f"DEVICE-A7,2026-09-28T{t}:00+05:30,{lat:.5f},{lon:.5f}" for t, lat, lon in rows]
    return ("\n".join(lines) + "\n").encode()


def call_records() -> bytes:
    return (
        b"caller,callee,started_at,duration_s,cell_site\n"
        b"+1-202-555-0101,+1-202-555-0102,2026-09-28T20:33:00+05:30,95,RIVERSIDE-07\n"
        b"+1-202-555-0102,+1-202-555-0101,2026-09-28T20:47:00+05:30,40,DOCKROAD-02\n"
        b"+1-202-555-0101,+1-202-555-0177,2026-09-28T21:05:00+05:30,12,DOCKROAD-02\n"
    )


def transactions() -> bytes:
    return (
        b"transaction_id,account,merchant,amount,currency,occurred_at\n"
        b"TX-88213,A-4421-0098,Dockroad Fuel Station,42.50,USD,2026-09-28T20:45:00+05:30\n"
        b"TX-88240,A-4421-0098,Night Mart Riverside,8.20,USD,2026-09-28T21:12:00+05:30\n"
    )


def vehicle_sightings() -> bytes:
    return (
        f"plate,seen_at,camera,latitude,longitude\n"
        f"{PLATE},2026-09-28T20:37:00+05:30,GATE-02,{LOC_A[0] + 0.0004:.5f},{LOC_A[1]:.5f}\n"
        f"{PLATE},2026-09-28T20:52:00+05:30,DOCKROAD-01,{LOC_B[0]:.5f},{LOC_B[1] + 0.0003:.5f}\n"
    ).encode()


def incident_report() -> bytes:
    return (
        "INCIDENT REPORT (FICTIONAL DEMONSTRATION DOCUMENT)\n\n"
        "Reference: CASE-2026-001\n"
        "Location: Riverside Industrial Zone, Warehouse 4\n"
        "Reported: 28 September 2026, 22:10\n\n"
        "The night supervisor found the rear door forced open at approximately 22:00.\n"
        "Pallets of electronics were missing. The gate log shows a grey van with\n"
        f"registration {PLATE} leaving at 20:37. Staff member Ravi Kumar was on the rota\n"
        "until 20:00; his work phone is +1 202-555-0101. Security contractor Nightline\n"
        "Security Services has been asked for the full camera export.\n"
    ).encode()


def witness_statement_scan() -> bytes:
    """A paper statement, scanned: an image-only PDF (no text layer) → needs OCR."""
    page = Image.new("RGB", (1240, 900), "white")
    draw = ImageDraw.Draw(page)
    lines = [
        ("WITNESS STATEMENT (FICTIONAL DEMO)", 44),
        ("Name: Anita Shah", 36),
        ("Date: 29 September 2026", 36),
        ("At about 8:37 pm I saw a grey van leave the rear gate", 32),
        (f"of Warehouse 4. The number plate was {PLATE}.", 32),
        ("The driver was talking on a mobile phone.", 32),
        ("Contact: +1 202-555-0150", 32),
    ]
    y = 60
    for text, size in lines:
        draw.text((60, y), text, fill="black", font=_font(size))
        y += size + 48
    buffer = io.BytesIO()
    page.save(buffer, "PDF", resolution=150)
    return buffer.getvalue()


# (file name, evidence type, builder, description, source, location, collected at, lat/lon)
ITEMS = [
    (
        "rear_door_cam_2030.mp4",
        "video",
        cctv_video,
        "Rear-door camera, Warehouse 4",
        "Nightline Security camera export",
        "Warehouse 4 rear door",
        None,
        LOC_A,
    ),
    (
        "scene_rear_door.jpg",
        "image",
        scene_photo,
        "Rear door, photographed by first responder",
        "Patrol officer phone",
        "Riverside Industrial Zone, Warehouse 4",
        None,
        None,
    ),
    (
        "device_A7_track.csv",
        "gps",
        gps_track,
        "Location history of device DEVICE-A7",
        "Carrier location export",
        "",
        None,
        None,
    ),
    (
        "calls_2026-09-28.csv",
        "call_records",
        call_records,
        "Call records for +1 202-555-0101",
        "Carrier call-detail records",
        "",
        None,
        None,
    ),
    (
        "account_transactions.csv",
        "financial",
        transactions,
        "Card transactions, A-4421-0098",
        "Bank disclosure",
        "",
        None,
        None,
    ),
    (
        "gate_anpr.csv",
        "vehicle",
        vehicle_sightings,
        "Number-plate camera sightings",
        "Municipal ANPR export",
        "",
        None,
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
        None,
    ),
    (
        "witness_statement_shah.pdf",
        "witness_statement",
        witness_statement_scan,
        "Witness statement (scanned paper)",
        "Taken by SI K. Iyer",
        "",
        datetime(2026, 9, 29, 11, 0, tzinfo=IST),
        None,
    ),
]


def main() -> int:
    if get_settings().environment != "development":
        print("Refusing to seed demo data outside development.")
        return 1
    context = RequestContext(ip_address=None, user_agent="seed-script")
    with SessionLocal() as db:
        lead = db.scalar(select(User).where(User.email == "r.varma@falcon.example"))
        analyst = db.scalar(select(User).where(User.email == "a.kumar@falcon.example"))
        case = db.scalar(select(Investigation).where(Investigation.reference == CASE))
        if lead is None or analyst is None or case is None:
            print("Run seed_demo_users and seed_demo_investigations first.")
            return 1
        for name, kind, build, description, source, location, collected, coords in ITEMS:
            upload = evidence_service.EvidenceUpload(
                file=io.BytesIO(build()),
                filename=name,
                evidence_type=kind,
                source=source,
                description=description,
                location_text=location,
                collected_at=collected,
                latitude=coords[0] if coords else None,
                longitude=coords[1] if coords else None,
                tags=["demo"],
            )
            try:
                evidence = evidence_service.upload(db, lead, CASE, upload, context)
                print(f"uploaded {evidence.reference:9} {name}")
            except ConflictError as exists:
                print(f"exists   {name}: {exists.message[:60]}…")

        _analyst_notes(db, analyst, context)
        total = db.query(Evidence).filter(Evidence.investigation_id == case.id).count()
        print(f"{CASE} now has {total} evidence items. The worker will process them.")
    return 0


def _analyst_notes(db, analyst: User, context: RequestContext) -> None:
    """What an analyst writes down while watching CCTV-001 — USER ENTERED, never automatic."""
    existing = extraction_service.list_events(
        db, analyst, CASE, extraction_service.EventFilters(evidence_reference="CCTV-001"), 50, 0
    )[0]
    if any(e.created_by_id for e in existing):
        print("exists   analyst notes on CCTV-001")
        return
    van = extraction_service.create_entity(
        db,
        analyst,
        CASE,
        "vehicle",
        PLATE,
        "CCTV-001",
        "Plate readable at 20:36:50 as the van passes the camera",
        context,
    )
    notes = [
        (
            "person_detected",
            datetime(2026, 9, 28, 20, 30, 2, tzinfo=IST),
            "Person in a dark jacket forces the rear door (face not visible)",
            [],
        ),
        (
            "vehicle_detected",
            datetime(2026, 9, 28, 20, 36, 50, tzinfo=IST),
            "Grey van passes the rear-door camera towards the gate",
            [(van.reference, "vehicle")],
        ),
    ]
    for kind, when, description, participants in notes:
        extraction_service.create_event(
            db,
            analyst,
            CASE,
            extraction_service.NewEvent(
                evidence_reference="CCTV-001",
                event_type=kind,
                occurred_at=when,
                description=description,
                participants=participants,
                latitude=LOC_A[0],
                longitude=LOC_A[1],
                location_text="Warehouse 4 rear door",
            ),
            context,
        )
    print("added    analyst notes on CCTV-001 (2 events, 1 entity)")


if __name__ == "__main__":
    sys.exit(main())
