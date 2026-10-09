"""Create fictional demo tasks for the Riverside case. Development only.

    uv run python -m app.scripts.seed_demo_work

Needs the demo users, investigations and evidence first. Uses the real task service, so the
demo also gets the audit entries and notifications a real team would see.
"""

import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Investigation, Task, User
from app.services import task_service
from app.services.request_context import RequestContext

CASE = "CASE-2026-001"
# Due dates are days from the reset, so a demo never looks stale: one task is overdue.
TASKS = [
    {
        "title": "Verify the CCTV-001 camera clock against GPS-001 time",
        "description": (
            "The rear-door camera may run fast or slow. Compare with GPS fixes from DEVICE-A7."
        ),
        "assignee": "a.kumar@falcon.example",
        "priority": "high",
        "status": "in_progress",
        "due_in_days": 2,
        "evidence": ["CCTV-001", "GPS-001"],
    },
    {
        "title": "Review COR-001: same van at the rear door and the gate",
        "description": (
            "High potential relationship between the CCTV clip and the plate-camera log."
        ),
        "assignee": "a.kumar@falcon.example",
        "priority": "high",
        "status": "review",
        "due_in_days": 1,
        "evidence": ["CCTV-001", "VEH-001"],
    },
    {
        "title": "Request subscriber details for +1 202-555-0102",
        "description": (
            "Formal request to the (fictional) network operator for the number called at 20:33."
        ),
        "assignee": "r.varma@falcon.example",
        "priority": "medium",
        "status": "todo",
        "due_in_days": 5,
        "evidence": ["CALL-001"],
    },
    {
        "title": "Re-scan the WIT-001 statement at higher resolution",
        "description": (
            "OCR confidence is 68 %. A clearer scan should make names and numbers reliable."
        ),
        "assignee": "m.das@falcon.example",
        "priority": "low",
        "status": "todo",
        "due_in_days": -1,
        "evidence": ["WIT-001"],
    },
    {
        "title": "Record chain of custody for the first responder's photo",
        "description": "Who took IMG-001, on which device, and how it reached the case.",
        "assignee": "m.das@falcon.example",
        "priority": "medium",
        "status": "completed",
        "due_in_days": -3,
        "evidence": ["IMG-001"],
    },
]


def main() -> int:
    if get_settings().environment != "development":
        print("Refusing to seed demo tasks outside development.")
        return 1
    context = RequestContext(ip_address=None, user_agent="seed_demo_work")
    with SessionLocal() as db:
        case = db.scalar(select(Investigation).where(Investigation.reference == CASE))
        if case is None:
            print(f"{CASE} not found: run the investigation and evidence seeds first.")
            return 1
        if db.scalar(select(Task).where(Task.investigation_id == case.id)):
            print("Demo tasks already exist; skipped.")
            return 0
        today = datetime.now(UTC).date()
        lead = db.get(User, case.lead_investigator_id)
        people = {u.email: u for u in db.scalars(select(User))}
        for spec in TASKS:
            task_service.create_task(
                db,
                lead,
                CASE,
                spec["title"],
                task_service.TaskChanges(
                    description=spec["description"],
                    priority=spec["priority"],
                    status=spec["status"],
                    assignee_id=people[spec["assignee"]].id,
                    due_date=today + timedelta(days=spec["due_in_days"]),
                    evidence_references=spec["evidence"],
                ),
                context,
            )
        print(f"Created {len(TASKS)} demo tasks in {CASE}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
