"""Draft requisition letters for the evidence an insight says is missing.

Officers write these by hand for every phone number, account and camera: the same facts typed
again and again (case, number, period, legal basis). FALCON fills them from the case record.
Legal basis: Section 94 of the Bharatiya Nagarik Suraksha Sanhita, 2023 (summons to produce a
document or other thing; formerly Section 91 CrPC). The officer checks and signs.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.documents.draft import BLANK, DraftDocument, Section

LETTER_KINDS = ("telecom_subscriber", "telecom_imei", "bank_kyc", "cctv_preservation")
LEGAL_BASIS = "Section 94 of the Bharatiya Nagarik Suraksha Sanhita, 2023"


@dataclass(frozen=True)
class LetterFacts:
    kind: str
    case_reference: str
    case_title: str
    case_type: str
    case_location: str
    time_zone: str
    officer: str
    entity_reference: str
    entity_label: str
    # The period the records should cover: the case's own records involving the entity,
    # widened to whole days (operators and banks answer per day).
    first_seen: datetime | None
    last_seen: datetime | None
    places: tuple[str, ...] = ()
    today: datetime | None = None


def requisition(facts: LetterFacts) -> DraftDocument:
    zone = ZoneInfo(facts.time_zone)
    day = "%d/%m/%Y"

    def local(moment: datetime | None, fmt: str = day) -> str:
        return moment.astimezone(zone).strftime(fmt) if moment else BLANK

    start = facts.first_seen - timedelta(days=3) if facts.first_seen else None
    end = facts.last_seen + timedelta(days=1) if facts.last_seen else None
    period = f"{local(start)} to {local(end)}"
    opening = (
        f"In connection with the investigation of “{facts.case_title}” ({facts.case_reference}, "
        f"{facts.case_type}) at {facts.case_location or BLANK}, you are requested under "
        f"{LEGAL_BASIS} to furnish the following at the earliest:"
    )
    certificate = (
        "A certificate under Section 63 of the Bharatiya Sakshya Adhiniyam, 2023 for the "
        "electronic records furnished, stating their HASH value."
    )
    builders = {
        "telecom_subscriber": (
            "The Nodal Officer, telecom service provider of the number below",
            f"Subscriber details and call detail records of {facts.entity_label}",
            [
                f"Subscriber details of mobile number {facts.entity_label}, with a copy of the "
                "customer application form (CAF) and the identity and address proof submitted.",
                f"Call detail records with cell-site location and IMEI for the period {period}.",
                certificate,
            ],
        ),
        "telecom_imei": (
            "The Nodal Officer, telecom service providers",
            f"Numbers used in handset {facts.entity_label}",
            [
                f"All mobile numbers (SIMs) used in the handset with {facts.entity_label} "
                f"during {period}, with subscriber details of each.",
                f"Call detail records with cell-site location for those numbers, {period}.",
                certificate,
            ],
        ),
        "bank_kyc": (
            "The Nodal Officer, bank / payment service provider of the account below",
            f"KYC, linked mobile number and statement of {facts.entity_label}",
            [
                f"KYC details of the holder of {facts.entity_label}, with the identity and "
                "address proof submitted.",
                "The mobile number(s) and device details linked to the account or UPI ID.",
                f"The account statement for {period}, with the IP addresses and device IDs of "
                "the transactions.",
                certificate,
            ],
        ),
        "cctv_preservation": (
            "The owner / manager of the premises, and the CCTV control room (Traffic Police / "
            "GHMC), for cameras on the route below",
            f"Preservation and copy of CCTV footage: {facts.entity_label}",
            [
                "Do not overwrite or delete the CCTV recordings of cameras covering the route "
                f"between {' and '.join(facts.places) or BLANK} on "
                f"{local(facts.first_seen)}, from {local(facts.first_seen, '%H:%M')} to "
                f"{local(facts.last_seen, '%H:%M')}.",
                "Provide a copy of that footage on write-once media, with the recorder's make, "
                "model and the difference between its clock and the actual time.",
                certificate,
            ],
        ),
    }
    to, subject, items = builders[facts.kind]
    return DraftDocument(
        kind=facts.kind,
        title="REQUISITION",
        subtitle=f"Under {LEGAL_BASIS}",
        reference=f"{facts.case_reference} · {facts.entity_reference} · dated {local(facts.today)}",
        notice=(
            "DRAFT prepared by FALCON from the case record. Check the recipient, the period "
            "and the details, then issue it on letterhead with your department's number."
        ),
        sections=[
            Section(fields=[("To", to), ("Subject", subject), ("Reference", facts.case_reference)]),
            Section(paragraphs=["Sir / Madam,", opening], items=items),
            Section(
                paragraphs=[
                    "The information is required for the investigation and will be kept "
                    "confidential. Kindly treat this as urgent."
                ],
                signatures=[f"{facts.officer}\nInvestigating Officer"],
            ),
        ],
        to_check=[
            "The exact recipient (operator, bank or premises) and its address.",
            "The period requested, and whether a longer one is justified.",
            "Your department's letter number and seal.",
        ],
    )
