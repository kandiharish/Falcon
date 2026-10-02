"""Find entities in free text: phones, emails, vehicle plates, people, organisations, places.

Two kinds of detectors:
  • Patterns (phone numbers via Google's libphonenumber, emails, plates): precise rules.
  • spaCy's statistical model (en_core_web_sm) for names: useful, but it makes mistakes —
    e.g. it may call a street name a person. So these are labelled DETECTED with modest
    confidence and always need human review. The model never "decides" anything.
"""

import re

import phonenumbers

from app.core.config import get_settings
from app.extraction.sink import ExtractionSink, Provenance

MAX_CHARS = 200_000
CONTEXT_CHARS = 60

EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# Registration plates in the common Indian layout, e.g. "TS09 AB 1234".
# (The fictional demo uses the non-existent state code ZZ: "ZZ99 ZZ 0001".)
# "Not preceded/followed by a capital or digit" instead of a word boundary, so plates are also
# found in OCR text where a space went missing ("wasZZ99ZZ0001").
PLATE = re.compile(r"(?<![A-Z0-9])[A-Z]{2}[ -]?\d{1,2}[ -]?[A-Z]{1,3}[ -]?\d{4}(?![A-Z0-9])")

SPACY_TYPES = {
    "PERSON": ("person", 0.6),
    "ORG": ("organization", 0.5),
    "GPE": ("location", 0.5),
    "LOC": ("location", 0.5),
    "FAC": ("location", 0.45),
}
SPACY_MODEL = "en_core_web_sm"
# Small words allowed in lower case inside names ("Bank of India", "van der Berg").
_NAME_PARTICLES = {"of", "the", "and", "de", "da", "van", "von", "der", "bin", "al"}
_nlp = None


def extract_entities(sink: ExtractionSink, text: str, text_confidence: float, method: str) -> int:
    """Run every detector over `text`; returns how many mentions were recorded."""
    text = text[:MAX_CHARS]
    taken: list[tuple[int, int]] = []  # spans already claimed by a precise pattern
    found = 0

    def record(entity_type: str, raw: str, start: int, end: int, confidence: float, how: str):
        nonlocal found
        provenance = Provenance(
            assertion="detected",
            confidence=confidence * text_confidence,
            extractor=f"{how}{'+ocr' if 'ocr' in method else ''}",
            source_location=f"characters {start}–{end}",
            context=_context(text, start, end),
        )
        if sink.entity(entity_type, raw, provenance) is not None:
            found += 1
            taken.append((start, end))

    region = get_settings().default_phone_region
    for match in phonenumbers.PhoneNumberMatcher(text, region):
        record("phone_number", match.raw_string, match.start, match.end, 0.9, "pattern:phone")
    for match in EMAIL.finditer(text):
        record("account", match.group(), match.start(), match.end(), 0.9, "pattern:email")
    for match in PLATE.finditer(text):
        if not _overlaps(match.start(), match.end(), taken):
            record("vehicle", match.group(), match.start(), match.end(), 0.7, "pattern:plate")

    for ent in _model()(text).ents:
        mapped = SPACY_TYPES.get(ent.label_)
        if not mapped:
            continue
        # A name never continues onto the next line; the model sometimes runs past it.
        start = ent.start_char
        end = start + len(ent.text.split("\n", 1)[0].rstrip())
        name = text[start:end]
        if _overlaps(start, end, taken):
            continue
        entity_type, confidence = mapped
        if not _plausible(name, entity_type):
            continue
        if entity_type == "person" and len(name.split()) == 1:
            confidence = 0.4  # a single first name is weak evidence of who someone is
        record(entity_type, name, start, end, confidence, f"spacy:{SPACY_MODEL}")
    return found


def _model():
    global _nlp
    if _nlp is None:
        import spacy

        # Only the named-entity recogniser is needed: disabling the rest makes it faster.
        _nlp = spacy.load(SPACY_MODEL, disable=["lemmatizer", "attribute_ruler"])
    return _nlp


def _plausible(text: str, entity_type: str) -> bool:
    cleaned = text.strip()
    if len(cleaned) < 3 or not re.search(r"[A-Za-z]{2}", cleaned) or "\n" in cleaned:
        return False
    if entity_type == "person" and any(ch.isdigit() for ch in cleaned):
        return False
    # Names of people, organisations and places are written with capitals. The small model
    # sometimes tags ordinary phrases ("grey van") as a person; requiring a capital on every
    # word removes most of those mistakes.
    words = [w for w in re.split(r"[\s-]+", cleaned) if w and w.lower() not in _NAME_PARTICLES]
    return bool(words) and all(w[0].isupper() for w in words)


def _overlaps(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(start < s_end and s_start < end for s_start, s_end in spans)


def _context(text: str, start: int, end: int) -> str:
    before = text[max(0, start - CONTEXT_CHARS) : start]
    after = text[end : end + CONTEXT_CHARS]
    return " ".join(f"…{before}[{text[start:end]}]{after}…".split())
