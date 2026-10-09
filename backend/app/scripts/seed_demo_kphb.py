"""Fictional demo case CASE-2026-005: a chain snatching in KPHB Colony, Hyderabad. Dev only.

    uv run python -m app.scripts.seed_demo_kphb

Every file is generated here and uploaded through the real upload service (fingerprinted,
stored read-only, processed by the worker). People, phone numbers (+91 90000 0xxxx), UPI IDs
and the plate TG 09 ZZ 0001 are INVENTED; the places are real Hyderabad areas, the scene is not.
Safe to run twice.

The story, Wednesday 7 Oct 2026, India time (+05:30):
  19:28  the rider's phone (IMEI ...011) leaves Moosapet                         GPS-001
  19:42  temple lane: the pillion rider snatches Lakshmi Devi's chain  VEH-001 (community cam)
         the shop camera records it too, but ITS CLOCK RUNS 2 MIN FAST (19:44)   CCTV-001
  19:46  TG 09 ZZ 0001 at the JNTU junction ANPR camera                          VEH-001, GPS-001
  19:47  +91 90000 01111 calls +91 90000 02222 (later: a gold buyer)            CALL-001
  19:58  UPI: Rs 200 of petrol at a Miyapur bunk                                TXN-001, GPS-001
  20:05  the victim's son photographs the spot                                   IMG-001
  20:47  the bike passes Kukatpally main road, near a gold exchange              VEH-001, GPS-001
  21:30  FIR registered; next morning a tea-stall owner gives a statement        DOC-001, WIT-001
Also: the same plate was reported stolen in CASE-2026-003 (a cross-case lead).
"""

import io
import sys
from datetime import UTC, datetime, timedelta, timezone

import av
from PIL import Image, ImageDraw
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Evidence, Investigation, User
from app.scripts.seed_demo_evidence import _dms, _font
from app.services import evidence_service, extraction_service
from app.services.errors import ConflictError
from app.services.request_context import RequestContext

CASE = "CASE-2026-005"
THEFT_CASE = "CASE-2026-003"
IST = timezone(timedelta(hours=5, minutes=30))
PLATE = "TG 09 ZZ 0001"
RIDER_PHONE = "+91 90000 01111"
BUYER_PHONE = "+91 90000 02222"
SCENE = (17.48720, 78.39010)  # temple lane, KPHB Colony (fictional spot)
SHOP_CAM = (17.48745, 78.39030)  # the shop camera, ~35 m from the community camera
JNTU = (17.49380, 78.39190)  # JNTU junction ANPR camera
BUNK = (17.49650, 78.35790)  # petrol bunk on the Miyapur road (fictional business)
GOLD = (17.48390, 78.41210)  # Kukatpally main road, near a gold exchange (fictional business)
CAMERA_FAST_BY = timedelta(minutes=2)  # the shop camera's clock is wrong: 2 minutes ahead


def shop_cctv() -> bytes:
    """12 s of an evening street; the burned-in clock is the camera's own (2 min fast)."""
    start = datetime(2026, 10, 7, 19, 42, 0, tzinfo=IST) + CAMERA_FAST_BY
    buffer = io.BytesIO()
    with av.open(buffer, mode="w", format="mp4") as out:
        out.metadata["creation_time"] = start.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000000Z")
        stream = out.add_stream("mpeg4", rate=5)
        stream.width, stream.height, stream.pix_fmt = 320, 240, "yuv420p"
        for i in range(60):
            frame = Image.new("RGB", (320, 240), (30, 30, 42))
            draw = ImageDraw.Draw(frame)
            draw.rectangle((0, 150, 320, 240), fill=(55, 55, 60))  # road
            draw.rectangle((20, 40, 120, 150), fill=(70, 50, 40))  # temple wall
            stamp = (start + timedelta(seconds=i // 5)).strftime("%d-%m-%Y %H:%M:%S")
            draw.text((8, 8), f"SHOP-CAM-02  {stamp}  DEMO", fill=(210, 210, 210))
            draw.rectangle((200, 170, 214, 205), fill=(150, 120, 60))  # pedestrian
            if 15 <= i < 45:  # the motorcycle passes from left to right
                x = 40 + (i - 15) * 8
                draw.rectangle((x, 180, x + 46, 205), fill=(10, 10, 10))
                draw.rectangle((x + 10, 160, x + 22, 182), fill=(140, 30, 30))  # red jacket
            for packet in stream.encode(av.VideoFrame.from_image(frame)):
                out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)
    return buffer.getvalue()


def spot_photo() -> bytes:
    image = Image.new("RGB", (960, 640), (36, 40, 52))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 420, 960, 640), fill=(70, 70, 74))  # road
    draw.rectangle((60, 160, 380, 420), fill=(120, 80, 50))  # temple compound wall
    draw.ellipse((520, 470, 560, 490), outline=(230, 200, 80), width=3)  # broken clasp found
    draw.text((24, 24), "FICTIONAL DEMO IMAGE - temple lane, KPHB Colony", fill=(230, 230, 240))
    exif = Image.Exif()
    exif[0x010F] = "DemoPhone"
    exif[0x0110] = "N-12"
    exif.get_ifd(0x8769)[0x9003] = "2026:10:07 20:05:31"
    exif.get_ifd(0x8769)[0x9011] = "+05:30"
    exif[0x8825] = {1: "N", 2: _dms(SCENE[0]), 3: "E", 4: _dms(SCENE[1])}
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=88, exif=exif)
    return buffer.getvalue()


def phone_location() -> bytes:
    rows = [
        ("19:28:00", 17.46600, 78.42500),  # Moosapet
        ("19:35:00", 17.47800, 78.40500),
        ("19:42:10", SCENE[0] + 0.00005, SCENE[1]),  # at the temple lane
        ("19:46:05", JNTU[0], JNTU[1] + 0.00010),
        ("19:52:00", 17.49600, 78.37800),
        ("19:58:20", BUNK[0], BUNK[1] + 0.00008),
        ("20:25:00", 17.49000, 78.40000),
        ("20:48:00", GOLD[0] + 0.00010, GOLD[1]),
        ("21:15:00", 17.47000, 78.42000),
    ]
    lines = ["device_id,recorded_at,latitude,longitude"]
    lines += [f"IMEI-860000000000011,2026-10-07T{t}+05:30,{a:.5f},{b:.5f}" for t, a, b in rows]
    return ("\n".join(lines) + "\n").encode()


def call_records() -> bytes:
    return (
        "caller,callee,started_at,duration_s,cell_site\n"
        f"{RIDER_PHONE},{BUYER_PHONE},2026-10-07T19:47:30+05:30,48,KPHB-12\n"
        f"{BUYER_PHONE},{RIDER_PHONE},2026-10-07T20:20:00+05:30,65,MIYAPUR-04\n"
        f"{RIDER_PHONE},+91 90000 03333,2026-10-07T20:52:00+05:30,20,KUKATPALLY-09\n"
    ).encode()


def upi_statement() -> bytes:
    return (
        "transaction_id,account,merchant,amount,currency,occurred_at,latitude,longitude\n"
        f"UPI-71001,suresh.k.demo@upi,Miyapur Highway Fuels,200.00,INR,"
        f"2026-10-07T19:58:40+05:30,{BUNK[0]:.5f},{BUNK[1]:.5f}\n"
        f"UPI-71044,suresh.k.demo@upi,Kukatpally Mobile Store,1450.00,INR,"
        f"2026-10-07T21:05:00+05:30,{GOLD[0] - 0.0006:.5f},{GOLD[1] + 0.0004:.5f}\n"
    ).encode()


def anpr_log() -> bytes:
    return (
        "plate,seen_at,camera,latitude,longitude\n"
        f"{PLATE},2026-10-07T19:42:15+05:30,TEMPLE-LANE-CC03,{SCENE[0]:.5f},{SCENE[1]:.5f}\n"
        f"{PLATE},2026-10-07T19:46:00+05:30,JNTU-JN-ANPR-01,{JNTU[0]:.5f},{JNTU[1]:.5f}\n"
        f"{PLATE},2026-10-07T20:47:30+05:30,KUKATPALLY-MR-ANPR-07,{GOLD[0]:.5f},{GOLD[1]:.5f}\n"
    ).encode()


def fir_copy() -> bytes:
    return (
        b"FIRST INFORMATION REPORT (FICTIONAL DEMONSTRATION DOCUMENT)\n\n"
        b"FIR No.: 0412/2026    Police Station: KPHB Colony (demo)    District: Cyberabad\n"
        b"Section: 304 BNS (snatching)\n"
        b"Date and time of report: 07-10-2026 21:30\n\n"
        b"Complainant: Lakshmi Devi, aged 62, resident of KPHB Colony.\n\n"
        b"On 07-10-2026 at about 19:40 hrs, while the complainant was walking home from the\n"
        b"temple, two unknown persons came on a black motorcycle. The pillion rider, wearing a\n"
        b"red jacket and helmet, snatched her gold chain of about 3 tolas (approx. Rs 2,10,000)\n"
        b"and both fled towards JNTU. A passer-by noted the number as TG 09 ZZ 0001.\n"
        b"Her son Kiran Kumar can be contacted on +91 90000 04444.\n"
    )


def witness_scan() -> bytes:
    """A paper statement, scanned without a text layer: FALCON must OCR it."""
    page = Image.new("RGB", (1240, 900), "white")
    draw = ImageDraw.Draw(page)
    lines = [
        ("WITNESS STATEMENT (FICTIONAL DEMO)", 44),
        ("Name: Srinivas Rao, tea stall owner", 34),
        ("Date: 8 October 2026", 34),
        ("At about 7:40 pm two men on a black bike", 32),
        (f"pulled a chain from a lady. Number {PLATE}.", 32),
        ("The rider in a red jacket was on his phone.", 32),
        ("Contact: +91 90000 05555", 32),
    ]
    y = 60
    for text, size in lines:
        draw.text((60, y), text, fill="black", font=_font(size))
        y += size + 48
    buffer = io.BytesIO()
    page.save(buffer, "PDF", resolution=150)
    return buffer.getvalue()


def theft_complaint() -> bytes:
    """The earlier case: the same motorcycle was reported stolen four days before."""
    return (
        "E-PETTY CASE / VEHICLE THEFT COMPLAINT (FICTIONAL DEMONSTRATION DOCUMENT)\n\n"
        "Date: 03-10-2026    Area: Miyapur metro station parking\n"
        f"Vehicle: black motorcycle, registration {PLATE}.\n"
        "Owner: Ramesh Goud, contact +91 90000 06666.\n"
        "The owner parked at 08:15 and found the vehicle missing at 18:40.\n"
    ).encode()


# (case, file name, evidence type, builder, description, source, location, collected, lat/lon)
ITEMS = [
    (
        CASE,
        "shop_cam_02_1944.mp4",
        "video",
        shop_cctv,
        "Shop camera facing the temple lane",
        "Sri Durga Kirana (fictional) DVR export",
        "Temple lane, KPHB Colony",
        None,
        SHOP_CAM,
    ),
    (
        CASE,
        "spot_photo_son.jpg",
        "image",
        spot_photo,
        "The spot, photographed by the victim's son",
        "Complainant's son, phone camera",
        "Temple lane, KPHB Colony",
        None,
        None,
    ),
    (
        CASE,
        "imei_011_locations.csv",
        "gps",
        phone_location,
        "Location history of the rider's phone (IMEI ...011)",
        "Handset location disclosure",
        "",
        None,
        None,
    ),
    (
        CASE,
        "cdr_9000001111.csv",
        "call_records",
        call_records,
        f"Call records for {RIDER_PHONE}",
        "Telecom operator CDR (fictional)",
        "",
        None,
        None,
    ),
    (
        CASE,
        "upi_suresh_k_demo.csv",
        "financial",
        upi_statement,
        "UPI statement, suresh.k.demo@upi",
        "Bank disclosure (fictional)",
        "",
        None,
        None,
    ),
    (
        CASE,
        "traffic_anpr_0710.csv",
        "vehicle",
        anpr_log,
        "ANPR and community camera hits for TG 09 ZZ 0001",
        "Traffic police ANPR export",
        "",
        None,
        None,
    ),
    (
        CASE,
        "fir_0412_2026.txt",
        "document",
        fir_copy,
        "FIR 0412/2026 (copy)",
        "KPHB Colony police station (demo)",
        "KPHB Colony",
        datetime(2026, 10, 7, 21, 30, tzinfo=IST),
        None,
    ),
    (
        CASE,
        "statement_srinivas_rao.pdf",
        "witness_statement",
        witness_scan,
        "Eyewitness statement (scanned paper)",
        "Recorded by SI M. Das (demo)",
        "",
        datetime(2026, 10, 8, 10, 0, tzinfo=IST),
        None,
    ),
    (
        THEFT_CASE,
        "theft_complaint_tg09zz0001.txt",
        "document",
        theft_complaint,
        "Vehicle theft complaint, Miyapur metro parking",
        "Miyapur police station (demo)",
        "Miyapur",
        datetime(2026, 10, 3, 19, 30, tzinfo=IST),
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
        for case_ref, name, kind, build, description, source, place, collected, at in ITEMS:
            upload = evidence_service.EvidenceUpload(
                file=io.BytesIO(build()),
                filename=name,
                evidence_type=kind,
                source=source,
                description=description,
                location_text=place,
                collected_at=collected,
                latitude=at[0] if at else None,
                longitude=at[1] if at else None,
                tags=["demo"],
            )
            try:
                evidence = evidence_service.upload(db, lead, case_ref, upload, context)
                print(f"uploaded {case_ref} {evidence.reference:9} {name}")
            except ConflictError as exists:
                print(f"exists   {name}: {exists.message[:60]}…")
        _analyst_notes(db, analyst, context)
        total = db.query(Evidence).filter(Evidence.investigation_id == case.id).count()
        print(f"{CASE} now has {total} evidence items. The worker will process them.")
    return 0


def _analyst_notes(db, analyst: User, context: RequestContext) -> None:
    """What the analyst writes while watching CCTV-001, in the CAMERA's (wrong) time."""
    existing = extraction_service.list_events(
        db, analyst, CASE, extraction_service.EventFilters(evidence_reference="CCTV-001"), 50, 0
    )[0]
    if any(e.created_by_id for e in existing):
        print("exists   analyst notes on CCTV-001")
        return
    bike = extraction_service.create_entity(
        db,
        analyst,
        CASE,
        "vehicle",
        PLATE,
        "CCTV-001",
        "Plate readable as the motorcycle passes the shop camera",
        context,
    )
    camera_time = datetime(2026, 10, 7, 19, 42, 3, tzinfo=IST) + CAMERA_FAST_BY
    notes = [
        (
            "person_detected",
            camera_time,
            "Pillion rider in a red jacket pulls a chain from a woman walking from the temple "
            "(both riders wear helmets; faces not visible)",
            [],
        ),
        (
            "vehicle_detected",
            camera_time + timedelta(seconds=9),
            "Black motorcycle leaves towards JNTU; plate readable",
            [(bike.reference, "vehicle")],
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
                latitude=SHOP_CAM[0],
                longitude=SHOP_CAM[1],
                location_text="Temple lane, KPHB Colony",
            ),
            context,
        )
    print("added    analyst notes on CCTV-001 (2 events, 1 entity), in the camera's own time")


if __name__ == "__main__":
    sys.exit(main())
