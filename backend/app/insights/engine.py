"""FALCON insights: what the case data suggests an investigator should CHECK next.

Pure, like the correlation engine: plain data in, explained suggestions out, no database.
Every insight says what was seen, which records show it, and what to do about it. None of
them is a conclusion. The rules:

  CLOCK DRIFT     The same vehicle at the same spot is recorded by a camera with its own clock
                  (CCTV, photo) and by a network-timed source (ANPR, GPS, call records, bank):
                  the difference is probably the camera's clock error.
  SIGHTING GAP    A vehicle is not seen for a long time while it moved far: its route is unknown.
                  CCTV along the way is the evidence to ask for, before it is overwritten.
  WHO IS THIS?    Phone numbers in call records, UPI/bank accounts in payments and handset
                  IMEIs in location data have no known owner yet: ask the operator or bank.
  WAITING LEADS   High relationships nobody has reviewed.
  OTHER CASES     The same phone, vehicle, account or device in another investigation
                  (supplied by the service, which also hides cases the user may not open).
"""

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Clocks set by a network (GPS satellites, operator, bank, ANPR server) vs. a device's own.
NETWORK_CLOCK = {"vehicle", "gps", "call_records", "financial"}
LOCAL_CLOCK = {"video", "image"}
SAME_SPOT_M = 100.0  # two records this close are "the same place"
DRIFT_MIN_S = 30  # smaller differences are normal (rounding, a few seconds of movement)
DRIFT_MAX_S = 15 * 60  # bigger ones are probably two different visits, not a wrong clock
GAP_MIN_S = 15 * 60
GAP_MIN_M = 1000.0
MAX_PER_KIND = 3

SEVERITY_ORDER = {"high": 0, "medium": 1, "info": 2}


# ---------- Input ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EntityRef:
    reference: str
    entity_type: str
    label: str


@dataclass(frozen=True)
class EventInfo:
    reference: str
    evidence_reference: str
    evidence_type: str
    event_type: str
    occurred_at: datetime | None
    latitude: float | None
    longitude: float | None
    place: str
    participants: tuple[EntityRef, ...] = ()


@dataclass(frozen=True)
class CorrelationInfo:
    reference: str
    level: str
    review_status: str
    evidence_a: str
    evidence_b: str
    score: float


@dataclass(frozen=True)
class OtherCase:
    """The same entity in another investigation. reference None = the user may not open it."""

    entity: EntityRef
    reference: str | None
    title: str | None


@dataclass
class CaseFacts:
    time_zone: Any  # a ZoneInfo: times in explanations are written in the case's local time
    events: list[EventInfo] = field(default_factory=list)
    correlations: list[CorrelationInfo] = field(default_factory=list)
    other_cases: list[OtherCase] = field(default_factory=list)


# ---------- Output --------------------------------------------------------------------------


@dataclass
class Insight:
    key: str  # stable: the same finding keeps the same key between runs
    kind: str
    severity: str  # high | medium | info
    title: str
    detail: str
    action: str
    evidence: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    # A requisition letter that would get the missing evidence: kind + what to fill it with.
    letter: dict[str, Any] | None = None


def analyse(facts: CaseFacts) -> list[Insight]:
    found = (
        _other_cases(facts)
        + _clock_drift(facts)
        + _waiting_leads(facts)
        + _sighting_gaps(facts)
        + _unknown_owners(facts)
    )
    return sorted(found, key=lambda i: SEVERITY_ORDER[i.severity])


# ---------- Rules ---------------------------------------------------------------------------


def _other_cases(facts: CaseFacts) -> list[Insight]:
    insights = []
    hidden: dict[str, list[OtherCase]] = {}
    for hit in facts.other_cases:
        if hit.reference is None:
            hidden.setdefault(hit.entity.reference, []).append(hit)
            continue
        insights.append(
            Insight(
                key=f"other_case:{hit.entity.reference}:{hit.reference}",
                kind="other_case",
                severity="high",
                title=f"{hit.entity.label} also appears in {hit.reference}",
                detail=(
                    f"{_noun(hit.entity)} {hit.entity.label} ({hit.entity.reference}) is also "
                    f"recorded in {hit.reference} “{hit.title}”. The same identifier in two "
                    "cases may connect them, or may be a coincidence or a typing error."
                ),
                action=f"Open {hit.reference} and compare the records before linking the cases.",
                entities=[hit.entity.reference],
            )
        )
    for reference, hits in hidden.items():
        entity = hits[0].entity
        many = "investigation" if len(hits) == 1 else "investigations"
        insights.append(
            Insight(
                key=f"other_case:{reference}:restricted",
                kind="other_case",
                severity="high",
                title=f"{entity.label} appears in {len(hits)} other {many} you cannot open",
                detail=(
                    f"{_noun(entity)} {entity.label} is recorded in {len(hits)} {many} outside "
                    "your team. FALCON does not show which, or what they contain."
                ),
                action="Ask a supervisor to review the match. They can see every case.",
                entities=[reference],
            )
        )
    return insights


def _clock_drift(facts: CaseFacts) -> list[Insight]:
    offsets: dict[str, list[tuple[float, EventInfo, EventInfo, float]]] = {}
    network = [
        e for e in facts.events if e.evidence_type in NETWORK_CLOCK and _placed(e) and e.occurred_at
    ]
    for local in facts.events:
        if local.evidence_type not in LOCAL_CLOCK or not (_placed(local) and local.occurred_at):
            continue
        shared = {p.reference for p in local.participants}
        for other in network:
            if not shared & {p.reference for p in other.participants}:
                continue
            metres = distance_m(local, other)
            seconds = (local.occurred_at - other.occurred_at).total_seconds()
            if metres <= SAME_SPOT_M and DRIFT_MIN_S <= abs(seconds) <= DRIFT_MAX_S:
                offsets.setdefault(local.evidence_reference, []).append(
                    (seconds, local, other, metres)
                )

    insights = []
    for evidence, pairs in offsets.items():
        offset = statistics.median(p[0] for p in pairs)
        seconds, local, other, metres = min(pairs, key=lambda p: abs(p[0] - offset))
        thing = next(p for p in local.participants if p in other.participants)
        direction = "fast (ahead)" if offset > 0 else "slow (behind)"
        insights.append(
            Insight(
                key=f"clock_drift:{evidence}",
                kind="clock_drift",
                severity="high",
                title=f"{evidence}'s clock appears to run {_duration(abs(offset))} {direction}",
                detail=(
                    f"{thing.label} ({thing.reference}) was recorded at the same spot "
                    f"({_metres(metres)} apart) by {other.evidence_reference} at "
                    f"{_clock(other.occurred_at, facts)} and by {evidence} at "
                    f"{_clock(local.occurred_at, facts)}. {other.evidence_reference} takes its "
                    f"time from a network; {evidence} from its own clock. "
                    + (
                        f"{len(pairs)} matching records agree on this difference."
                        if len(pairs) > 1
                        else "Only one matching pair was found: confirm it before relying on it."
                    )
                ),
                action=(
                    f"Check {evidence}'s recorder clock against a reference time and note the "
                    f"offset in the case. Read {evidence}'s times about {_duration(abs(offset))} "
                    f"{'earlier' if offset > 0 else 'later'}. FALCON does not change the times."
                ),
                evidence=[evidence, other.evidence_reference],
                entities=[thing.reference],
            )
        )
    return insights


def _waiting_leads(facts: CaseFacts) -> list[Insight]:
    waiting = [c for c in facts.correlations if c.level == "high" and c.review_status == "pending"]
    return [
        Insight(
            key=f"waiting:{c.reference}",
            kind="waiting_lead",
            severity="high",
            title=f"{c.reference} is a High relationship nobody has reviewed",
            detail=(
                f"{c.evidence_a} and {c.evidence_b} score {c.score:.2f}. Until an analyst confirms "
                "or rejects it, reports show it as unreviewed."
            ),
            action=f"Open {c.reference}, check the supporting records and record a decision.",
            evidence=[c.evidence_a, c.evidence_b],
        )
        for c in waiting[:MAX_PER_KIND]
    ]


def _sighting_gaps(facts: CaseFacts) -> list[Insight]:
    sightings: dict[EntityRef, list[EventInfo]] = {}
    for event in facts.events:
        if not (_placed(event) and event.occurred_at):
            continue
        for p in event.participants:
            if p.entity_type == "vehicle":
                sightings.setdefault(p, []).append(event)

    insights = []
    for vehicle, events in sightings.items():
        events.sort(key=lambda e: e.occurred_at)
        gaps = [
            (b.occurred_at - a.occurred_at, a, b)
            for a, b in zip(events, events[1:], strict=False)
            if (b.occurred_at - a.occurred_at).total_seconds() >= GAP_MIN_S
            and distance_m(a, b) >= GAP_MIN_M
        ]
        if not gaps:
            continue
        gap, before, after = max(gaps, key=lambda g: g[0])
        hint = _other_tracks_in(facts, before, after, vehicle)
        insights.append(
            Insight(
                key=f"gap:{vehicle.reference}:{before.reference}",
                kind="sighting_gap",
                severity="medium",
                title=f"{vehicle.label} is not seen for {_duration(gap.total_seconds())}",
                detail=(
                    f"Last seen at {_where(before)} at {_clock(before.occurred_at, facts)} "
                    f"({before.evidence_reference}), next at {_where(after)} at "
                    f"{_clock(after.occurred_at, facts)} ({after.evidence_reference}), "
                    f"{_metres(distance_m(before, after))} away. Its route in between is unknown."
                    + hint
                ),
                action=(
                    "Ask shops, apartments and the municipality for CCTV between these two points "
                    "for this time window. Most recorders overwrite footage within 15–30 days."
                ),
                evidence=[before.evidence_reference, after.evidence_reference],
                entities=[vehicle.reference],
                letter={
                    "kind": "cctv_preservation",
                    "entity": vehicle.reference,
                    "from": before.occurred_at.isoformat(),
                    "to": after.occurred_at.isoformat(),
                    "places": [_where(before), _where(after)],
                },
            )
        )
    return insights


def _unknown_owners(facts: CaseFacts) -> list[Insight]:
    calls: dict[EntityRef, list[EventInfo]] = {}
    payments: dict[EntityRef, list[EventInfo]] = {}
    handsets: dict[EntityRef, list[EventInfo]] = {}
    for event in facts.events:
        for p in event.participants:
            if p.entity_type == "phone_number" and event.event_type in (
                "call_made",
                "message_sent",
            ):
                calls.setdefault(p, []).append(event)
            elif p.entity_type == "account" and event.event_type == "transaction_completed":
                payments.setdefault(p, []).append(event)
            elif p.entity_type == "device" and event.event_type == "location_recorded":
                handsets.setdefault(p, []).append(event)

    insights = []
    for phone, events in sorted(calls.items(), key=lambda kv: -len(kv[1]))[:MAX_PER_KIND]:
        partners = sorted(
            {
                q.label
                for e in events
                for q in e.participants
                if q != phone and q.entity_type == "phone_number"
            }
        )
        insights.append(
            Insight(
                key=f"owner:{phone.reference}",
                kind="unknown_owner",
                severity="medium",
                title=f"Who uses {phone.label}?",
                detail=(
                    f"{phone.reference} is in {len(events)} call{'s' if len(events) > 1 else ''}"
                    + (f" with {', '.join(partners)}" if partners else "")
                    + ", but no subscriber is known. The SIM's customer application form (CAF) "
                    "names who registered it."
                ),
                action="Request the subscriber details (CAF) and call records from the operator.",
                evidence=sorted({e.evidence_reference for e in events}),
                entities=[phone.reference],
                letter={"kind": "telecom_subscriber", "entity": phone.reference},
            )
        )
    for account, events in payments.items():
        insights.append(
            Insight(
                key=f"owner:{account.reference}",
                kind="unknown_owner",
                severity="medium",
                title=f"Whose account is {account.label}?",
                detail=(
                    f"{account.reference} made {_count(len(events), 'payment')} in this case. "
                    "The bank's KYC record gives the holder, the linked mobile number and the "
                    "full statement."
                ),
                action="Request KYC, the linked mobile number and the statement from the bank.",
                evidence=sorted({e.evidence_reference for e in events}),
                entities=[account.reference],
                letter={"kind": "bank_kyc", "entity": account.reference},
            )
        )
    for device, events in handsets.items():
        if not device.label.upper().startswith("IMEI"):
            continue
        insights.append(
            Insight(
                key=f"owner:{device.reference}",
                kind="unknown_owner",
                severity="medium",
                title=f"Which SIM was in handset {device.label}?",
                detail=(
                    f"{device.reference} has {len(events)} location records. An IMEI identifies "
                    "the handset, not the person: the operator can say which numbers used it."
                ),
                action="Request the IMEI-to-SIM history (numbers used in this handset).",
                evidence=sorted({e.evidence_reference for e in events}),
                entities=[device.reference],
                letter={"kind": "telecom_imei", "entity": device.reference},
            )
        )
    return insights


# ---------- Helpers -------------------------------------------------------------------------


def _other_tracks_in(facts: CaseFacts, before: EventInfo, after: EventInfo, vehicle) -> str:
    """Other located records in the gap may narrow the route down (a hint, not a finding)."""
    inside = [
        e
        for e in facts.events
        if _placed(e)
        and e.occurred_at
        and before.occurred_at < e.occurred_at < after.occurred_at
        and vehicle not in e.participants
    ]
    if not inside:
        return ""
    sources = sorted({e.evidence_reference for e in inside})
    return (
        f" {len(inside)} other located record{'s' if len(inside) > 1 else ''} fall in this "
        f"window ({', '.join(sources)}) and may help narrow the route."
    )


def _placed(e: EventInfo) -> bool:
    return e.latitude is not None and e.longitude is not None


def distance_m(a: EventInfo, b: EventInfo) -> float:
    """Great-circle distance (haversine), the same idea as the correlation engine."""
    la1, lo1, la2, lo2 = map(math.radians, (a.latitude, a.longitude, b.latitude, b.longitude))
    h = (
        math.sin((la2 - la1) / 2) ** 2
        + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    )
    return 2 * 6_371_008.8 * math.asin(math.sqrt(h))


def _clock(moment: datetime, facts: CaseFacts) -> str:
    return moment.astimezone(facts.time_zone).strftime("%H:%M:%S")


def _where(e: EventInfo) -> str:
    return e.place or f"{e.latitude:.4f}, {e.longitude:.4f}"


def _duration(seconds: float) -> str:
    seconds = round(seconds)
    if seconds < 60:
        return f"{seconds} s"
    minutes, rest = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} min {rest} s" if rest and minutes < 10 else f"{minutes} min"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min"


def _metres(metres: float) -> str:
    return f"{metres:.0f} m" if metres < 1000 else f"{metres / 1000:.1f} km"


def _count(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _noun(entity: EntityRef) -> str:
    return {
        "phone_number": "Phone number",
        "vehicle": "Vehicle",
        "account": "Account",
        "device": "Device",
        "person": "Person",
    }.get(entity.entity_type, "Entity")
