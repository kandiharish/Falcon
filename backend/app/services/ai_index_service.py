"""Builds the AI similarity index: text embeddings (pgvector) and image fingerprints.

Called by the processing pipeline for new evidence, and by "Rebuild AI index" for evidence
processed while the AI service was off. Indexing never changes the evidence itself.
"""

import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai import provider as ai
from app.ai.similarity import chunk_text, dhash
from app.core.config import get_settings
from app.models import Evidence, EvidenceChunk, User
from app.security.permissions import Permission, permissions_for
from app.services import audit_service, evidence_service, investigation_service
from app.services.errors import ForbiddenError
from app.services.request_context import RequestContext
from app.storage import local as storage

log = logging.getLogger("falcon.ai")
BATCH = 16


def text_key(evidence: Evidence) -> str:
    return f"derived/{evidence.investigation_id}/{evidence.id}/text.txt"


def index_text(db: Session, evidence: Evidence, text: str) -> int:
    """Replace this evidence's chunks with fresh ones. Raises AIUnavailable."""
    chunks = chunk_text(text)
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), BATCH):
        vectors += ai.current().embed(chunks[start : start + BATCH])
    db.execute(delete(EvidenceChunk).where(EvidenceChunk.evidence_id == evidence.id))
    model = get_settings().ai_embed_model
    for number, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
        db.add(
            EvidenceChunk(
                investigation_id=evidence.investigation_id,
                evidence_id=evidence.id,
                chunk_index=number,
                text=chunk,
                embedding=vector,
                model=model,
            )
        )
    return len(chunks)


def fingerprint_image(evidence: Evidence) -> str:
    evidence.perceptual_hash = dhash(storage.path_of(evidence.storage_key))
    return evidence.perceptual_hash


def rebuild(
    db: Session, user: User, case_reference: str, context: RequestContext
) -> dict[str, int]:
    """Index every evidence item of a case again (team members who may process evidence)."""
    case = investigation_service.get_investigation(db, user, case_reference)
    if Permission.EVIDENCE_UPLOAD not in permissions_for(user.role):
        raise ForbiddenError("Only team members who process evidence can rebuild the AI index.")
    evidence_service.require_team_member(db, user, case)
    texts = images = chunks = 0
    for evidence in db.scalars(select(Evidence).where(Evidence.investigation_id == case.id)):
        if evidence.media_type.startswith("image/"):
            fingerprint_image(evidence)
            images += 1
        path = storage.path_of(text_key(evidence))
        if path.exists():
            text = path.read_text(encoding="utf-8")
            if text.strip():
                chunks += index_text(db, evidence, text)
                texts += 1
    result = {"documents": texts, "chunks": chunks, "images": images}
    audit_service.record(
        db,
        "ai.index_rebuilt",
        actor=user,
        object_type="investigation",
        object_id=case.reference,
        new_state={**result, "model": get_settings().ai_embed_model},
        context=context,
    )
    db.commit()
    return result
