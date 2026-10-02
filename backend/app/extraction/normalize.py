"""Turn the many ways an identifier can be written into ONE matching key.

    "+1 (202) 555-0101", "+1-202-555-0101", "12025550101"  → "+12025550101"
    "zz99 zz 0001", "ZZ99-ZZ-0001"                           → "ZZ99ZZ0001"

Matching on the key is what lets FALCON notice that the same phone or vehicle appears in
two different evidence files. The label keeps a readable form for people.
"""

import re
from dataclasses import dataclass

import phonenumbers

from app.core.config import get_settings


@dataclass(frozen=True)
class Normalized:
    key: str
    label: str


_SPACES = re.compile(r"\s+")


def _collapse(text: str) -> str:
    return _SPACES.sub(" ", text).strip()


def phone(raw: str) -> Normalized | None:
    try:
        number = phonenumbers.parse(raw, get_settings().default_phone_region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_possible_number(number):
        return None
    return Normalized(
        key=phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164),
        label=phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
    )


def vehicle(raw: str) -> Normalized | None:
    key = re.sub(r"[^A-Z0-9]", "", raw.upper())
    if len(key) < 4 or not re.search(r"\d", key):
        return None
    return Normalized(key=key, label=_collapse(raw.upper()))


def identifier(raw: str) -> Normalized | None:
    """Devices, accounts, artefacts: case and spacing don't matter."""
    label = _collapse(raw)
    if len(label) < 2:
        return None
    return Normalized(key=label.upper().replace(" ", ""), label=label)


def email(raw: str) -> Normalized | None:
    label = raw.strip().lower()
    return Normalized(key=label, label=label) if "@" in label else None


def name(raw: str) -> Normalized | None:
    """People, organisations, places: same words → same key."""
    label = _collapse(raw.strip(" .,;:'\"()[]"))
    if len(label) < 2 or not re.search(r"[A-Za-z]", label):
        return None
    return Normalized(key=label.lower(), label=label)


NORMALIZERS = {
    "phone_number": phone,
    "vehicle": vehicle,
    "device": identifier,
    "account": identifier,
    "digital_artifact": identifier,
    "person": name,
    "organization": name,
    "location": name,
}


def normalize(entity_type: str, raw: str) -> Normalized | None:
    if not raw or not raw.strip():
        return None
    if entity_type == "account" and "@" in raw:
        return email(raw)
    return NORMALIZERS[entity_type](raw)
