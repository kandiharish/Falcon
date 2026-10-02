"""Tasks and notifications."""

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import AuditLog
from tests.helpers import process_latest_job, signed_in, upload


def _ids(client):
    return client.get("/api/auth/me").json()["id"]


def test_task_lifecycle_is_audited_and_notifies_the_assignee(team):
    officer, analyst, case = team["officer"], team["analyst"], team["case"]
    upload(officer, case, b"Report text.", "report.txt", "document")
    analyst_id = _ids(analyst)

    created = officer.post(
        f"/api/investigations/{case}/tasks",
        json={
            "title": "Verify the CCTV timestamp",
            "priority": "high",
            "assignee_id": analyst_id,
            "due_date": "2026-10-05",
            "evidence": ["doc-001"],
        },
    )
    assert created.status_code == 201, created.text
    task = created.json()
    assert task["reference"] == "T-001" and task["evidence"] == ["DOC-001"]
    assert task["assignee"]["id"] == analyst_id

    inbox = analyst.get("/api/notifications").json()
    # Newest first: the task, then being added to the team (by the fixture).
    assert [n["kind"] for n in inbox["items"]] == ["task_assigned", "investigation_assigned"]
    assert "T-001" in inbox["items"][0]["title"]
    assert officer.get("/api/notifications").json()["unread"] == 0  # not for your own action

    moved = analyst.patch(f"/api/investigations/{case}/tasks/T-001", json={"status": "completed"})
    assert moved.json()["status"] == "completed" and moved.json()["completed_at"]
    assert analyst.get("/api/tasks/mine").json() == []  # completed tasks leave "my tasks"
    assert len(analyst.get("/api/tasks/mine", params={"include_completed": True}).json()) == 1

    unassigned = officer.patch(
        f"/api/investigations/{case}/tasks/T-001", json={"assignee_id": None}
    )
    assert unassigned.json()["assignee"] is None
    with SessionLocal() as db:
        updates = db.scalars(
            select(AuditLog).where(
                AuditLog.object_id == f"{case}/T-001", AuditLog.action == "task.updated"
            )
        ).all()
    assert [u.new_state for u in updates][0]["status"] == "completed"


def test_task_rules(team, make_user):
    officer, case = team["officer"], team["case"]
    outsider = make_user("forensic_analyst")
    base = f"/api/investigations/{case}/tasks"
    not_member = officer.post(base, json={"title": "Check", "assignee_id": str(outsider.id)})
    assert not_member.status_code == 422
    assert officer.post(base, json={"title": "Check", "evidence": ["NOPE-001"]}).status_code == 422
    assert officer.post(base, json={"title": "x"}).status_code == 422
    assert signed_in(outsider).get(base).status_code == 404  # hidden case


def test_notifications_from_processing_and_team_changes(team, make_user):
    officer, case = team["officer"], team["case"]
    upload(officer, case, b"Plain report.", "report.txt", "document")
    process_latest_job(case, "DOC-001")
    inbox = officer.get("/api/notifications").json()
    assert inbox["items"][0]["title"] == "DOC-001 processed"
    assert inbox["items"][0]["link"].endswith("/evidence/DOC-001")

    newcomer = make_user("forensic_analyst")
    officer.post(f"/api/investigations/{case}/members", json={"email": newcomer.email})
    newcomer_client = signed_in(newcomer)
    assert (
        newcomer_client.get("/api/notifications").json()["items"][0]["kind"]
        == "investigation_assigned"
    )

    first = inbox["items"][0]["id"]
    assert officer.post(f"/api/notifications/{first}/read").status_code == 204
    assert officer.get("/api/notifications", params={"unread_only": True}).json()["items"] == []
    # Someone else's notification cannot be marked read by me.
    other = newcomer_client.get("/api/notifications").json()["items"][0]["id"]
    officer.post(f"/api/notifications/{other}/read")
    assert newcomer_client.get("/api/notifications").json()["unread"] == 1
    newcomer_client.post("/api/notifications/read-all")
    assert newcomer_client.get("/api/notifications").json()["unread"] == 0


def test_reassigning_a_task_notifies_the_new_assignee(team, make_user):
    officer, case = team["officer"], team["case"]
    second = make_user("evidence_analyst")
    officer.post(f"/api/investigations/{case}/members", json={"email": second.email})
    officer.post(f"/api/investigations/{case}/tasks", json={"title": "Label the photos"})
    changed = officer.patch(
        f"/api/investigations/{case}/tasks/T-001", json={"assignee_id": str(second.id)}
    )
    assert changed.json()["assignee"]["id"] == str(second.id)
    kinds = [n["kind"] for n in signed_in(second).get("/api/notifications").json()["items"]]
    assert kinds[0] == "task_assigned"
    with SessionLocal() as db:
        update = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "task.updated", AuditLog.object_id == f"{case}/T-001"
            )
        )
    assert update.previous_state == {"assignee_id": None}
    assert update.new_state == {"assignee_id": str(second.id)}
