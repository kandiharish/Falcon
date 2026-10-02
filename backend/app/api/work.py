"""Tasks (plan §30) and notifications (plan §29)."""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Notification, Task, User
from app.security.dependencies import current_user, require_permission
from app.security.permissions import Permission
from app.services import notification_service, task_service
from app.services.request_context import request_context

router = APIRouter(tags=["work"])
Reader = Annotated[User, Depends(require_permission(Permission.INVESTIGATION_READ))]
Manager = Annotated[User, Depends(require_permission(Permission.TASK_MANAGE))]
Me = Annotated[User, Depends(current_user)]
DB = Annotated[Session, Depends(get_db)]

TaskStatus = Literal["todo", "in_progress", "review", "completed"]
Priority = Literal["low", "medium", "high", "critical"]


class Person(BaseModel):
    id: uuid.UUID
    display_name: str


class TaskOut(BaseModel):
    reference: str
    investigation_reference: str
    investigation_title: str
    title: str
    description: str
    status: TaskStatus
    priority: Priority
    assignee: Person | None
    due_date: date | None
    evidence: list[str]
    created_by: Person
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class TaskIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field("", max_length=5000)
    status: TaskStatus = "todo"
    priority: Priority = "medium"
    assignee_id: uuid.UUID | None = None
    due_date: date | None = None
    evidence: list[str] = Field(default_factory=list, max_length=50)


class TaskPatch(BaseModel):
    """Only the fields that are sent are changed; send assignee_id: null to unassign."""

    title: str | None = Field(None, min_length=3, max_length=200)
    description: str | None = Field(None, max_length=5000)
    status: TaskStatus | None = None
    priority: Priority | None = None
    assignee_id: uuid.UUID | None = None
    due_date: date | None = None
    evidence: list[str] | None = Field(None, max_length=50)


class NotificationOut(BaseModel):
    id: uuid.UUID
    kind: str
    title: str
    body: str
    link: str
    created_at: datetime
    read: bool


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    unread: int


def task_out(t: Task) -> TaskOut:
    return TaskOut(
        reference=t.reference,
        investigation_reference=t.investigation.reference,
        investigation_title=t.investigation.title,
        title=t.title,
        description=t.description,
        status=t.status,  # type: ignore[arg-type]
        priority=t.priority,  # type: ignore[arg-type]
        assignee=Person(id=t.assignee.id, display_name=t.assignee.display_name)
        if t.assignee
        else None,
        due_date=t.due_date,
        evidence=[e.reference for e in t.evidence],
        created_by=Person(id=t.created_by.id, display_name=t.created_by.display_name),
        created_at=t.created_at,
        updated_at=t.updated_at,
        completed_at=t.completed_at,
    )


def _changes(body: TaskIn | TaskPatch) -> task_service.TaskChanges:
    sent = body.model_dump(exclude_unset=True) if isinstance(body, TaskPatch) else body.model_dump()
    return task_service.TaskChanges(
        **{
            ("evidence_references" if k == "evidence" else k): v
            for k, v in sent.items()
            if k != "title"
        }
    )


@router.get("/investigations/{case_reference}/tasks", response_model=list[TaskOut])
def list_tasks(
    case_reference: str, user: Reader, db: DB, status: TaskStatus | None = None, mine: bool = False
) -> list[TaskOut]:
    return [task_out(t) for t in task_service.list_tasks(db, user, case_reference, status, mine)]


@router.post(
    "/investigations/{case_reference}/tasks",
    response_model=TaskOut,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    case_reference: str, body: TaskIn, request: Request, user: Manager, db: DB
) -> TaskOut:
    task = task_service.create_task(
        db, user, case_reference, body.title, _changes(body), request_context(request)
    )
    return task_out(task)


@router.patch("/investigations/{case_reference}/tasks/{reference}", response_model=TaskOut)
def update_task(
    case_reference: str, reference: str, body: TaskPatch, request: Request, user: Manager, db: DB
) -> TaskOut:
    changes = _changes(body)
    if body.title is not None:
        changes.title = body.title
    task = task_service.update_task(
        db, user, case_reference, reference, changes, request_context(request)
    )
    return task_out(task)


@router.get("/tasks/mine", response_model=list[TaskOut])
def my_tasks(user: Reader, db: DB, include_completed: bool = False) -> list[TaskOut]:
    return [task_out(t) for t in task_service.my_tasks(db, user, include_completed)]


@router.get("/notifications", response_model=NotificationPage)
def notifications(user: Me, db: DB, unread_only: bool = False) -> NotificationPage:
    rows, unread = notification_service.list_for(db, user, unread_only, limit=30)
    return NotificationPage(items=[_notification(n) for n in rows], unread=unread)


@router.post("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def read_one(notification_id: uuid.UUID, user: Me, db: DB) -> None:
    notification_service.mark_read(db, user, notification_id)


@router.post("/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT)
def read_all(user: Me, db: DB) -> None:
    notification_service.mark_read(db, user, None)


def _notification(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=n.id,
        kind=n.kind,
        title=n.title,
        body=n.body,
        link=n.link,
        created_at=n.created_at,
        read=n.read_at is not None,
    )
