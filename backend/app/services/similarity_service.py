"""Similar evidence and meaning-based ("semantic") search (plan §22, §23).

Two different kinds of "similar", labelled differently because they are known differently:

  IMAGES  near-duplicate by perceptual hash        → DETECTED (a fixed algorithm)
  TEXT    close in embedding space (cosine)        → AI-ASSISTED (a model's judgement)

Scores are similarity, not proof: two reports can read alike and describe different nights.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import provider as ai
from app.ai.similarity import NEAR_DUPLICATE_BITS, hamming
from app.models import Evidence, EvidenceChunk, User
from app.services import evidence_service, investigation_service

TEXT_SIMILAR = 0.55  # cosine similarity above which two passages are worth showing
SEARCH_FLOOR = 0.2  # semantic search: weaker matches are noise
CHUNKS_COMPARED = 20


@dataclass
class SimilarEvidence:
    evidence: Evidence
    kind: str  # image | text
    score: float  # 0–1
    explanation: str
    passage: str = ""  # from the evidence being viewed
    match: str = ""  # from the other evidence


@dataclass
class SearchHit:
    evidence: Evidence
    score: float
    passage: str


def similar_to(
    db: Session, user: User, case_reference: str, reference: str
) -> list[SimilarEvidence]:
    evidence = evidence_service.get_evidence(db, user, case_reference, reference)
    results: list[SimilarEvidence] = []
    if evidence.perceptual_hash:
        others = db.scalars(
            select(Evidence).where(
                Evidence.investigation_id == evidence.investigation_id,
                Evidence.id != evidence.id,
                Evidence.perceptual_hash.is_not(None),
            )
        )
        for other in others:
            bits = hamming(evidence.perceptual_hash, other.perceptual_hash or "0")
            if bits <= NEAR_DUPLICATE_BITS:
                results.append(
                    SimilarEvidence(
                        other,
                        "image",
                        round(1 - bits / 64, 3),
                        f"The pictures look almost the same: their fingerprints differ in {bits} "
                        f"of 64 points. Possibly the same photo resized, cropped or re-saved.",
                    )
                )
    results += _similar_text(db, evidence)
    return sorted(results, key=lambda r: -r.score)


def _similar_text(db: Session, evidence: Evidence) -> list[SimilarEvidence]:
    own = db.scalars(
        select(EvidenceChunk)
        .where(EvidenceChunk.evidence_id == evidence.id)
        .order_by(EvidenceChunk.chunk_index)
        .limit(CHUNKS_COMPARED)
    ).all()
    best: dict[uuid.UUID, SimilarEvidence] = {}
    for chunk in own:
        distance = EvidenceChunk.embedding.cosine_distance(chunk.embedding).label("distance")
        rows = db.execute(
            select(EvidenceChunk, distance)
            .where(
                EvidenceChunk.investigation_id == evidence.investigation_id,
                EvidenceChunk.evidence_id != evidence.id,
            )
            .order_by(distance)
            .limit(5)
        ).all()
        for other, dist in rows:
            score = round(1 - float(dist), 3)
            if score < TEXT_SIMILAR:
                continue
            current = best.get(other.evidence_id)
            if current is None or score > current.score:
                best[other.evidence_id] = SimilarEvidence(
                    other.evidence,
                    "text",
                    score,
                    f"A passage of {evidence.reference} and a passage of "
                    f"{other.evidence.reference} say similar things "
                    f"(similarity {score:.2f} by the AI text model).",
                    passage=chunk.text,
                    match=other.text,
                )
    return list(best.values())


def search(
    db: Session, user: User, case_reference: str, text: str, limit: int = 8
) -> list[SearchHit]:
    """Passages whose MEANING is closest to the question. Raises AIUnavailable."""
    case = investigation_service.get_investigation(db, user, case_reference)
    [vector] = ai.current().embed([text])
    distance = EvidenceChunk.embedding.cosine_distance(vector).label("distance")
    rows = db.execute(
        select(EvidenceChunk, distance)
        .where(EvidenceChunk.investigation_id == case.id)
        .order_by(distance)
        .limit(limit * 3)
    ).all()
    hits: list[SearchHit] = []
    seen: set[uuid.UUID] = set()
    for chunk, dist in rows:
        score = round(1 - float(dist), 3)
        if score < SEARCH_FLOOR or chunk.evidence_id in seen:
            continue
        seen.add(chunk.evidence_id)  # one passage per evidence item: the best one
        hits.append(SearchHit(chunk.evidence, score, chunk.text))
    return hits[:limit]
