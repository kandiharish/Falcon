"""AI similarity index (plan §22): evidence text cut into chunks, each with an embedding.

An EMBEDDING is a list of 384 numbers that places a piece of text in "meaning space":
texts about the same thing get vectors that point the same way, even with different words
("grey van" ≈ "silver vehicle"). pgvector stores them and finds the nearest ones.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.evidence import Evidence

EMBEDDING_DIMENSIONS = 384  # all-MiniLM-L6-v2


class EvidenceChunk(Base):
    __tablename__ = "evidence_chunks"
    __table_args__ = (
        # HNSW = a navigable "small world" graph of vectors: nearest neighbours without
        # comparing against every row. Cosine = compare directions, not lengths.
        Index(
            "ix_evidence_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), index=True
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    model: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    evidence: Mapped[Evidence] = relationship()
