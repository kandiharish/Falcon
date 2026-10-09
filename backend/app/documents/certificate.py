"""Draft certificate for an electronic record under Section 63 of the Bharatiya Sakshya
Adhiniyam, 2023 (which replaced Section 65B of the Indian Evidence Act from 1 July 2024).

Courts admit an electronic record (a CCTV export, call records, a phone photo) with a
certificate in the format of the Act's Schedule: Part A by the person producing the record,
Part B by an expert. Both state the record's HASH value — which FALCON computed at upload and
re-checks — so FALCON can pre-fill most of it. The officer and the expert check, complete and
sign it; FALCON never signs.
"""

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from app.documents.draft import BLANK, DraftDocument, Section

# What kind of device or system each evidence type usually comes from (the Schedule asks).
SOURCE_DEVICE = {
    "video": "DVR / NVR (CCTV recorder)",
    "image": "Mobile phone or camera",
    "gps": "Server (location data provider)",
    "call_records": "Server (telecom operator)",
    "financial": "Server (bank / payment system)",
    "vehicle": "Server (ANPR / traffic camera system)",
    "document": "Computer / storage media",
    "witness_statement": "Scanner / computer",
    "device_metadata": "Computer / storage media",
    "digital_file": "Computer / storage media",
}


@dataclass(frozen=True)
class RecordFacts:
    case_reference: str
    case_title: str
    time_zone: str
    evidence_reference: str
    evidence_type: str
    description: str
    source: str
    original_filename: str
    media_type: str
    size_bytes: int
    sha256: str
    collected_at: datetime | None
    uploaded_at: datetime
    uploaded_by: str
    integrity_checked_at: datetime | None
    integrity_ok: bool | None
    make_model: str  # from the file's own metadata, if it has any
    custody: list[tuple[datetime, str, str]]  # (when, who, what), oldest first


def section_63(record: RecordFacts) -> DraftDocument:
    zone = ZoneInfo(record.time_zone)

    def when(moment: datetime | None) -> str:
        return moment.astimezone(zone).strftime("%d/%m/%Y %H:%M") if moment else BLANK

    device = SOURCE_DEVICE.get(record.evidence_type, "Other")
    verified = (
        f"matched on {when(record.integrity_checked_at)}"
        if record.integrity_ok
        else "NOT VERIFIED: re-check before certifying"
    )
    hash_statement = (
        f"I state that the HASH value of the electronic/digital record is {record.sha256}, "
        "obtained through the following algorithm: SHA-256."
    )
    record_fields = [
        ("Electronic record", f"{record.evidence_reference}: {record.description}"),
        ("File", f"{record.original_filename} ({record.media_type}, {record.size_bytes:,} bytes)"),
        ("Source", record.source or BLANK),
        ("Device / record source", device),
        ("Make and model", record.make_model or BLANK),
        ("Serial number / IMEI / UID / MAC / cloud ID", BLANK),
        ("Collected", when(record.collected_at)),
        ("HASH algorithm", "SHA-256"),
        ("HASH value", record.sha256),
    ]
    return DraftDocument(
        kind="section_63_certificate",
        title="CERTIFICATE UNDER SECTION 63(4)(c) OF THE BHARATIYA SAKSHYA ADHINIYAM, 2023",
        subtitle="Electronic record: certificate in the format of the Schedule (Parts A and B)",
        reference=f"{record.case_reference} · {record.evidence_reference} · {record.case_title}",
        notice=(
            "DRAFT prepared by FALCON from the case record. Compare it with the Schedule to the "
            "Bharatiya Sakshya Adhiniyam, 2023 and your department's format, complete the blanks, "
            "and sign only what you can personally state. FALCON does not certify anything."
        ),
        sections=[
            Section(heading="The electronic record", fields=record_fields),
            Section(
                heading="Part A: to be filled by the party producing the record",
                paragraphs=[
                    f"I, {BLANK} (name), {BLANK} (designation), employed at {BLANK}, do hereby "
                    "solemnly affirm and sincerely state and submit as follows:",
                    f"I have produced the electronic record/output of the digital record taken "
                    f"from the following device/digital record source: {device}; "
                    f"make and model: {record.make_model or BLANK}; "
                    f"serial number / IMEI / UID / MAC / cloud ID: {BLANK}.",
                    "The digital device or the digital record source was under lawful control for "
                    "regularly creating, storing or processing information for the purposes of "
                    "carrying out regular activities, and during this period it was working "
                    "properly and the relevant information was regularly fed into it in the "
                    "ordinary course of business. If at any point it was not working properly or "
                    "was out of operation, that has not affected the electronic/digital record "
                    "or its accuracy.",
                    hash_statement,
                ],
                fields=[("Date (DD/MM/YYYY)", BLANK), ("Time (IST)", BLANK), ("Place", BLANK)],
                signatures=["Name and signature"],
            ),
            Section(
                heading="Part B: to be filled by the expert",
                paragraphs=[
                    f"I, {BLANK} (name), {BLANK} (designation), do hereby solemnly affirm and "
                    "sincerely state and submit as follows:",
                    "The produced electronic record/output of the digital record was obtained from "
                    f"the following device/digital record source: {device}.",
                    hash_statement,
                ],
                fields=[("Date (DD/MM/YYYY)", BLANK), ("Time (IST)", BLANK), ("Place", BLANK)],
                signatures=["Name, designation and signature"],
            ),
            Section(
                heading="From the FALCON record (supporting information)",
                fields=[
                    ("Received into FALCON", f"{when(record.uploaded_at)} by {record.uploaded_by}"),
                    ("Original stored", "read-only, unchanged since receipt"),
                    ("Last integrity check", verified),
                ],
                items=[f"{when(at)}  {who}: {what}" for at, who, what in record.custody],
            ),
        ],
        to_check=[
            "Name, designation and place of the person producing the record (Part A).",
            "The device's serial number, IMEI, UID, MAC address or cloud ID.",
            "That the HASH value above matches a fresh computation by the expert (Part B).",
            "That the record source was working properly over the relevant period.",
        ],
    )
