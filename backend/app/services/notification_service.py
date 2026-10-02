"""Notifications (plan §29): tell the RIGHT person about something they need to act on.

Avoiding overload (the plan's rule) is a design choice in every call site:
  • nobody is notified about their own action;
  • processing results go to the uploader only, new correlations to the case lead only;
  • a repeat of an unread notification with the same title updates it instead of piling up.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import Evidence, Investigation, Notification, User


def notify(
    db: Session,
    user_id: uuid.UUID | None,
    kind: str,
    title: str,
    *,
    body: str = "",
    link: str = "",
    investigation_id: uuid.UUID | None = None,
    actor: User | None = None,
) -> None:
    """Add a notification to the current transaction (the caller commits)."""
    if user_id is None or (actor is not None and actor.id == user_id):
        return
    existing = db.scalar(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.title == title,
            Notification.read_at.is_(None),
        )
    )
    if existing:
        existing.body, existing.link, existing.created_at = body, link, datetime.now(UTC)
        return
    db.add(
        Notification(
            user_id=user_id,
            kind=kind,
            title=title[:200],
            body=body,
            link=link,
            investigation_id=investigation_id,
        )
    )


def evidence_link(evidence: Evidence, case_reference: str) -> str:
    return f"/investigations/{case_reference}/evidence/{evidence.reference}"


def processing_finished(
    db: Session, evidence: Evidence, case: Investigation, ok: bool, warnings: str | None
) -> None:
    link = evidence_link(evidence, case.reference)
    if not ok:
        notify(
            db,
            evidence.uploaded_by_id,
            "processing_failed",
            f"Processing failed: {evidence.reference}",
            body=warnings or "",
            link=link,
            investigation_id=case.id,
        )
    elif warnings:
        notify(
            db,
            evidence.uploaded_by_id,
            "requires_review",
            f"{evidence.reference} needs review",
            body=warnings,
            link=link,
            investigation_id=case.id,
        )
    else:
        notify(
            db,
            evidence.uploaded_by_id,
            "processing_completed",
            f"{evidence.reference} processed",
            body=evidence.description or evidence.original_filename,
            link=link,
            investigation_id=case.id,
        )


def list_for(
    db: Session, user: User, unread_only: bool, limit: int
) -> tuple[list[Notification], int]:
    query = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    rows = list(db.scalars(query.order_by(Notification.created_at.desc()).limit(limit)))
    unread = db.scalar(
        select(func.count()).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    )
    return rows, unread or 0


def mark_read(db: Session, user: User, notification_id: uuid.UUID | None) -> None:
    """One notification, or all of them (None). Only ever the user's own."""
    query = update(Notification).where(
        Notification.user_id == user.id, Notification.read_at.is_(None)
    )
    if notification_id is not None:
        query = query.where(Notification.id == notification_id)
    db.execute(query.values(read_at=datetime.now(UTC)))
    db.commit()
