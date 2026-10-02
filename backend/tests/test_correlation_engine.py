"""Unit tests for the pure correlation engine: exact scores, rules and explanations."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.correlation.engine import (
    TIME_WINDOW_S,
    EntityFact,
    EventFact,
    EvidenceFacts,
    correlate,
    level_for,
)

T0 = datetime(2026, 9, 28, 15, 0, tzinfo=UTC)
SCENE = (17.43862, 78.39215)


def evidence(ref: str, events=(), entities=()) -> EvidenceFacts:
    item = EvidenceFacts(id=uuid.uuid4(), reference=ref)
    item.events = [
        EventFact(uuid.uuid4(), f"E-{ref}-{i}", when, lat, lon)
        for i, (when, lat, lon) in enumerate(events)
    ]
    item.entities = {entity.id: (entity, confidence) for entity, confidence in entities}
    return item


def entity(ref: str, label: str) -> EntityFact:
    return EntityFact(uuid.uuid4(), ref, label)


def factors_of(result) -> dict[str, float]:
    return {f.kind: round(f.score, 3) for f in result.factors}


def test_shared_entity_time_and_place_give_a_high_explained_score():
    van = entity("V001", "ZZ99 ZZ 0001")
    cctv = evidence("CCTV-001", [(T0, *SCENE)], [(van, 1.0)])
    anpr = evidence(
        "VEH-001", [(T0 + timedelta(seconds=10), SCENE[0] + 0.0004, SCENE[1])], [(van, 0.95)]
    )

    [result] = correlate([cctv, anpr])

    assert {result.evidence_a.reference, result.evidence_b.reference} == {"CCTV-001", "VEH-001"}
    scores = factors_of(result)
    assert scores["entity"] == 0.95  # the weaker of the two sightings
    assert scores["time"] == round(1 - 10 / TIME_WINDOW_S, 3)
    assert 0.9 < scores["location"] < 0.92  # ~44 m of a 500 m radius
    assert result.score == pytest.approx(
        0.45 * 0.95 + 0.30 * scores["time"] + 0.25 * scores["location"], abs=1e-3
    )
    assert result.level == "high"
    explanations = " ".join(f.explanation for f in result.factors)
    assert (
        "V001 (ZZ99 ZZ 0001)" in explanations
        and "10 seconds apart" in explanations
        and "44 m" in explanations
    )


def test_time_alone_is_coincidence_not_a_relationship():
    a = evidence("A", [(T0, None, None)])
    b = evidence("B", [(T0 + timedelta(minutes=2), None, None)])
    assert correlate([a, b]) == []


def test_time_and_place_without_shared_entity_is_reported():
    a = evidence("GPS-001", [(T0, *SCENE)])
    b = evidence("IMG-001", [(T0 + timedelta(minutes=2), SCENE[0] + 0.0001, SCENE[1])])
    [result] = correlate([a, b])
    assert set(factors_of(result)) == {"time", "location"}
    assert result.level == "medium"


def test_shared_entity_alone_is_reported_even_far_apart_in_time():
    phone = entity("PH001", "+1 202-555-0101")
    calls = evidence("CALL-001", [(T0, None, None)], [(phone, 0.95)])
    report = evidence("DOC-001", [(T0 + timedelta(hours=2), None, None)], [(phone, 0.9)])
    [result] = correlate([calls, report])
    assert set(factors_of(result)) == {"entity"}
    assert result.level == "low"


def test_events_beyond_the_window_or_radius_do_not_count():
    a = evidence("A", [(T0, *SCENE)])
    b = evidence("B", [(T0 + timedelta(seconds=TIME_WINDOW_S + 1), *SCENE)])
    c = evidence("C", [(T0 + timedelta(minutes=1), SCENE[0] + 0.05, SCENE[1])])  # ~5.5 km away
    results = correlate([a, b, c])
    assert results == []  # A–B too late, A–C too far (time alone is not enough)


def test_events_in_the_same_evidence_never_correlate_with_each_other():
    item = evidence("GPS-001", [(T0, *SCENE), (T0 + timedelta(seconds=5), *SCENE)])
    assert correlate([item]) == []


def test_the_best_pair_of_events_is_used():
    a = evidence("A", [(T0, *SCENE), (T0 + timedelta(minutes=20), *SCENE)])
    b = evidence("B", [(T0 + timedelta(minutes=19, seconds=50), *SCENE)])
    [result] = correlate([a, b])
    time_factor = next(f for f in result.factors if f.kind == "time")
    assert time_factor.details["seconds_apart"] == 10


def test_order_of_input_does_not_change_the_result():
    van = entity("V001", "van")
    a = evidence("A", [(T0, *SCENE)], [(van, 0.9)])
    b = evidence("B", [(T0 + timedelta(seconds=30), *SCENE)], [(van, 0.8)])
    first, second = correlate([a, b]), correlate([b, a])
    assert [(r.evidence_a.reference, r.score) for r in first] == [
        (r.evidence_a.reference, r.score) for r in second
    ]


@pytest.mark.parametrize(
    ("score", "level"), [(0.75, "high"), (0.749, "medium"), (0.5, "medium"), (0.3, "low")]
)
def test_levels(score, level):
    assert level_for(score) == level
