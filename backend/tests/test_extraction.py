"""Extraction tests: entities, events, provenance, cross-file matching, OCR, review."""

import io

import av
import docx
from PIL import Image, ImageDraw, ImageFont

from tests.helpers import CALLS_CSV, create_case, process_latest_job, signed_in, upload

GPS_CSV = (
    b"device_id,recorded_at,latitude,longitude\n"
    b"DEVICE-A7,2026-09-28T20:31:00+05:30,17.43862,78.39215\n"
    b"DEVICE-A7,2026-09-28T20:44:00+05:30,17.44510,78.38020\n"
)
TXN_CSV = (
    b"transaction_id,account,merchant,amount,currency,occurred_at\n"
    b"TX-1,A-4421-0098,Dockroad Fuel Station,42.50,USD,2026-09-28T20:45:00+05:30\n"
)
VEHICLE_CSV = b"plate,seen_at,camera\nZZ99 ZZ 0001,2026-09-28 20:37:00,GATE-02\n"
REPORT = (
    b"Incident report. Staff member Ravi Kumar (phone +1 202-555-0101) left at 20:00.\n"
    b"Witness Anita Shah saw a grey van, registration ZZ99-ZZ-0001, near Dockroad Fuel Station.\n"
    b"Contact: night.supervisor@example.org\n"
)


def entities(client, case, **params):
    return client.get(f"/api/investigations/{case}/entities", params=params).json()["items"]


def events(client, case, **params):
    return client.get(f"/api/investigations/{case}/events", params=params).json()["items"]


def by_label(items, label):
    return next(i for i in items if i["label"] == label)


# ---------- Structured records ------------------------------------------------------------


def test_call_records_become_phone_entities_and_call_events(team):
    client, case = team["officer"], team["case"]
    upload(client, case, CALLS_CSV, "calls.csv", "call_records")
    process_latest_job(case, "CALL-001")

    phones = entities(client, case, entity_type="phone_number")
    # +15550100002 appears in both rows → ONE entity, two mentions
    shared = next(p for p in phones if p["mention_count"] == 2)
    assert shared["assertion_kinds"] == ["extracted"]
    calls = events(client, case, event_type="call_made")
    assert len(calls) == 2
    first = calls[0]
    assert {p["role"] for p in first["participants"]} == {"caller", "callee"}
    assert first["evidence_reference"] == "CALL-001"
    assert first["source_location"] == "line 2"
    assert first["attributes"]["duration_s"] == 95
    # Times without a zone: lower confidence + a warning on the job
    assert first["confidence"] == 0.8
    evidence = client.get(f"/api/investigations/{case}/evidence/CALL-001").json()
    assert "time zone" in evidence["latest_job"]["error_message"]


def test_gps_transactions_and_vehicles(team):
    client, case = team["officer"], team["case"]
    upload(client, case, GPS_CSV, "track.csv", "gps")
    upload(client, case, TXN_CSV, "txn.csv", "financial")
    upload(client, case, VEHICLE_CSV, "anpr.csv", "vehicle")
    for ref in ("GPS-001", "TXN-001", "VEH-001"):
        process_latest_job(case, ref)

    fixes = events(client, case, event_type="location_recorded")
    assert [(e["latitude"], e["longitude"]) for e in fixes] == [
        (17.43862, 78.39215),
        (17.4451, 78.3802),
    ]
    assert fixes[0]["confidence"] == 0.95  # zone given → high confidence
    assert fixes[0]["participants"][0]["label"] == "DEVICE-A7"

    payment = events(client, case, event_type="transaction_completed")[0]
    assert "42.50 USD to Dockroad Fuel Station" in payment["description"]
    assert {p["entity_type"] for p in payment["participants"]} == {"account", "organization"}

    sighting = events(client, case, event_type="vehicle_detected")[0]
    assert sighting["participants"][0]["label"] == "ZZ99 ZZ 0001"


def test_missing_columns_are_reported_not_guessed(team):
    client, case = team["officer"], team["case"]
    upload(client, case, b"a,b,c\n1,2,3\n", "odd.csv", "call_records")
    process_latest_job(case, "CALL-001")
    body = client.get(f"/api/investigations/{case}/evidence/CALL-001").json()
    assert body["status"] == "requires_review"
    assert "Could not find column(s)" in body["latest_job"]["error_message"]
    assert events(client, case) == []


# ---------- Text, cross-file matching -----------------------------------------------------


def test_text_detection_and_cross_file_matching(team):
    client, case = team["officer"], team["case"]
    upload(client, case, VEHICLE_CSV, "anpr.csv", "vehicle")
    upload(client, case, REPORT, "report.txt", "document")
    process_latest_job(case, "VEH-001")
    process_latest_job(case, "DOC-001")

    found = entities(client, case)
    people = {e["label"] for e in found if e["entity_type"] == "person"}
    assert {"Ravi Kumar", "Anita Shah"} <= people
    ravi = by_label(found, "Ravi Kumar")
    assert ravi["assertion_kinds"] == ["detected"]  # a model's guess, not a fact
    assert ravi["max_confidence"] <= 0.6

    # The van's plate is in the ANPR file AND the report → one vehicle, two evidence items
    van = next(e for e in found if e["entity_type"] == "vehicle")
    assert van["evidence_count"] == 2
    assert van["assertion_kinds"] == ["detected", "extracted"]
    assert any(e["label"] == "night.supervisor@example.org" for e in found)

    detail = client.get(f"/api/investigations/{case}/entities/{van['reference']}").json()
    report_mention = next(m for m in detail["mentions"] if m["evidence_reference"] == "DOC-001")
    assert "[ZZ99-ZZ-0001]" in report_mention["context"]  # the words around it, for humans
    assert report_mention["extractor"] == "pattern:plate"


def test_scanned_pdf_is_read_with_ocr(team):
    client, case = team["officer"], team["case"]
    page = Image.new("RGB", (1240, 400), "white")
    draw = ImageDraw.Draw(page)
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except OSError:
        font = ImageFont.load_default(40)
    draw.text((40, 60), "Statement of Anita Shah", fill="black", font=font)
    draw.text((40, 160), "Call me on +1 202-555-0102", fill="black", font=font)
    buffer = io.BytesIO()
    page.save(buffer, "PDF")  # an image-only PDF: no text layer, like a scanner makes
    upload(client, case, buffer.getvalue(), "statement.pdf", "witness_statement")
    process_latest_job(case, "WIT-001")

    evidence = client.get(f"/api/investigations/{case}/evidence/WIT-001").json()
    document = evidence["file_metadata"]["document"]
    assert document["method"] == "ocr" and document["ocr_pages"] == [1]
    phone = by_label(entities(client, case, entity_type="phone_number"), "+1 202-555-0102")
    mention = client.get(f"/api/investigations/{case}/entities/{phone['reference']}").json()[
        "mentions"
    ][0]
    assert mention["extractor"] == "pattern:phone+ocr"
    assert mention["confidence"] < 0.9  # OCR uncertainty lowers confidence


def test_docx_text_is_read(team):
    client, case = team["officer"], team["case"]
    document = docx.Document()
    document.add_paragraph("Interview with Anita Shah about the grey van.")
    buffer = io.BytesIO()
    document.save(buffer)
    upload(client, case, buffer.getvalue(), "interview.docx", "witness_statement")
    process_latest_job(case, "WIT-001")
    assert any(e["label"] == "Anita Shah" for e in entities(client, case, entity_type="person"))


def test_video_metadata_and_recording_event(team):
    client, case = team["officer"], team["case"]
    buffer = io.BytesIO()
    with av.open(buffer, mode="w", format="mp4") as out:
        out.metadata["creation_time"] = "2026-09-28T15:00:00.000000Z"
        stream = out.add_stream("mpeg4", rate=5)
        stream.width, stream.height, stream.pix_fmt = 160, 120, "yuv420p"
        for i in range(10):
            frame = av.VideoFrame.from_image(Image.new("RGB", (160, 120), (i * 20, 40, 90)))
            for packet in stream.encode(frame):
                out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)
    upload(client, case, buffer.getvalue(), "gate.mp4", "video", location_text="Gate 2")
    process_latest_job(case, "CCTV-001")

    body = client.get(f"/api/investigations/{case}/evidence/CCTV-001").json()
    assert body["file_metadata"]["video"]["duration_s"] == 2.0
    assert body["collected_at"].startswith("2026-09-28T15:00:00")
    recording = events(client, case, event_type="video_recorded")[0]
    assert recording["assertion_kind"] == "extracted"
    assert recording["ended_at"].startswith("2026-09-28T15:00:02")


# ---------- Reprocessing, manual input, review --------------------------------------------


def test_reprocessing_never_duplicates_and_keeps_human_input(team):
    client, case = team["officer"], team["case"]
    upload(client, case, CALLS_CSV, "calls.csv", "call_records")
    process_latest_job(case, "CALL-001")
    phone = entities(client, case, entity_type="phone_number")[0]["reference"]
    manual = client.post(
        f"/api/investigations/{case}/events",
        json={
            "evidence_reference": "CALL-001",
            "event_type": "communication",
            "description": "Analyst note: this call matches the witness account",
            "participants": [{"entity_reference": phone, "role": "subject"}],
        },
    )
    assert manual.status_code == 201 and manual.json()["assertion_kind"] == "user_entered"
    before = (len(entities(client, case)), len(events(client, case)))

    client.post(f"/api/investigations/{case}/evidence/CALL-001/reprocess")
    process_latest_job(case, "CALL-001")

    after_events = events(client, case)
    assert (len(entities(client, case)), len(after_events)) == before
    assert any(e["added_manually"] for e in after_events)


def test_review_needs_verify_permission_and_is_audited(team):
    case = team["case"]
    upload(team["officer"], case, CALLS_CSV, "calls.csv", "call_records")
    process_latest_job(case, "CALL-001")
    event = events(team["officer"], case)[0]["reference"]
    url = f"/api/investigations/{case}/events/{event}/review"

    assert team["officer"].post(url, json={"review_status": "confirmed"}).status_code == 403
    ok = team["analyst"].post(url, json={"review_status": "rejected", "note": "Duplicate CDR row"})
    assert ok.status_code == 200 and ok.json()["review_status"] == "rejected"


def test_manual_entity_requires_existing_evidence(team):
    client, case = team["officer"], team["case"]
    missing = client.post(
        f"/api/investigations/{case}/entities",
        json={"entity_type": "person", "value": "Unknown Driver", "evidence_reference": "IMG-404"},
    )
    assert missing.status_code == 404


def test_entities_are_isolated_per_case(team, make_user):
    client, case = team["officer"], team["case"]
    other_case = create_case(client, title="Second case")["reference"]
    upload(client, case, CALLS_CSV, "calls.csv", "call_records")
    upload(client, other_case, CALLS_CSV, "calls.csv", "call_records")
    process_latest_job(case, "CALL-001")
    process_latest_job(other_case, "CALL-001")
    first = {e["reference"] for e in entities(client, case)}
    second = {e["reference"] for e in entities(client, other_case)}
    assert first == second  # numbered per case …
    detail = client.get(f"/api/investigations/{other_case}/entities/PH001").json()
    assert {m["evidence_reference"] for m in detail["mentions"]} == {"CALL-001"}  # … but separate

    outsider = signed_in(make_user("forensic_analyst"))
    assert outsider.get(f"/api/investigations/{case}/entities").status_code == 404


def test_investigation_counts_include_entities_and_events(team):
    client, case = team["officer"], team["case"]
    upload(client, case, CALLS_CSV, "calls.csv", "call_records")
    process_latest_job(case, "CALL-001")
    counts = client.get(f"/api/investigations/{case}").json()["counts"]
    assert counts == {"evidence": 1, "entities": 3, "events": 2, "correlations": 0}


def test_ocr_spacing_repair_and_name_filters():
    from app.extraction.nlp import PLATE, _plausible
    from app.extraction.text import repair_ocr_spacing

    assert repair_ocr_spacing("Name:AnitaShah") == "Name: Anita Shah"
    assert repair_ocr_spacing("night.supervisor@example.org") == "night.supervisor@example.org"
    assert PLATE.search("The number plate wasZZ99ZZ0001.").group() == "ZZ99ZZ0001"
    assert not _plausible("grey van", "person")  # a lower-case phrase is not a name
    assert _plausible("Anita Shah", "person")
    assert _plausible("Bank of India", "organization")


def test_names_never_run_onto_the_next_line():
    from unittest.mock import MagicMock

    from app.extraction import nlp

    recorded: list[tuple[str, str]] = []
    sink = MagicMock()
    sink.entity = lambda entity_type, raw, _provenance: recorded.append((entity_type, raw)) or 1
    nlp.extract_entities(sink, "Name: Anita Shah\nDate:29September2026\n", 0.97, "ocr")
    assert ("person", "Anita Shah") in recorded


def test_reprocessing_keeps_entity_references_stable(team):
    client, case = team["officer"], team["case"]
    upload(client, case, CALLS_CSV, "calls.csv", "call_records")
    process_latest_job(case, "CALL-001")
    before = sorted((e["reference"], e["label"]) for e in entities(client, case))
    client.post(f"/api/investigations/{case}/evidence/CALL-001/reprocess")
    process_latest_job(case, "CALL-001")
    assert sorted((e["reference"], e["label"]) for e in entities(client, case)) == before
