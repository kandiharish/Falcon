"""Court-ready outputs: Section 63 certificates, requisition letters, the court bundle."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User
from app.security.dependencies import require_permission
from app.security.permissions import Permission
from app.services import documents_service
from app.services.errors import InvalidInputError
from app.services.request_context import request_context

router = APIRouter(prefix="/investigations/{case_reference}", tags=["documents"])

Reader = Annotated[User, Depends(require_permission(Permission.EVIDENCE_READ))]
DB = Annotated[Session, Depends(get_db)]


class SectionOut(BaseModel):
    heading: str
    paragraphs: list[str]
    fields: list[tuple[str, str]]
    items: list[str]
    signatures: list[str]


class DocumentOut(BaseModel):
    kind: str
    title: str
    subtitle: str
    reference: str
    notice: str
    sections: list[SectionOut]
    to_check: list[str]


def _out(doc) -> DocumentOut:
    return DocumentOut(
        **{k: v for k, v in vars(doc).items() if k != "sections"},
        sections=[SectionOut(**vars(s)) for s in doc.sections],
    )


@router.get("/evidence/{evidence_reference}/certificate", response_model=DocumentOut)
def section_63_certificate(
    case_reference: str, evidence_reference: str, request: Request, user: Reader, db: DB
) -> DocumentOut:
    return _out(
        documents_service.certificate_for(
            db, user, case_reference, evidence_reference, request_context(request)
        )
    )


@router.get("/letters/{kind}", response_model=DocumentOut)
def requisition_letter(
    case_reference: str,
    kind: str,
    request: Request,
    user: Reader,
    db: DB,
    entity: Annotated[str, Query(max_length=12)],
    start: Annotated[datetime | None, Query(alias="from")] = None,
    end: Annotated[datetime | None, Query(alias="to")] = None,
    place: Annotated[list[str] | None, Query(max_length=200)] = None,
) -> DocumentOut:
    if (start is None) != (end is None):
        raise InvalidInputError("Give both 'from' and 'to', or neither.")
    window = (start, end) if start and end else None
    return _out(
        documents_service.letter_for(
            db,
            user,
            case_reference,
            kind,
            entity,
            request_context(request),
            window,
            tuple(place or ())[:4],
        )
    )


@router.get("/bundle")
def court_bundle(case_reference: str, request: Request, user: Reader, db: DB):
    file, name = documents_service.court_bundle(db, user, case_reference, request_context(request))

    def stream():
        with file:
            yield from iter(lambda: file.read(1024 * 1024), b"")

    return StreamingResponse(
        stream(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
