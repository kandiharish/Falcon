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
    """All evidence pairs that qualify as potential relationships, strongest first."""
    by_id = {e.id: e for e in evidence}
    proximity = _best_proximity(evidence)
    pairs = set(proximity) | _pairs_sharing_entities(evidence)

    results: list[PairResult] = []
    for a_id, b_id in sorted(pairs, key=lambda p: (by_id[p[0]].reference, by_id[p[1]].reference)):
        a, b = by_id[a_id], by_id[b_id]
        factors: list[Factor] = []
        entity = _entity_factor(a, b)
        if entity:
            factors.append(entity)
        best = proximity.get((a_id, b_id))
        if best:
            factors.extend(_proximity_factors(best, describe_time))
        positive = [f for f in factors if f.score > 0]
        if entity or len(positive) >= 2:
            results.append(PairResult(a, b, positive))
    return sorted(results, key=lambda r: -r.score)


def _ordered(a: EvidenceFacts, b: EvidenceFacts) -> tuple[uuid.UUID, uuid.UUID]:
    """Each pair has ONE canonical order, so (A,B) and (B,A) are the same correlation."""
    return (a.id, b.id) if a.reference <= b.reference else (b.id, a.id)


def _pairs_sharing_entities(evidence: list[EvidenceFacts]) -> set[tuple[uuid.UUID, uuid.UUID]]:
    holders: dict[uuid.UUID, list[EvidenceFacts]] = {}
    for item in evidence:
        for entity_id in item.entities:
            holders.setdefault(entity_id, []).append(item)
    pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()
    for items in holders.values():
        for i, a in enumerate(items):
            for b in items[i + 1 :]:
                pairs.add(_ordered(a, b))
    return pairs


def _entity_factor(a: EvidenceFacts, b: EvidenceFacts) -> Factor | None:
    shared = [
        (a.entities[eid][0], min(a.entities[eid][1], b.entities[eid][1]))
        for eid in a.entities.keys() & b.entities.keys()
    ]
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


def _best_proximity(evidence: list[EvidenceFacts]) -> dict[tuple[uuid.UUID, uuid.UUID], _Proximity]:
    """For each evidence pair, the two events closest in time AND place.

    Sweep-line: sort all timed events once, then compare each event only with the events that
    follow it within the time window — not every event with every other (n log n, not n²).
    """
    timed = sorted(
        ((item, event) for item in evidence for event in item.events if event.occurred_at),
        key=lambda pair: pair[1].occurred_at,  # type: ignore[arg-type, return-value]
    )
    best: dict[tuple[uuid.UUID, uuid.UUID], _Proximity] = {}
    for i, (item_a, event_a) in enumerate(timed):
        for item_b, event_b in timed[i + 1 :]:
            seconds = (event_b.occurred_at - event_a.occurred_at).total_seconds()  # type: ignore[operator]
            if seconds > TIME_WINDOW_S:
                break  # sorted by time: every later event is even further away
            if item_a.id == item_b.id:
                continue
            metres = _metres(event_a, event_b)
            candidate = _Proximity(event_a, event_b, seconds, metres)
            key = _ordered(item_a, item_b)
            if key not in best or candidate.strength > best[key].strength:
                best[key] = candidate
    return best


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
    earth = 6_371_008.8  # mean Earth radius in metres
    lat1, lat2 = math.radians(a.latitude), math.radians(b.latitude)  # type: ignore[arg-type]
    d_lat = lat2 - lat1
    d_lon = math.radians(b.longitude - a.longitude)  # type: ignore[operator]
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
    return 2 * earth * math.asin(math.sqrt(h))


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
