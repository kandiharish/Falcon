"""Investigation reports: generation, observed vs interpretation, integrity, rules."""

import hashlib

from sqlalchemy import select, update

from app.db.session import SessionLocal
from app.models import AuditLog, Report
from tests.helpers import process_latest_job, signed_in, upload

CALLS_CSV = (
    b"caller,callee,started_at,duration_s\n"
    b"+1-202-555-0101,+1-202-555-0102,2026-09-28T20:33:00+05:30,95\n"
)


def _case_with_calls(team):
    officer, case = team["officer"], team["case"]
    upload(officer, case, CALLS_CSV, "calls.csv", "call_records")
    process_latest_job(case, "CALL-001")
    return officer, case


def test_report_snapshot_is_complete_fingerprinted_and_exportable(team):
    officer, case = _case_with_calls(team)
    created = officer.post(
        f"/api/investigations/{case}/reports",
        json={
            "title": "Interim report",
            "analyst_notes": "Calls cluster at 20:33.",
            "limitations": "No subscriber data yet.",
        },
    )
    assert created.status_code == 201, created.text
    report = created.json()
    assert report["reference"] == "RPT-001" and report["status"] == "ready" and report["intact"]
    content = report["content"]
    assert content["scope"]["counts"]["evidence"] == 1
    assert [e["reference"] for e in content["timeline"]] == ["E001"]
    assert content["relationships"][0]["type"] == "communicated_with"
    assert content["analyst_notes"]["written"] == "Calls cluster at 20:33."
    assert content["limitations"]["written"] == "No subscriber data yet."
    assert any("not yet been reviewed" in n for n in content["limitations"]["automatic"])
    assert content["evidence"][0]["sha256"]  # evidence fingerprints are in the report

    exported = officer.get(f"/api/investigations/{case}/reports/RPT-001/export")
    assert exported.headers["content-disposition"].endswith('RPT-001.json"')
    assert hashlib.sha256(exported.content).hexdigest() == report["content_sha256"]
    with SessionLocal() as db:
        actions = set(
            db.scalars(select(AuditLog.action).where(AuditLog.object_id == f"{case}/RPT-001"))
        )
    assert actions == {"report.generated", "report.exported"}


def test_rejected_items_are_left_out_and_pending_can_be_excluded(team):
    officer, case = _case_with_calls(team)
    team["analyst"].post(
        f"/api/investigations/{case}/events/E001/review",
        json={"review_status": "rejected", "note": "Test"},
    )
    content = officer.post(
        f"/api/investigations/{case}/reports", json={"title": "Without the call"}
    ).json()["content"]
    assert content["timeline"] == []
    confirmed_only = officer.post(
        f"/api/investigations/{case}/reports",
        json={"title": "Confirmed only", "include_pending": False},
    ).json()["content"]
    assert confirmed_only["entities"] == [] and confirmed_only["scope"]["included"].startswith(
        "Only"
    )


def test_tampering_with_a_stored_report_is_detected(team):
    officer, case = _case_with_calls(team)
    officer.post(f"/api/investigations/{case}/reports", json={"title": "Original"})
    with SessionLocal() as db:
        report = db.scalar(select(Report).where(Report.title == "Original"))
        changed = {
            **report.content,
            "summary": {**report.content["summary"], "title": "Edited later"},
        }
        db.execute(update(Report).where(Report.id == report.id).values(content=changed))
        db.commit()
    assert officer.get(f"/api/investigations/{case}/reports/RPT-001").json()["intact"] is False


def test_who_may_generate_and_see_reports(team, make_user):
    officer, case = team["officer"], team["case"]
    evidence_analyst = make_user("evidence_analyst")
    officer.post(f"/api/investigations/{case}/members", json={"email": evidence_analyst.email})
    assert (
        signed_in(evidence_analyst)
        .post(f"/api/investigations/{case}/reports", json={"title": "Mine"})
        .status_code
        == 403
    )
    colleague = make_user("incident_investigator")
    officer.post(f"/api/investigations/{case}/members", json={"email": colleague.email})
    signed_in(colleague).post(
        f"/api/investigations/{case}/reports", json={"title": "By a colleague"}
    )
    kinds = [n["kind"] for n in officer.get("/api/notifications").json()["items"]]
    assert "report_ready" in kinds  # the lead hears about it
    outsider = signed_in(make_user("investigation_officer"))
    assert outsider.get(f"/api/investigations/{case}/reports").status_code == 404
