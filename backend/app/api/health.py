"""System health: is the API alive, and can it reach the database?"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(tags=["system"])

REQUIRED_EXTENSIONS = ("postgis", "vector", "pg_trgm")


class DatabaseHealth(BaseModel):
    connected: bool
    server_version: str | None = None
    extensions: dict[str, str | None] = {}


class HealthResponse(BaseModel):
    status: str  # "ok" | "degraded"
    database: DatabaseHealth


@router.get("/health", response_model=HealthResponse)
def health(db: Annotated[Session, Depends(get_db)]) -> HealthResponse:
    try:
        version = db.execute(text("SHOW server_version")).scalar_one()
        rows = db.execute(
            text("SELECT extname, extversion FROM pg_extension WHERE extname = ANY(:names)"),
            {"names": list(REQUIRED_EXTENSIONS)},
        ).all()
    except SQLAlchemyError:
        # Never leak internal error details to the client.
        return HealthResponse(status="degraded", database=DatabaseHealth(connected=False))

    installed = dict(rows)
    extensions = {name: installed.get(name) for name in REQUIRED_EXTENSIONS}
    all_present = all(extensions.values())
    return HealthResponse(
        status="ok" if all_present else "degraded",
        database=DatabaseHealth(connected=True, server_version=version, extensions=extensions),
    )
