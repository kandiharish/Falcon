"""Investigation tasks (plan §30): To Do → In Progress → Review → Completed.

Rules:
  • anyone who can see the case can see its tasks;
  • team members with task:manage create and change them, while the case is open;
  • a task can only be assigned to a member of the case team;
  • every change is audited with the before/after values, and the new assignee is notified.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import case as sql_case
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Evidence, Investigation, InvestigationMember, Task, User
from app.repositories import reference_counters
from app.security.permissions import Permission, Role, permissions_for
from app.services import audit_service, investigation_service, notification_service
from app.services.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError
from app.services.request_context import RequestContext

UNSET: Any = object()  # "field not sent" — different from "sent as empty"


@dataclass
class TaskChanges:
    title: Any = UNSET
    description: Any = UNSET
    status: Any = UNSET
    priority: Any = UNSET
    assignee_id: Any = UNSET  # uuid or None (= unassigned)
    due_date: Any = UNSET
    evidence_references: Any = UNSET  # list[str]
    extra: dict[str, Any] = field(default_factory=dict)


def _query():
    return select(Task).options(
        selectinload(Task.assignee),
        selectinload(Task.created_by),
        selectinload(Task.evidence),
        selectinload(Task.investigation),
    )


def list_tasks(
    db: Session, user: User, case_reference: str, status: str | None = None, mine: bool = False
) -> list[Task]:
    case = investigation_service.get_investigation(db, user, case_reference)
    query = _query().where(Task.investigation_id == case.id)
    if status:
        query = query.where(Task.status == status)
    if mine:
        query = query.where(Task.assignee_id == user.id)
    return list(db.scalars(query.order_by(*_order())))


def my_tasks(db: Session, user: User, include_completed: bool = False) -> list[Task]:
    """Tasks assigned to me, in every case I can still see (removed from a team = hidden)."""
    query = _query().where(Task.assignee_id == user.id)
    if not investigation_service.sees_all(user):
        my_cases = select(InvestigationMember.investigation_id).where(
            InvestigationMember.user_id == user.id
        )
        query = query.where(Task.investigation_id.in_(my_cases))
    if not include_completed:
        query = query.where(Task.status != "completed")
    return list(db.scalars(query.order_by(*_order()).limit(200)))


def _order():
    status_rank = sql_case(
        {"in_progress": 0, "review": 1, "todo": 2, "completed": 3}, value=Task.status
    )
    priority_rank = sql_case({"critical": 0, "high": 1, "medium": 2, "low": 3}, value=Task.priority)
    return (status_rank, Task.due_date.asc().nulls_last(), priority_rank, Task.reference)


def get_task(db: Session, user: User, case_reference: str, reference: str) -> Task:
    case = investigation_service.get_investigation(db, user, case_reference)
    task = db.scalar(
        _query().where(Task.investigation_id == case.id, Task.reference == reference.upper())
    )
    if task is None:
        raise NotFoundError("This task does not exist in this investigation.")
    return task


def create_task(
    db: Session,
    user: User,
    case_reference: str,
    title: str,
    changes: TaskChanges,
    context: RequestContext,
) -> Task:
    case = _require_manager(db, user, case_reference)
    number = reference_counters.next_value(db, case.id, "T")
    task = Task(
        investigation_id=case.id,
        reference=f"T-{number:03d}",
        title=_title(title),
        created_by_id=user.id,
    )
    db.add(task)
    _apply(db, case, task, changes)
    db.flush()
    audit_service.record(
        db,
        "task.created",
        actor=user,
        object_type="task",
        object_id=f"{case.reference}/{task.reference}",
        new_state=_snapshot(task),
        context=context,
    )
    _notify_assignee(db, user, case, task, None)
    db.commit()
    return get_task(db, user, case.reference, task.reference)


def update_task(
    db: Session,
    user: User,
    case_reference: str,
    reference: str,
    changes: TaskChanges,
    context: RequestContext,
) -> Task:
    case = _require_manager(db, user, case_reference)
    task = get_task(db, user, case_reference, reference)
    before = _snapshot(task)
    previous_assignee = task.assignee_id
    if changes.title is not UNSET:
        task.title = _title(changes.title)
    _apply(db, case, task, changes)
    db.flush()  # writes the new assignee_id, so the snapshot and notification see it
    after = _snapshot(task)
    changed = {k for k in after if after[k] != before[k]}
    if not changed:
        return task
    audit_service.record(
        db,
        "task.updated",
        actor=user,
        object_type="task",
        object_id=f"{case.reference}/{task.reference}",
        previous_state={k: before[k] for k in changed},
        new_state={k: after[k] for k in changed},
        context=context,
    )
    _notify_assignee(db, user, case, task, previous_assignee)
    db.commit()
    return get_task(db, user, case.reference, task.reference)


def _apply(db: Session, case: Investigation, task: Task, c: TaskChanges) -> None:
    if c.description is not UNSET:
        task.description = (c.description or "").strip()[:5000]
    if c.priority is not UNSET:
        task.priority = c.priority
    if c.due_date is not UNSET:
        task.due_date = c.due_date
    if c.status is not UNSET and c.status != task.status:
        task.status = c.status
        task.completed_at = datetime.now(UTC) if c.status == "completed" else None
    if c.assignee_id is not UNSET:
        if c.assignee_id is not None and not _is_team_member(db, case, c.assignee_id):
            raise InvalidInputError("A task can only be assigned to a member of the case team.")
        # Set the relationship, not just the column: an already-loaded `assignee` object
        # would otherwise keep showing the previous person until the next reload.
        task.assignee = db.get(User, c.assignee_id) if c.assignee_id else None
    if c.evidence_references is not UNSET:
        refs = sorted({r.strip().upper() for r in c.evidence_references if r.strip()})
        found = list(
            db.scalars(
                select(Evidence).where(
                    Evidence.investigation_id == case.id, Evidence.reference.in_(refs)
                )
            )
        )
        missing = set(refs) - {e.reference for e in found}
        if missing:
            raise InvalidInputError(f"Not evidence in this case: {', '.join(sorted(missing))}.")
        task.evidence = found


def _notify_assignee(
    db: Session, actor: User, case: Investigation, task: Task, previous: uuid.UUID | None
) -> None:
    if task.assignee_id and task.assignee_id != previous:
        due = f" Due {task.due_date.isoformat()}." if task.due_date else ""
        notification_service.notify(
            db,
            task.assignee_id,
            "task_assigned",
            f"Task {task.reference} assigned to you",
            body=f"{task.title} ({case.reference}).{due}",
            link=f"/tasks?case={case.reference}&task={task.reference}",
            investigation_id=case.id,
            actor=actor,
        )


def _snapshot(task: Task) -> dict[str, Any]:
    return {
        "title": task.title,
        "status": task.status,
        "priority": task.priority,
        "assignee_id": str(task.assignee_id) if task.assignee_id else None,
        "due_date": task.due_date.isoformat() if isinstance(task.due_date, date) else None,
        "evidence": [e.reference for e in task.evidence],
    }


def _title(value: str) -> str:
    title = (value or "").strip()
    if len(title) < 3:
        raise InvalidInputError("Give the task a name of at least 3 characters.")
    return title[:200]


def _is_team_member(db: Session, case: Investigation, user_id: uuid.UUID) -> bool:
    return (
        db.scalar(
            select(InvestigationMember).where(
                InvestigationMember.investigation_id == case.id,
                InvestigationMember.user_id == user_id,
            )
        )
        is not None
    )


def _require_manager(db: Session, user: User, case_reference: str) -> Investigation:
    case = investigation_service.get_investigation(db, user, case_reference)
    if Permission.TASK_MANAGE not in permissions_for(user.role):
        raise ForbiddenError("Your role cannot manage tasks.")
    if user.role != Role.SUPERVISOR and not _is_team_member(db, case, user.id):
        raise ForbiddenError("Only members of the investigation team can manage its tasks.")
    if case.status in ("closed", "archived"):
        raise ConflictError(f"The investigation is {case.status}; its tasks can no longer change.")
    return case
