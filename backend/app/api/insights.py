"""/api/investigations/{case}/insights — what the case data suggests checking next."""

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User
from app.security.dependencies import require_permission
from app.security.permissions import Permission
from app.services import insights_service

router = APIRouter(prefix="/investigations/{case_reference}/insights", tags=["insights"])

Reader = Annotated[User, Depends(require_permission(Permission.EVIDENCE_READ))]
DB = Annotated[Session, Depends(get_db)]


class InsightOut(BaseModel):
    key: str
    kind: Literal["other_case", "clock_drift", "waiting_lead", "sighting_gap", "unknown_owner"]
    severity: Literal["high", "medium", "info"]
    title: str
    detail: str
    action: str
    evidence: list[str]
    entities: list[str]
    letter: dict[str, Any] | None


class InsightsOut(BaseModel):
    items: list[InsightOut]
    generated_at: datetime
    note: str


@router.get("", response_model=InsightsOut)
def insights(case_reference: str, user: Reader, db: DB) -> InsightsOut:
    found = insights_service.build(db, user, case_reference)
    return InsightsOut(
        items=[InsightOut(**vars(i)) for i in found],
        generated_at=datetime.now(UTC),
        note=(
            "Suggestions from fixed rules over this case's records. Each one is something to "
            "check, not a finding."
        ),
    )
