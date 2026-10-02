"""Natural-language search, step 1: QUESTION → SEARCH PLAN (structured filters).

"Show communications involving P001 between 8 PM and 10 PM"
    │  the LLM (or, without AI, simple rules) fills in this form ↓
    ▼
SearchPlan(intent="events", entity_refs=["P001"], event_types=["call_made", …],
           time_from="20:00", time_to="22:00")
    │  validate(): unknown IDs dropped, types checked — never trust a model's output
    ▼
our own database code runs the plan (nl_search_service). The model never sees the
database and never writes the answer, so it cannot invent evidence.
"""

import re
from dataclasses import dataclass
from datetime import date, time
from typing import Literal

from pydantic import BaseModel, Field

from app.models.evidence import EVIDENCE_TYPES
from app.models.extraction import ENTITY_TYPES, EVENT_TYPES

Intent = Literal["events", "evidence", "entities", "connection", "text"]
REFERENCE = re.compile(r"\b(?:[A-Z]{1,4}\d{3}|[A-Z]{2,5}-\d{3})\b")


class SearchPlan(BaseModel):
    intent: Intent = Field(
        description="events = things that happened; evidence = files; entities = people, "
        "phones, vehicles…; connection = how two items are linked; text = find passages "
        "about a topic in documents"
    )
    entity_refs: list[str] = Field(default_factory=list, description="IDs like P001, V001")
    evidence_refs: list[str] = Field(default_factory=list, description="IDs like CCTV-001")
    event_types: list[str] = Field(default_factory=list)
    evidence_types: list[str] = Field(default_factory=list)
    entity_types: list[str] = Field(default_factory=list)
    date_from: str | None = Field(None, description="YYYY-MM-DD")
    date_to: str | None = Field(None, description="YYYY-MM-DD")
    time_from: str | None = Field(None, description="HH:MM, 24-hour, time of day")
    time_to: str | None = Field(None, description="HH:MM, 24-hour, time of day")
    text: str | None = Field(None, description="topic words to look for in documents")


@dataclass
class CaseVocabulary:
    """What exists in THIS case — the only IDs a plan may use."""

    entities: dict[str, tuple[str, str]]  # reference → (type, label)
    evidence: dict[str, tuple[str, str]]  # reference → (type, description)
    time_zone: str
    today: date


COMMUNICATION = ["call_made", "message_sent", "communication"]
KEYWORDS: list[tuple[re.Pattern[str], str, list[str]]] = [
    (
        re.compile(r"\b(call|calls|called|phoned|communicat\w*|message\w*|sms)\b"),
        "event",
        COMMUNICATION,
    ),
    (
        re.compile(r"\b(payment|paid|transaction\w*|purchase\w*|bought)\b"),
        "event",
        ["transaction_completed"],
    ),
    (
        re.compile(r"\b(seen|sighting\w*|detected|camera|anpr|plate)\b"),
        "event",
        ["vehicle_detected", "person_detected"],
    ),
    (re.compile(r"\b(location\w*|gps|movement\w*|where)\b"), "event", ["location_recorded"]),
    (re.compile(r"\b(cctv|video\w*)\b"), "evidence", ["video"]),
    (re.compile(r"\b(photo\w*|image\w*|picture\w*)\b"), "evidence", ["image"]),
    (re.compile(r"\b(witness\w*|statement\w*)\b"), "evidence", ["witness_statement"]),
    (re.compile(r"\b(document\w*|report\w*)\b"), "evidence", ["document"]),
]
TIME = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", re.IGNORECASE)
BETWEEN = re.compile(r"between\s+([\d:apm\s.]+?)\s+(?:and|to)\s+([\d:apm\s.]+)", re.IGNORECASE)


def rules_plan(question: str, vocab: CaseVocabulary) -> SearchPlan:
    """No-AI fallback: IDs, keywords and "between X and Y". Simple, predictable, limited."""
    lower = question.lower()
    refs = REFERENCE.findall(question.upper()) + named_entities(question, vocab)
    entity_refs = [r for r in refs if r in vocab.entities]
    evidence_refs = [r for r in refs if r in vocab.evidence]
    event_types: list[str] = []
    evidence_types: list[str] = []
    for pattern, kind, values in KEYWORDS:
        if pattern.search(lower):
            (event_types if kind == "event" else evidence_types).extend(values)
    time_from = time_to = None
    if match := BETWEEN.search(question):
        time_from, time_to = _clock(match.group(1)), _clock(match.group(2))
    if re.search(r"\b(link|linked|connect\w*|relationship\w*|related)\b", lower) and (
        len(entity_refs) + len(evidence_refs) >= 2
    ):
        intent: Intent = "connection"
    elif re.search(r"\bevidence\b", lower) or (evidence_types and not event_types):
        intent = "evidence"
    elif event_types or time_from or re.search(r"\bevent", lower):
        intent = "events"
    elif entity_refs or evidence_refs:
        intent = "evidence"
    else:
        intent = "text"
    return SearchPlan(
        intent=intent,
        entity_refs=entity_refs,
        evidence_refs=evidence_refs,
        event_types=sorted(set(event_types)),
        evidence_types=sorted(set(evidence_types)),
        time_from=time_from,
        time_to=time_to,
        text=question if intent == "text" else None,
    )


def _squash(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def named_entities(question: str, vocab: CaseVocabulary) -> list[str]:
    """Entities whose label is written in the question: "the van ZZ99 ZZ 0001" → V001.
    Compared without spaces and punctuation, so "+1 202-555-0101" matches "12025550101".
    Short labels are skipped: "Ali" would match too much."""
    squashed = _squash(question)
    return [
        ref
        for ref, (_kind, label) in vocab.entities.items()
        if len(_squash(label)) >= 6 and _squash(label) in squashed
    ]


def _clock(raw: str) -> str | None:
    match = TIME.search(raw.strip())
    if not match:
        return None
    hour, minute, half = int(match.group(1)), int(match.group(2) or 0), (match.group(3) or "")
    if half.lower() == "pm" and hour < 12:
        hour += 12
    if half.lower() == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}" if hour < 24 and minute < 60 else None


def system_prompt(vocab: CaseVocabulary) -> str:
    entities = "\n".join(
        f"- {ref}: {kind}, {label}" for ref, (kind, label) in list(vocab.entities.items())[:200]
    )
    evidence = "\n".join(
        f"- {ref}: {kind}, {desc}" for ref, (kind, desc) in list(vocab.evidence.items())[:200]
    )
    return f"""You turn an investigator's question into search filters for ONE investigation.
Fill in the JSON form. Use ONLY the IDs listed below. Leave a field empty when the question
does not mention it. Never invent IDs. Times are time of day in {vocab.time_zone}.
Today is {vocab.today.isoformat()}.

intent:
- "events" for things that happened (calls, payments, sightings, movements), also time ranges
- "evidence" for files/evidence items, e.g. "which evidence involves V001"
- "entities" for people, phones, vehicles, devices, accounts, organisations, locations
- "connection" for how two IDs are linked ("relationship between P001 and D001")
- "text" for a topic to look for inside documents ("anything about a grey van")

Event types: {", ".join(EVENT_TYPES)}
Evidence types: {", ".join(EVIDENCE_TYPES)}
Entity types: {", ".join(ENTITY_TYPES)}
"Communications" = call_made, message_sent, communication.
Match names and numbers to IDs: "the van ZZ99 ZZ 0001" → its vehicle ID.

Entities in this case:
{entities or "- (none yet)"}

Evidence in this case:
{evidence or "- (none yet)"}

Examples:
"Show events between 8 PM and 10 PM" → intent events, time_from 20:00, time_to 22:00
"Show all communications involving P001" → intent events, entity_refs [P001],
  event_types [call_made, message_sent, communication]
"Find relationships between P001 and D001" → intent connection, entity_refs [P001, D001]
"Which evidence is connected to vehicle V001?" → intent evidence, entity_refs [V001]"""


def validate(
    plan: SearchPlan, vocab: CaseVocabulary, question: str
) -> tuple[SearchPlan, list[str]]:
    """Keep only what exists and makes sense; explain everything that was dropped."""
    notes: list[str] = []
    # Every ID — from the model's two lists, or typed by the user (always counts, even if the
    # model missed it) — is sorted by what it really is in this case. Unknown IDs are dropped.
    candidates = (
        plan.entity_refs
        + plan.evidence_refs
        + REFERENCE.findall(question.upper())
        + named_entities(question, vocab)
    )
    entity_refs: list[str] = []
    evidence_refs: list[str] = []
    for ref in dict.fromkeys(r.strip().upper() for r in candidates if r and r.strip()):
        if ref in vocab.entities:
            entity_refs.append(ref)
        elif ref in vocab.evidence:
            evidence_refs.append(ref)
        else:
            notes.append(f"{ref} is not in this investigation, so it was ignored.")

    def allowed(values: list[str], options: tuple[str, ...]) -> list[str]:
        return [v for v in dict.fromkeys(values) if v in options]

    clean = plan.model_copy(
        update={
            "entity_refs": entity_refs,
            "evidence_refs": evidence_refs,
            "event_types": allowed(plan.event_types, EVENT_TYPES),
            "evidence_types": allowed(plan.evidence_types, EVIDENCE_TYPES),
            "entity_types": allowed(plan.entity_types, ENTITY_TYPES),
            "date_from": _date_or_none(plan.date_from, notes),
            "date_to": _date_or_none(plan.date_to, notes),
            "time_from": _time_or_none(plan.time_from, notes),
            "time_to": _time_or_none(plan.time_to, notes),
            "text": (plan.text or "").strip()[:300] or None,
        }
    )
    if clean.intent == "connection" and len(clean.entity_refs) + len(clean.evidence_refs) < 2:
        notes.append("A connection needs two known IDs; showing evidence instead.")
        clean.intent = "evidence"
    if clean.intent == "text" and not clean.text:
        clean.text = question
    return clean, notes


def _date_or_none(value: str | None, notes: list[str]) -> str | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        notes.append(f"Could not read the date “{value}”.")
        return None


def _time_or_none(value: str | None, notes: list[str]) -> str | None:
    if not value:
        return None
    if value.strip() in ("24:00", "24:00:00"):  # "until midnight"
        return "23:59"
    try:
        return time.fromisoformat(value).strftime("%H:%M")
    except ValueError:
        notes.append(f"Could not read the time “{value}”.")
        return None


INTENT_WORDS = {
    "events": "events",
    "evidence": "evidence items",
    "entities": "entities",
    "connection": "the chain of links",
    "text": "document passages",
}


def describe(plan: SearchPlan) -> str:
    """The plan in plain words, written by code (so it always says exactly what was searched)."""
    parts = [f"Showing {INTENT_WORDS[plan.intent]}"]
    refs = plan.entity_refs + plan.evidence_refs
    if plan.intent == "connection" and len(refs) >= 2:
        parts = [f"Showing the chain of links between {refs[0]} and {refs[1]}"]
    elif refs:
        parts.append(f"involving {', '.join(refs)}")
    if plan.event_types:
        parts.append(f"of type {', '.join(t.replace('_', ' ') for t in plan.event_types)}")
    if plan.evidence_types:
        parts.append(f"from {', '.join(t.replace('_', ' ') for t in plan.evidence_types)} evidence")
    if plan.entity_types:
        parts.append(f"limited to {', '.join(t.replace('_', ' ') for t in plan.entity_types)}")
    if plan.date_from or plan.date_to:
        parts.append(f"dated {plan.date_from or '…'} to {plan.date_to or '…'}")
    if plan.time_from or plan.time_to:
        parts.append(f"between {plan.time_from or '00:00'} and {plan.time_to or '23:59'}")
    if plan.text:
        parts.append(f"with passages about “{plan.text}”")
    return " ".join(parts) + "."
