"""AI-assisted features (plan §22–§23): status, natural-language search, similar evidence,
rebuilding the similarity index, and the Investigation Assistant (streamed)."""

import json
from collections.abc import Iterator
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai import assistant
from app.ai import provider as ai
from app.ai.search_plan import SearchPlan, describe
from app.api.extraction import EventOut, event_out
from app.api.graph import EdgeOut, NodeOut
from app.db.session import SessionLocal, get_db
from app.models import User
from app.security.dependencies import require_permission
from app.security.permissions import Permission
from app.security.rate_limit import limit
from app.services import ai_index_service, investigation_service, nl_search_service
from app.services import similarity_service as similarity
from app.services.request_context import request_context

router = APIRouter(tags=["ai"])
Reader = Annotated[User, Depends(require_permission(Permission.EVIDENCE_READ))]
DB = Annotated[Session, Depends(get_db)]
CASE = "/investigations/{case_reference}"


class AIStatusOut(BaseModel):
    available: bool
    chat_model: str
    embed_model: str
    chat_model_ready: bool
    embed_model_ready: bool
    message: str


class EvidenceBrief(BaseModel):
    reference: str
    evidence_type: str
    description: str


class EntityBrief(BaseModel):
    reference: str
    entity_type: str
    label: str
    review_status: str


class Passage(BaseModel):
    evidence: EvidenceBrief
    score: float
    passage: str


class SearchIn(BaseModel):
    question: str = Field(min_length=2, max_length=500)


class SearchOut(BaseModel):
    question: str
    plan: SearchPlan
    summary: str
    notes: list[str]
    interpreted_by: str
    duration_ms: int
    events: list[EventOut]
    evidence: list[EvidenceBrief]
    entities: list[EntityBrief]
    path: list[EdgeOut]
    path_nodes: list[NodeOut]
    passages: list[Passage]


class SimilarOut(BaseModel):
    evidence: EvidenceBrief
    kind: Literal["image", "text"]
    score: float
    explanation: str
    passage: str
    match: str


class ReindexOut(BaseModel):
    documents: int
    chunks: int
    images: int


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    history: list[Turn] = Field(default_factory=list, max_length=12)


def _brief(e) -> EvidenceBrief:
    return EvidenceBrief(
        reference=e.reference,
        evidence_type=e.evidence_type,
        description=e.description or e.original_filename,
    )


@router.get("/ai/status", response_model=AIStatusOut)
def status(_: Reader) -> AIStatusOut:
    return AIStatusOut(**ai.current().status().__dict__)


@router.post(
    f"{CASE}/ai/search",
    response_model=SearchOut,
    dependencies=[Depends(limit("ai-search", 20, by="user"))],
)
def search(
    case_reference: str, body: SearchIn, request: Request, user: Reader, db: DB
) -> SearchOut:
    r = nl_search_service.search(db, user, case_reference, body.question, request_context(request))
    return SearchOut(
        question=r.question,
        plan=r.plan,
        summary=describe(r.plan),
        notes=r.notes,
        interpreted_by=r.interpreted_by,
        duration_ms=r.duration_ms,
        events=[event_out(e) for e in r.events],
        evidence=[_brief(e) for e in r.evidence],
        entities=[
            EntityBrief(
                reference=e.reference,
                entity_type=e.entity_type,
                label=e.label,
                review_status=e.review_status,
            )
            for e in r.entities
        ],
        path=[EdgeOut(**e.__dict__) for e in r.path],
        path_nodes=[
            NodeOut(**r.nodes[i].__dict__)
            for i in dict.fromkeys(x for e in r.path for x in (e.source, e.target))
            if i in r.nodes
        ],
        passages=[
            Passage(evidence=_brief(h.evidence), score=h.score, passage=h.passage)
            for h in r.passages
        ],
    )


@router.get(f"{CASE}/evidence/{{evidence_reference}}/similar", response_model=list[SimilarOut])
def similar(case_reference: str, evidence_reference: str, user: Reader, db: DB) -> list[SimilarOut]:
    return [
        SimilarOut(
            evidence=_brief(s.evidence),
            kind=s.kind,  # type: ignore[arg-type]
            score=s.score,
            explanation=s.explanation,
            passage=s.passage,
            match=s.match,
        )
        for s in similarity.similar_to(db, user, case_reference, evidence_reference)
    ]


@router.post(f"{CASE}/ai/reindex", response_model=ReindexOut)
def reindex(case_reference: str, request: Request, user: Reader, db: DB) -> ReindexOut:
    return ReindexOut(
        **ai_index_service.rebuild(db, user, case_reference, request_context(request))
    )


@router.post(f"{CASE}/assistant", dependencies=[Depends(limit("assistant", 6, by="user"))])
def ask(
    case_reference: str, body: AskIn, request: Request, user: Reader, db: DB
) -> StreamingResponse:
    """Streams newline-delimited JSON events: status, tool_start, tool_result, answer, error."""
    investigation_service.get_investigation(db, user, case_reference)  # 404 before streaming
    context = request_context(request)
    user_id = user.id
    history = [t.model_dump() for t in body.history]

    def events() -> Iterator[str]:
        # The stream outlives this request's database session: use our own.
        with SessionLocal() as session:
            me = session.get(User, user_id)
            if me is None:  # deleted between the request and the stream: nothing to say
                return
            case = investigation_service.get_investigation(session, me, case_reference)
            try:
                for event in assistant.ask(session, me, case, body.question, history, context):
                    yield _line(event)
            except ai.AIUnavailable as error:
                yield _line({"type": "error", "message": str(error)})

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


def _line(event: dict[str, Any]) -> str:
    return json.dumps(event, default=str) + "\n"
