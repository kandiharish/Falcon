"""Per-case numbering: IMG-001, P001, E001 … One atomic statement, safe under concurrency."""

import uuid

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import EvidenceReferenceCounter


def next_value(db: Session, investigation_id: uuid.UUID, prefix: str) -> int:
    """Increment and return the counter for (case, prefix); the first call returns 1."""
    return db.execute(
        insert(EvidenceReferenceCounter)
        .values(investigation_id=investigation_id, prefix=prefix, last_value=1)
        .on_conflict_do_update(
            index_elements=[
                EvidenceReferenceCounter.investigation_id,
                EvidenceReferenceCounter.prefix,
            ],
            set_={"last_value": EvidenceReferenceCounter.last_value + 1},
        )
        .returning(EvidenceReferenceCounter.last_value)
    ).scalar_one()
