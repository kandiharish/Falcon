"""The FALCON correlation engine — pure, deterministic, explainable (plan §18–§19, §43).

Pure = no database, no web: plain data in, scored pairs out. Same input → same output.

For every pair of evidence items in a case, three independent factors:

    ENTITY    an entity (phone, vehicle, device…) appears in both     weight 0.45
    TIME      their events happened close together (≤ TIME_WINDOW)   weight 0.30
    LOCATION  their events happened close together (≤ RADIUS)        weight 0.25

    factor scores are 0–1 and fall off linearly:  time = 1 − Δt / window,  place = 1 − d / radius
    score = Σ weight × factor score        High ≥ 0.75 · Medium ≥ 0.50 · Low below

A pair is reported only if it shares an entity, or if at least two factors agree:
the same time alone is coincidence, not a relationship.
"""

import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

ALGORITHM = "falcon-correlation-v1"
WEIGHTS = {"entity": 0.45, "time": 0.30, "location": 0.25}
TIME_WINDOW_S = 30 * 60
RADIUS_M = 500.0
HIGH, MEDIUM = 0.75, 0.50
EARTH_RADIUS_M = 6_371_008.8  # mean Earth radius (the same idea as PostGIS geography)


# ---------- Input ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EventFact:
    id: uuid.UUID
    reference: str
    occurred_at: datetime | None
    latitude: float | None
    longitude: float | None


@dataclass(frozen=True)
class EntityFact:
    id: uuid.UUID
    reference: str
    label: str


@dataclass
class EvidenceFacts:
    id: uuid.UUID
    reference: str
    events: list[EventFact] = field(default_factory=list)
    # Entities that appear in this evidence, with the best confidence of their appearance.
    entities: dict[uuid.UUID, tuple[EntityFact, float]] = field(default_factory=dict)


# ---------- Output --------------------------------------------------------------------------


@dataclass
class Factor:
    kind: str  # entity | time | location
    score: float  # 0–1
    weight: float
    explanation: str
    details: dict[str, Any]

    @property
    def contribution(self) -> float:
        return round(self.score * self.weight, 4)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "score": round(self.score, 4),
            "weight": self.weight,
            "contribution": self.contribution,
            "explanation": self.explanation,
            "details": self.details,
        }


@dataclass
class PairResult:
    evidence_a: EvidenceFacts
    evidence_b: EvidenceFacts
    factors: list[Factor]

    @property
    def score(self) -> float:
        return round(min(1.0, sum(f.contribution for f in self.factors)), 4)

    @property
    def level(self) -> str:
        return level_for(self.score)


def level_for(score: float) -> str:
    return "high" if score >= HIGH else "medium" if score >= MEDIUM else "low"


# ---------- The engine ----------------------------------------------------------------------


def correlate(
    evidence: list[EvidenceFacts], describe_time=lambda t: t.isoformat()
) -> list[PairResult]:
    """All evidence pairs that qualify as potential relationships, strongest first.

    Inside the engine, evidence items and entities are numbered 0, 1, 2…: dictionary look-ups
    on small integers are far cheaper than on UUIDs (hashing a UUID runs Python code, and the
    inner loops do it millions of times on a big case). Sorting evidence by reference first
    makes a pair's canonical order simply (smaller number, larger number).
    """
    items = sorted(evidence, key=lambda e: e.reference)
    numbers: dict[uuid.UUID, int] = {}
    entities = [
        {numbers.setdefault(eid, len(numbers)): fact for eid, fact in item.entities.items()}
        for item in items
    ]
    proximity = _best_proximity(items)
    pairs = set(proximity) | _pairs_sharing_entities(entities)

    results: list[PairResult] = []
    for a_n, b_n in sorted(pairs):
        factors: list[Factor] = []
        entity = _entity_factor(entities[a_n], entities[b_n])
        if entity:
            factors.append(entity)
        best = proximity.get((a_n, b_n))
        if best:
            factors.extend(_proximity_factors(best, describe_time))
        positive = [f for f in factors if f.score > 0]
        if entity or len(positive) >= 2:
            results.append(PairResult(items[a_n], items[b_n], positive))
    return sorted(results, key=lambda r: -r.score)


def _pairs_sharing_entities(entities: list[dict[int, tuple]]) -> set[tuple[int, int]]:
    holders: dict[int, list[int]] = {}
    for n, held in enumerate(entities):
        for entity in held:
            holders.setdefault(entity, []).append(n)
    pairs: set[tuple[int, int]] = set()
    for owners in holders.values():  # owners are in ascending order already
        for i, a in enumerate(owners):
            for b in owners[i + 1 :]:
                pairs.add((a, b))
    return pairs


def _entity_factor(a: dict[int, tuple], b: dict[int, tuple]) -> Factor | None:
    shared = [(a[eid][0], min(a[eid][1], b[eid][1])) for eid in a.keys() & b.keys()]
    if not shared:
        return None
    shared.sort(key=lambda item: (-item[1], item[0].reference))
    best_entity, best_confidence = shared[0]
    names = ", ".join(f"{e.reference} ({e.label})" for e, _ in shared[:5])
    more = f" and {len(shared) - 5} more" if len(shared) > 5 else ""
    return Factor(
        kind="entity",
        score=best_confidence,
        weight=WEIGHTS["entity"],
        explanation=(
            f"Both evidence items contain {names}{more}. The weakest of the two sightings of "
            f"{best_entity.reference} has confidence {best_confidence:.2f}."
        ),
        details={
            "shared": [
                {"reference": e.reference, "label": e.label, "confidence": round(c, 3)}
                for e, c in shared
            ],
        },
    )


@dataclass
class _Proximity:
    event_a: EventFact
    event_b: EventFact
    seconds: float
    metres: float | None

    @property
    def time_score(self) -> float:
        return max(0.0, 1 - self.seconds / TIME_WINDOW_S)

    @property
    def place_score(self) -> float:
        return 0.0 if self.metres is None else max(0.0, 1 - self.metres / RADIUS_M)

    @property
    def strength(self) -> float:
        return WEIGHTS["time"] * self.time_score + WEIGHTS["location"] * self.place_score


def _best_proximity(items: list[EvidenceFacts]) -> dict[tuple[int, int], _Proximity]:
    """For each evidence pair (by position in `items`), the two events closest in time AND place.

    Sweep-line: sort all timed events once, then compare each event only with the events that
    follow it within the time window — not every event with every other (n log n, not n²).
    """
    # Performance (measured on 6,000 events: 13.9 s → see docs/learning/phase-12.md):
    #  • work on plain numbers: timestamp, radians and cos(latitude) computed ONCE per event,
    #    not once per pair;
    #  • walk forward by index (a slice `timed[i+1:]` would copy the list for every event);
    #  • build a _Proximity object only for the pair that is currently the best.
    timed = sorted(
        (
            (
                event.occurred_at.timestamp(),  # type: ignore[union-attr]
                n,
                event,
                *_radians(event),
            )
            for n, item in enumerate(items)
            for event in item.events
            if event.occurred_at
        ),
        key=lambda row: row[0],
    )
    w_time, w_place = WEIGHTS["time"], WEIGHTS["location"]
    strongest: dict[tuple[int, int], float] = {}
    best: dict[tuple[int, int], tuple[EventFact, EventFact, float, float | None]] = {}
    count = len(timed)
    for i in range(count):
        t_a, item_a, event_a, lat_a, lon_a, cos_a = timed[i]
        j = i + 1
        while j < count:
            t_b, item_b, event_b, lat_b, lon_b, cos_b = timed[j]
            j += 1
            seconds = t_b - t_a
            if seconds > TIME_WINDOW_S:
                break  # sorted by time: every later event is even further away
            if item_a == item_b:
                continue
            metres = None
            if lat_a is not None and lat_b is not None:
                h = (
                    math.sin((lat_b - lat_a) / 2) ** 2
                    + cos_a * cos_b * math.sin((lon_b - lon_a) / 2) ** 2
                )
                metres = 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))
            place = 0.0 if metres is None else max(0.0, 1 - metres / RADIUS_M)
            strength = w_time * (1 - seconds / TIME_WINDOW_S) + w_place * place
            key = (item_a, item_b) if item_a < item_b else (item_b, item_a)
            if strength > strongest.get(key, -1.0):
                strongest[key] = strength
                best[key] = (event_a, event_b, seconds, metres)
    return {key: _Proximity(*value) for key, value in best.items()}


def _radians(event: EventFact) -> tuple[float | None, float | None, float]:
    if event.latitude is None or event.longitude is None:
        return None, None, 0.0
    lat = math.radians(event.latitude)
    return lat, math.radians(event.longitude), math.cos(lat)


def _proximity_factors(p: _Proximity, describe_time) -> list[Factor]:
    gap = _human_seconds(p.seconds)
    events = {
        "event_a": p.event_a.reference,
        "event_b": p.event_b.reference,
        # Always UTC: the same moment must always be written the same way, or re-runs would
        # see "changes" that are only different spellings of one time.
        "time_a": _utc_iso(p.event_a.occurred_at),
        "time_b": _utc_iso(p.event_b.occurred_at),
    }
    factors = [
        Factor(
            kind="time",
            score=p.time_score,
            weight=WEIGHTS["time"],
            explanation=(
                f"{p.event_a.reference} ({describe_time(p.event_a.occurred_at)}) and "
                f"{p.event_b.reference} ({describe_time(p.event_b.occurred_at)}) are {gap} apart "
                f"(considered close up to {TIME_WINDOW_S // 60} minutes)."
            ),
            details={**events, "seconds_apart": round(p.seconds), "window_seconds": TIME_WINDOW_S},
        )
    ]
    if p.metres is not None:
        factors.append(
            Factor(
                kind="location",
                score=p.place_score,
                weight=WEIGHTS["location"],
                explanation=(
                    f"{p.event_a.reference} and {p.event_b.reference} took place "
                    f"{_human_metres(p.metres)} apart (considered close up to {RADIUS_M:.0f} m)."
                ),
                details={**events, "metres_apart": round(p.metres), "radius_metres": RADIUS_M},
            )
        )
    return factors


def _metres(a: EventFact, b: EventFact) -> float | None:
    """Great-circle distance (haversine) — the same idea as PostGIS geography distance."""
    if None in (a.latitude, a.longitude, b.latitude, b.longitude):
        return None
    lat1, lat2 = math.radians(a.latitude), math.radians(b.latitude)  # type: ignore[arg-type]
    d_lat = lat2 - lat1
    d_lon = math.radians(b.longitude - a.longitude)  # type: ignore[operator]
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def _human_seconds(seconds: float) -> str:
    seconds = round(seconds)
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    minutes, rest = divmod(seconds, 60)
    return f"{minutes} min {rest} s" if rest else f"{minutes} min"


def _human_metres(metres: float) -> str:
    return f"{metres / 1000:.2f} km" if metres >= 1000 else f"{round(metres)} m"


def _utc_iso(moment: datetime | None) -> str | None:
    return moment.astimezone(UTC).isoformat() if moment else None
