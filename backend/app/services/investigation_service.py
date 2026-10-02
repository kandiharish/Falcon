"""Investigation use cases: list, open, create, update, team, activity.

Rules enforced here:
  • Data isolation — you see a case only if you are on its team (supervisors see all).
    A case you may not see answers 404, not 403, so its existence is not revealed.
  • Changing a case needs investigation:write AND team membership (or supervisor).
  • Status follows the allowed transitions below.
  • Every change is audited with its previous and new values.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Investigation, InvestigationMember, User
from app.repositories import investigation_repository as repo
from app.repositories.investigation_repository import InvestigationFilters
from app.security.permissions import Permission, Role, permissions_for
from app.services import audit_service
from app.services.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError
from app.services.request_context import RequestContext

NOT_FOUND = "This investigation does not exist or you are not on its team."

# Which status may follow which (plan §10). Archived is final.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"active", "archived"},
    "active": {"under_review", "suspended", "closed"},
    "under_review": {"active", "closed"},
    "suspended": {"active", "closed"},
    "closed": {"active", "archived"},  # "active" = reopen
    "archived": set(),
}

EDITABLE_FIELDS = (
    "title",
    "description",
    "case_type",
    "priority",
    "status",
    "stage",
    "location",
    "time_zone",
    "tags",
)


def validate_time_zone(name: str) -> str:
    """Only real IANA zone names ("Asia/Kolkata", "Europe/London", "UTC") are accepted."""
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise InvalidInputError(f"'{name}' is not a known time zone.") from None
    return name


def case_zone(investigation: Investigation) -> ZoneInfo:
    return ZoneInfo(investigation.time_zone or "UTC")


def _sees_all(user: User) -> bool:
    return user.role == Role.SUPERVISOR


@dataclass
class NewInvestigation:
    title: str
    case_type: str
    priority: str = "medium"
    location: str = ""
    description: str = ""
    time_zone: str = "UTC"
    tags: list[str] = field(default_factory=list)


def list_investigations(
    db: Session, user: User, filters: InvestigationFilters, limit: int, offset: int
) -> tuple[list[Investigation], int]:
    return repo.list_visible(db, user.id, _sees_all(user), filters, limit, offset)


def get_investigation(db: Session, user: User, reference: str) -> Investigation:
    investigation = repo.get_visible(db, user.id, _sees_all(user), reference)
    if investigation is None:
        raise NotFoundError(NOT_FOUND)
    return investigation


def _require_can_edit(db: Session, user: User, investigation: Investigation) -> None:
    if Permission.INVESTIGATION_WRITE not in permissions_for(user.role):
        raise ForbiddenError("Your role cannot change investigations.")
    if not _sees_all(user) and repo.membership(db, investigation.id, user.id) is None:
        raise ForbiddenError("Only members of the investigation team can change it.")


def create_investigation(
    db: Session, user: User, data: NewInvestigation, context: RequestContext
) -> Investigation:
    reference = repo.next_reference(db, datetime.now(UTC).year)
    investigation = Investigation(
        reference=reference,
        title=data.title.strip(),
        case_type=data.case_type.strip(),
        priority=data.priority,
        location=data.location.strip(),
        description=data.description.strip(),
        time_zone=validate_time_zone(data.time_zone),
        tags=clean_tags(data.tags),
        status="draft",
        stage="intake",
        lead_investigator_id=user.id,
        created_by_id=user.id,
    )
    investigation.members.append(InvestigationMember(user_id=user.id, role_in_case="lead"))
    db.add(investigation)
    db.flush()
    audit_service.record(
        db,
        "investigation.created",
        actor=user,
        object_type="investigation",
        object_id=reference,
        new_state=_snapshot(investigation),
        context=context,
    )
    db.commit()
    return get_investigation(db, user, reference)


def update_investigation(
    db: Session, user: User, reference: str, changes: dict[str, Any], context: RequestContext
) -> Investigation:
    investigation = get_investigation(db, user, reference)
    _require_can_edit(db, user, investigation)
    changes = {k: v for k, v in changes.items() if k in EDITABLE_FIELDS}
    if investigation.status == "archived":
        raise ConflictError("Archived investigations are read-only.")

    new_status = changes.get("status")
    if new_status and new_status != investigation.status:
        if new_status not in ALLOWED_TRANSITIONS[investigation.status]:
            raise ConflictError(
                f"An investigation that is '{investigation.status}' cannot move to "
                f"'{new_status}'. Allowed next: "
                f"{', '.join(sorted(ALLOWED_TRANSITIONS[investigation.status])) or 'none'}."
            )
    if "tags" in changes:
        changes["tags"] = clean_tags(changes["tags"])
    if "time_zone" in changes:
        validate_time_zone(changes["time_zone"])

    before = _snapshot(investigation)
    for key, value in changes.items():
        setattr(investigation, key, value.strip() if isinstance(value, str) else value)
    if investigation.status == "closed":
        investigation.stage = "closed"
    after = _snapshot(investigation)

    changed = {k for k in after if after[k] != before[k]}
    if changed:
        audit_service.record(
            db,
            "investigation.updated",
            actor=user,
            object_type="investigation",
            object_id=investigation.reference,
            previous_state={k: before[k] for k in changed},
            new_state={k: after[k] for k in changed},
            context=context,
        )
        db.commit()
    return get_investigation(db, user, reference)


def add_member(
    db: Session, user: User, reference: str, member_email: str, context: RequestContext
) -> InvestigationMember:
    investigation = get_investigation(db, user, reference)
    _require_can_edit(db, user, investigation)
    new_member = db.scalar(select(User).where(User.email == member_email.strip().lower()))
    if new_member is None or not new_member.is_active:
        raise NotFoundError("No active user has that email address.")
    if Permission.INVESTIGATION_READ not in permissions_for(new_member.role):
        raise ConflictError("This user's role cannot work on investigations.")
    if repo.membership(db, investigation.id, new_member.id):
        raise ConflictError(f"{new_member.display_name} is already on the team.")

    membership = InvestigationMember(investigation_id=investigation.id, user_id=new_member.id)
    db.add(membership)
    audit_service.record(
        db,
        "investigation.member_added",
        actor=user,
        object_type="investigation",
        object_id=investigation.reference,
        new_state={"member": new_member.email, "role_in_case": "member"},
        context=context,
    )
    db.commit()
    db.refresh(membership)
    return membership


def activity(db: Session, user: User, reference: str, limit: int = 50) -> list[AuditLog]:
    """The audit trail of one case — visible to everyone who can see the case."""
    investigation = get_investigation(db, user, reference)
    return list(
        db.scalars(
            select(AuditLog)
            .where(
                AuditLog.object_type == "investigation",
                AuditLog.object_id == investigation.reference,
            )
            .order_by(AuditLog.id.desc())
            .limit(limit)
        )
    )


def assignable_users(db: Session) -> list[User]:
    """Active users whose role can work on investigations (for the "add member" picker)."""
    users = db.scalars(select(User).where(User.is_active).order_by(User.display_name)).all()
    return [u for u in users if Permission.INVESTIGATION_READ in permissions_for(u.role)]


def clean_tags(tags: list[str]) -> list[str]:
    seen: list[str] = []
    for tag in tags:
        tag = tag.strip().lower()
        if tag and tag not in seen:
            seen.append(tag[:40])
    return seen[:10]


def _snapshot(investigation: Investigation) -> dict[str, Any]:
    return {name: getattr(investigation, name) for name in EDITABLE_FIELDS} | {
        "lead_investigator_id": str(investigation.lead_investigator_id)
    }
