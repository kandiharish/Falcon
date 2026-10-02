"""Data access for investigations. The only module that builds investigation SQL.

Services decide *what* is allowed; this module only knows *how* to fetch and store.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import Select, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from app.models import Investigation, InvestigationMember, ReferenceCounter


@dataclass(frozen=True)
class InvestigationFilters:
    search: str | None = None
    status: str | None = None
    priority: str | None = None


def _visible(user_id: uuid.UUID, see_all: bool) -> Select[tuple[Investigation]]:
    """Base query with data isolation applied: only cases the user may see."""
    query = select(Investigation)
    if not see_all:
        query = query.where(
            Investigation.id.in_(
                select(InvestigationMember.investigation_id).where(
                    InvestigationMember.user_id == user_id
                )
            )
        )
    return query


def list_visible(
    db: Session,
    user_id: uuid.UUID,
    see_all: bool,
    filters: InvestigationFilters,
    limit: int,
    offset: int,
) -> tuple[list[Investigation], int]:
    query = _visible(user_id, see_all)
    if filters.status:
        query = query.where(Investigation.status == filters.status)
    if filters.priority:
        query = query.where(Investigation.priority == filters.priority)
    if filters.search:
        term = f"%{filters.search.strip()}%"
        query = query.where(
            or_(
                Investigation.title.ilike(term),
                Investigation.reference.ilike(term),
                Investigation.location.ilike(term),
            )
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(
        query.options(
            selectinload(Investigation.lead_investigator), selectinload(Investigation.members)
        )
        .order_by(Investigation.updated_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(items), total


def get_visible(
    db: Session, user_id: uuid.UUID, see_all: bool, reference: str
) -> Investigation | None:
    return db.scalar(
        _visible(user_id, see_all)
        .where(Investigation.reference == reference.upper())
        .options(selectinload(Investigation.lead_investigator), selectinload(Investigation.members))
    )


def membership(
    db: Session, investigation_id: uuid.UUID, user_id: uuid.UUID
) -> InvestigationMember | None:
    return db.scalar(
        select(InvestigationMember).where(
            InvestigationMember.investigation_id == investigation_id,
            InvestigationMember.user_id == user_id,
        )
    )


def next_reference(db: Session, year: int) -> str:
    """CASE-2026-001, -002, … One atomic statement: two users creating cases at the same
    moment can never receive the same number (the row is locked while it is incremented)."""
    statement = (
        insert(ReferenceCounter)
        .values(year=year, last_value=1)
        .on_conflict_do_update(
            index_elements=[ReferenceCounter.year],
            set_={"last_value": ReferenceCounter.last_value + 1},
        )
        .returning(ReferenceCounter.last_value)
    )
    value = db.execute(statement).scalar_one()
    return f"CASE-{year}-{value:03d}"
