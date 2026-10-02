"""/api/investigations — the investigation management module (plan §10)."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.schemas import AuditEntry, audit_entry
from app.db.session import get_db
from app.models import Investigation, User
from app.repositories.investigation_repository import InvestigationFilters
from app.security.dependencies import require_permission
from app.security.permissions import Permission
from app.services import correlation_service, evidence_service, extraction_service
from app.services import investigation_service as service
from app.services.request_context import request_context

router = APIRouter(prefix="/investigations", tags=["investigations"])

Status = Literal["draft", "active", "under_review", "suspended", "closed", "archived"]
Priority = Literal["low", "medium", "high", "critical"]
Stage = Literal[
    "intake", "processing", "extraction", "correlation", "review", "reporting", "closed"
]

Reader = Annotated[User, Depends(require_permission(Permission.INVESTIGATION_READ))]
Writer = Annotated[User, Depends(require_permission(Permission.INVESTIGATION_WRITE))]
DB = Annotated[Session, Depends(get_db)]


# ---------- Shapes ----------------------------------------------------------------------


class PersonRef(BaseModel):
    id: uuid.UUID
    display_name: str


class InvestigationCounts(BaseModel):
    """Filled in as later phases add evidence (P5), entities/events (P6), correlations (P8)."""

    evidence: int = 0
    entities: int = 0
    events: int = 0
    correlations: int = 0


class InvestigationOut(BaseModel):
    reference: str
    title: str
    description: str
    case_type: str
    status: Status
    priority: Priority
    stage: Stage
    location: str
    time_zone: str
    tags: list[str]
    lead_investigator: PersonRef
    team_size: int
    my_role_in_case: Literal["lead", "member"] | None
    counts: InvestigationCounts
    created_at: datetime
    updated_at: datetime


class InvestigationPage(BaseModel):
    items: list[InvestigationOut]
    total: int
    limit: int
    offset: int


class InvestigationCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    case_type: str = Field(min_length=2, max_length=60)
    priority: Priority = "medium"
    location: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=5000)
    time_zone: str = Field(default="UTC", max_length=64)
    tags: list[str] = Field(default_factory=list, max_length=10)


class InvestigationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    case_type: str | None = Field(default=None, min_length=2, max_length=60)
    priority: Priority | None = None
    status: Status | None = None
    stage: Stage | None = None
    location: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    time_zone: str | None = Field(default=None, max_length=64)
    tags: list[str] | None = Field(default=None, max_length=10)


class MemberOut(BaseModel):
    user_id: uuid.UUID
    display_name: str
    email: str
    role: str
    role_in_case: Literal["lead", "member"]
    added_at: datetime


class MemberAdd(BaseModel):
    email: EmailStr


class AssignableUser(BaseModel):
    id: uuid.UUID
    display_name: str
    email: str
    role: str


def _out(
    investigation: Investigation, viewer: User, counts: dict[str, int] | None = None
) -> InvestigationOut:
    mine = next((m for m in investigation.members if m.user_id == viewer.id), None)
    return InvestigationOut(
        reference=investigation.reference,
        title=investigation.title,
        description=investigation.description,
        case_type=investigation.case_type,
        status=investigation.status,  # type: ignore[arg-type]
        priority=investigation.priority,  # type: ignore[arg-type]
        stage=investigation.stage,  # type: ignore[arg-type]
        location=investigation.location,
        time_zone=investigation.time_zone,
        tags=investigation.tags,
        lead_investigator=PersonRef(
            id=investigation.lead_investigator.id,
            display_name=investigation.lead_investigator.display_name,
        ),
        team_size=len(investigation.members),
        my_role_in_case=mine.role_in_case if mine else None,  # type: ignore[arg-type]
        counts=InvestigationCounts(**(counts or {})),
        created_at=investigation.created_at,
        updated_at=investigation.updated_at,
    )


def _counts(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
    evidence = evidence_service.counts_by_investigation(db, ids)
    extracted = extraction_service.counts_by_investigation(db, ids)
    correlations = correlation_service.counts_by_investigation(db, ids)
    return {
        i: {
            "evidence": evidence.get(i, 0),
            **extracted.get(i, {}),
            "correlations": correlations.get(i, 0),
        }
        for i in ids
    }


def _with_counts(db: Session, investigation: Investigation, user: User) -> InvestigationOut:
    return _out(investigation, user, _counts(db, [investigation.id])[investigation.id])


# ---------- Routes ----------------------------------------------------------------------


@router.get("", response_model=InvestigationPage)
def list_investigations(
    user: Reader,
    db: DB,
    search: Annotated[str | None, Query(max_length=100)] = None,
    status_filter: Annotated[Status | None, Query(alias="status")] = None,
    priority: Priority | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> InvestigationPage:
    filters = InvestigationFilters(search=search or None, status=status_filter, priority=priority)
    items, total = service.list_investigations(db, user, filters, limit, offset)
    counts = _counts(db, [i.id for i in items])
    return InvestigationPage(
        items=[_out(i, user, counts[i.id]) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=InvestigationOut, status_code=status.HTTP_201_CREATED)
def create_investigation(
    body: InvestigationCreate, request: Request, user: Writer, db: DB
) -> InvestigationOut:
    investigation = service.create_investigation(
        db, user, service.NewInvestigation(**body.model_dump()), request_context(request)
    )
    return _out(investigation, user)


@router.get("/assignable-users", response_model=list[AssignableUser])
def assignable_users(_: Writer, db: DB) -> list[AssignableUser]:
    return [
        AssignableUser(id=u.id, display_name=u.display_name, email=u.email, role=u.role)
        for u in service.assignable_users(db)
    ]


@router.get("/{reference}", response_model=InvestigationOut)
def get_investigation(reference: str, user: Reader, db: DB) -> InvestigationOut:
    investigation = service.get_investigation(db, user, reference)
    return _with_counts(db, investigation, user)


@router.patch("/{reference}", response_model=InvestigationOut)
def update_investigation(
    reference: str, body: InvestigationUpdate, request: Request, user: Writer, db: DB
) -> InvestigationOut:
    investigation = service.update_investigation(
        db, user, reference, body.model_dump(exclude_unset=True), request_context(request)
    )
    return _with_counts(db, investigation, user)


@router.get("/{reference}/members", response_model=list[MemberOut])
def list_members(reference: str, user: Reader, db: DB) -> list[MemberOut]:
    investigation = service.get_investigation(db, user, reference)
    members = sorted(investigation.members, key=lambda m: (m.role_in_case != "lead", m.added_at))
    return [
        MemberOut(
            user_id=m.user_id,
            display_name=m.user.display_name,
            email=m.user.email,
            role=m.user.role,
            role_in_case=m.role_in_case,  # type: ignore[arg-type]
            added_at=m.added_at,
        )
        for m in members
    ]


@router.post("/{reference}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def add_member(
    reference: str, body: MemberAdd, request: Request, user: Writer, db: DB
) -> MemberOut:
    m = service.add_member(db, user, reference, body.email, request_context(request))
    return MemberOut(
        user_id=m.user_id,
        display_name=m.user.display_name,
        email=m.user.email,
        role=m.user.role,
        role_in_case=m.role_in_case,  # type: ignore[arg-type]
        added_at=m.added_at,
    )


@router.get("/{reference}/activity", response_model=list[AuditEntry])
def investigation_activity(reference: str, user: Reader, db: DB) -> list[AuditEntry]:
    return [audit_entry(row) for row in service.activity(db, user, reference)]
