"""ExtractionSink: the only way extractors save entities, mentions and events.

Extractors say "I found phone +1 202-555-0101 at row 3"; the sink
  • normalises it and finds the existing entity in this case (or creates PH001),
  • records a mention with provenance (evidence, place in file, extractor, confidence),
  • links entities to events as participants.

Re-running extraction for an evidence item first removes what EARLIER AUTOMATIC runs produced
from that item (never anything a person entered), so reprocessing never duplicates facts.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import delete, exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.extraction.normalize import normalize
from app.models import Entity, EntityMention, Event, EventParticipant, Evidence
from app.repositories import reference_counters

ENTITY_PREFIX = {
    "person": "P",
    "phone_number": "PH",
    "device": "D",
    "vehicle": "V",
    "account": "A",
    "location": "LOC",
    "organization": "ORG",
    "digital_artifact": "ART",
}


@dataclass
class Provenance:
    assertion: str  # extracted | detected | user_entered …
    confidence: float
    extractor: str
    source_location: str = ""
    context: str = ""


@dataclass
class ExtractionSink:
    db: Session
    evidence: Evidence
    _entities: dict[tuple[str, str], Entity] = field(default_factory=dict)
    _mentioned: set[tuple[uuid.UUID, str]] = field(default_factory=set)
    entities_found: set[uuid.UUID] = field(default_factory=set)
    events_created: int = 0

    # ---- entities ----------------------------------------------------------------------

    def entity(
        self,
        entity_type: str,
        raw_value: str,
        provenance: Provenance,
        attributes: dict[str, Any] | None = None,
    ) -> Entity | None:
        normalized = normalize(entity_type, raw_value)
        if normalized is None:
            return None
        entity = self._find_or_create(entity_type, normalized.key, normalized.label, attributes)
        mention_key = (entity.id, provenance.source_location)
        if mention_key not in self._mentioned:  # one mention per place in the file
            self._mentioned.add(mention_key)
            self.db.add(
                EntityMention(
                    entity_id=entity.id,
                    evidence_id=self.evidence.id,
                    assertion_kind=provenance.assertion,
                    confidence=round(min(max(provenance.confidence, 0.0), 1.0), 3),
                    extractor=provenance.extractor,
                    source_location=provenance.source_location[:120],
                    context=provenance.context[:500],
                )
            )
        self.entities_found.add(entity.id)
        return entity

    def _find_or_create(
        self, entity_type: str, key: str, label: str, attributes: dict[str, Any] | None
    ) -> Entity:
        cache_key = (entity_type, key)
        if cache_key in self._entities:
            return self._entities[cache_key]
        entity = self._lookup(entity_type, key)
        if entity is None:
            prefix = ENTITY_PREFIX[entity_type]
            number = reference_counters.next_value(self.db, self.evidence.investigation_id, prefix)
            candidate = Entity(
                id=uuid.uuid4(),
                investigation_id=self.evidence.investigation_id,
                reference=f"{prefix}{number:03d}",
                entity_type=entity_type,
                label=label[:200],
                normalized_key=key[:200],
                attributes=attributes or {},
            )
            # A savepoint: if another worker created the same entity a moment ago, the
            # unique constraint rejects ours; we roll back just this insert and use theirs.
            try:
                with self.db.begin_nested():
                    self.db.add(candidate)
                entity = candidate
            except IntegrityError:
                entity = self._lookup(entity_type, key)
                assert entity is not None
        elif attributes:
            entity.attributes = {**attributes, **(entity.attributes or {})}  # keep existing values
        self._entities[cache_key] = entity
        return entity

    def _lookup(self, entity_type: str, key: str) -> Entity | None:
        return self.db.scalar(
            select(Entity).where(
                Entity.investigation_id == self.evidence.investigation_id,
                Entity.entity_type == entity_type,
                Entity.normalized_key == key,
            )
        )

    # ---- events ------------------------------------------------------------------------

    def event(
        self,
        event_type: str,
        occurred_at: datetime | None,
        provenance: Provenance,
        *,
        description: str,
        participants: list[tuple[Entity | None, str]] = (),
        ended_at: datetime | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        location_text: str = "",
        attributes: dict[str, Any] | None = None,
    ) -> Event:
        number = reference_counters.next_value(self.db, self.evidence.investigation_id, "E")
        event = Event(
            investigation_id=self.evidence.investigation_id,
            reference=f"E{number:03d}",
            event_type=event_type,
            occurred_at=occurred_at,
            ended_at=ended_at,
            latitude=latitude,
            longitude=longitude,
            location_text=location_text[:200],
            description=description,
            evidence_id=self.evidence.id,
            assertion_kind=provenance.assertion,
            confidence=round(min(max(provenance.confidence, 0.0), 1.0), 3),
            extractor=provenance.extractor,
            source_location=provenance.source_location[:120],
            attributes=attributes or {},
        )
        seen: set[tuple[uuid.UUID, str]] = set()
        for entity, role in participants:
            if entity is not None and (entity.id, role) not in seen:
                seen.add((entity.id, role))
                event.participants.append(EventParticipant(entity_id=entity.id, role=role))
        self.db.add(event)
        self.events_created += 1
        return event


def clear_automatic_results(db: Session, evidence: Evidence) -> None:
    """Remove what earlier automatic runs extracted from this evidence (keeps human input).
    Entities themselves stay for now, so if they are found again they keep their reference
    (P001 stays P001); call remove_orphan_entities() after extracting."""
    db.execute(delete(Event).where(Event.evidence_id == evidence.id, Event.created_by_id.is_(None)))
    db.execute(
        delete(EntityMention).where(
            EntityMention.evidence_id == evidence.id, EntityMention.created_by_id.is_(None)
        )
    )
    db.flush()


def remove_orphan_entities(db: Session, evidence: Evidence) -> None:
    """Automatic entities that are no longer mentioned anywhere and take part in nothing."""
    db.execute(
        delete(Entity).where(
            Entity.investigation_id == evidence.investigation_id,
            Entity.created_by_id.is_(None),
            ~exists().where(EntityMention.entity_id == Entity.id),
            ~exists().where(EventParticipant.entity_id == Entity.id),
        )
    )
    db.flush()
