"""A large, clearly labelled, FICTIONAL case for performance testing. Development only.

    uv run python -m app.scripts.seed_load_test            # create CASE-2026-900
    uv run python -m app.scripts.seed_load_test --remove   # delete it again

60 evidence items · 1,200 entities · 6,000 events with participants · 4,000 mentions,
spread over three days around one fictional city, then the real correlation engine runs.
Evidence rows have no files behind them (metadata only): enough to load every screen.
Random but repeatable (fixed seed), so measurements can be compared before/after a change.
"""

import hashlib
import random
import sys
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import (
    Correlation,
    Entity,
    EntityMention,
    Event,
    EventParticipant,
    Evidence,
    EvidenceReferenceCounter,
    Investigation,
    InvestigationMember,
    Notification,
    ProcessingJob,
    User,
)
from app.services import correlation_service

REFERENCE = "CASE-2026-900"
EVIDENCE, ENTITIES, EVENTS, MENTIONS = 60, 1_200, 6_000, 4_000
START = datetime(2026, 9, 20, 0, 0, tzinfo=UTC)
CENTRE = (17.4386, 78.3921)  # fictional coordinates also used by the demo case

EVIDENCE_TYPES = ["video", "image", "gps", "call_records", "financial", "vehicle", "document"]
ENTITY_TYPES = {
    "phone_number": "PH",
    "vehicle": "V",
    "device": "D",
    "account": "A",
    "person": "P",
    "organization": "ORG",
}
EVENT_TYPES = [
    "call_made",
    "location_recorded",
    "vehicle_detected",
    "transaction_completed",
    "person_detected",
]


def remove(db) -> None:
    """Evidence never cascades away with its case (chain of custody), so the synthetic case
    is taken apart explicitly, children first. The audit log keeps its entries."""
    case = db.scalar(select(Investigation).where(Investigation.reference == REFERENCE))
    if case is None:
        return
    in_case = Investigation.id == case.id
    events = select(Event.id).where(Event.investigation_id == case.id)
    entities = select(Entity.id).where(Entity.investigation_id == case.id)
    evidence = select(Evidence.id).where(Evidence.investigation_id == case.id)
    for statement in (
        delete(Correlation).where(Correlation.investigation_id == case.id),
        delete(EventParticipant).where(EventParticipant.event_id.in_(events)),
        delete(Event).where(Event.investigation_id == case.id),
        delete(EntityMention).where(EntityMention.entity_id.in_(entities)),
        delete(Entity).where(Entity.investigation_id == case.id),
        delete(ProcessingJob).where(ProcessingJob.evidence_id.in_(evidence)),
        delete(Notification).where(Notification.investigation_id == case.id),
        delete(Evidence).where(Evidence.investigation_id == case.id),
        delete(InvestigationMember).where(InvestigationMember.investigation_id == case.id),
        delete(EvidenceReferenceCounter).where(
            EvidenceReferenceCounter.investigation_id == case.id
        ),
        delete(Investigation).where(in_case),
    ):
        db.execute(statement)
    db.commit()
    print(f"Removed {REFERENCE}.")


def main() -> int:
    if get_settings().environment != "development":
        print("Development only.")
        return 1
    rng = random.Random(900)
    with SessionLocal() as db:
        if "--remove" in sys.argv:
            remove(db)
            return 0
        if db.scalar(select(Investigation).where(Investigation.reference == REFERENCE)):
            print(f"{REFERENCE} already exists (use --remove first).")
            return 0
        lead = db.scalar(select(User).where(User.email == "r.varma@falcon.example"))
        if lead is None:
            print("Run the demo seeds first.")
            return 1
        started = time.perf_counter()
        case = Investigation(
            reference=REFERENCE,
            title="LOAD TEST — synthetic city-wide case (fictional)",
            description="Generated for performance testing. Not part of the demo story.",
            case_type="Load test",
            status="active",
            priority="low",
            stage="correlation",
            location="Synthetic city",
            time_zone="Asia/Kolkata",
            tags=["load-test"],
            lead_investigator_id=lead.id,
            created_by_id=lead.id,
        )
        db.add(case)
        db.flush()
        db.add(InvestigationMember(investigation_id=case.id, user_id=lead.id, role_in_case="lead"))
        analyst = db.scalar(select(User).where(User.email == "a.kumar@falcon.example"))
        if analyst:
            db.add(InvestigationMember(investigation_id=case.id, user_id=analyst.id))

        evidence = []
        for n in range(EVIDENCE):
            kind = EVIDENCE_TYPES[n % len(EVIDENCE_TYPES)]
            digest = hashlib.sha256(f"{REFERENCE}-{n}".encode()).hexdigest()
            evidence.append(
                Evidence(
                    investigation_id=case.id,
                    reference=f"LT{kind[:3].upper()}-{n + 1:03d}",
                    evidence_type=kind,
                    status="processed",
                    description=f"Synthetic {kind.replace('_', ' ')} source {n + 1}",
                    original_filename=f"synthetic-{n + 1}.bin",
                    media_type="application/octet-stream",
                    size_bytes=1024,
                    sha256=digest,
                    storage_key=f"load-test/{digest}",
                    integrity_ok=True,
                    uploaded_by_id=lead.id,
                )
            )
        db.add_all(evidence)

        entities = []
        kinds = list(ENTITY_TYPES)
        counters = dict.fromkeys(kinds, 0)
        for n in range(ENTITIES):
            kind = kinds[n % len(kinds)]
            counters[kind] += 1
            ref = f"{ENTITY_TYPES[kind]}{counters[kind]:03d}"
            entities.append(
                Entity(
                    investigation_id=case.id,
                    reference=ref,
                    entity_type=kind,
                    label=f"Synthetic {kind.replace('_', ' ')} {counters[kind]}",
                    normalized_key=f"load-{ref}",
                    review_status=rng.choice(["pending", "pending", "confirmed"]),
                )
            )
        db.add_all(entities)
        db.flush()

        db.add_all(
            EntityMention(
                entity_id=rng.choice(entities).id,
                evidence_id=rng.choice(evidence).id,
                assertion_kind="extracted",
                confidence=round(rng.uniform(0.6, 0.99), 2),
                extractor="load-test",
                source_location=f"row {n + 1}",
                context="synthetic",
            )
            for n in range(MENTIONS)
        )

        events = []
        for n in range(EVENTS):
            when = START + timedelta(seconds=rng.randint(0, 3 * 86400))
            lat = CENTRE[0] + rng.gauss(0, 0.02)
            lon = CENTRE[1] + rng.gauss(0, 0.02)
            events.append(
                Event(
                    investigation_id=case.id,
                    reference=f"E{n + 1:04d}",
                    event_type=rng.choice(EVENT_TYPES),
                    occurred_at=when,
                    latitude=lat,
                    longitude=lon,
                    description=f"Synthetic event {n + 1}",
                    evidence_id=rng.choice(evidence).id,
                    assertion_kind="extracted",
                    confidence=round(rng.uniform(0.6, 0.99), 2),
                    extractor="load-test",
                    review_status="pending",
                )
            )
        db.add_all(events)
        db.flush()
        db.add_all(
            EventParticipant(event_id=e.id, entity_id=rng.choice(entities).id, role=role)
            for e in events
            for role in rng.sample(["caller", "callee", "device", "vehicle"], k=rng.randint(1, 2))
        )
        db.commit()
        print(f"Created {REFERENCE} in {time.perf_counter() - started:.1f} s.")

        started = time.perf_counter()
        summary = correlation_service.run_for_case(db, case)
        print(
            f"Correlation engine: {summary.total} relationships in "
            f"{time.perf_counter() - started:.1f} s."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
