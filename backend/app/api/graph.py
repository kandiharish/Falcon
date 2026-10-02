"""/api/investigations/{case}/graph — the relationship graph (plan §20)."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.graph import builder
from app.models import User
from app.security.dependencies import require_permission
from app.security.permissions import Permission
from app.services import graph_service

router = APIRouter(prefix="/investigations/{case_reference}/graph", tags=["graph"])

Reader = Annotated[User, Depends(require_permission(Permission.EVIDENCE_READ))]
DB = Annotated[Session, Depends(get_db)]

EdgeType = Literal[
    "appears_in",
    "communicated_with",
    "connected_to",
    "related_evidence",
    "involved_in",
    "recorded_in",
]


class NodeOut(BaseModel):
    id: str
    kind: Literal["entity", "evidence", "event"]
    type: str
    reference: str
    label: str
    review_status: str | None
    degree: int
    details: dict[str, Any]


class EdgeOut(BaseModel):
    id: str
    source: str
    target: str
    type: EdgeType
    why: str
    confidence: float
    review_status: str
    assertion_kinds: list[str]
    supporting_evidence: list[str]
    supporting_events: list[str]
    details: dict[str, Any]


class GraphOut(BaseModel):
    nodes: list[NodeOut]
    edges: list[EdgeOut]
    total_nodes: int
    total_edges: int
    truncated: bool


@router.get("", response_model=GraphOut)
def get_graph(
    case_reference: str,
    user: Reader,
    db: DB,
    include_events: bool = False,
    include_evidence: bool = True,
    include_rejected: bool = False,
    include_stale: bool = False,
    entity_type: Annotated[list[str] | None, Query(max_length=10)] = None,
    min_level: Literal["low", "medium", "high"] = "low",
    focus: Annotated[str | None, Query(max_length=40)] = None,
    depth: Annotated[int, Query(ge=1, le=3)] = 1,
    max_nodes: Annotated[int, Query(ge=10, le=1000)] = 300,
) -> GraphOut:
    options = builder.Options(
        include_events=include_events,
        include_evidence=include_evidence,
        include_rejected=include_rejected,
        include_stale=include_stale,
        entity_types=frozenset(entity_type) if entity_type else None,
        min_level=min_level,
        focus=focus,
        depth=depth,
        max_nodes=max_nodes,
    )
    result = graph_service.graph(db, user, case_reference, options)
    return GraphOut(
        nodes=[NodeOut(**n.__dict__) for n in result.nodes],
        edges=[EdgeOut(**e.__dict__) for e in result.edges],
        total_nodes=result.total_nodes,
        total_edges=result.total_edges,
        truncated=result.truncated,
    )
