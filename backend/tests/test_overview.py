"""Dashboard and global search: real counts, only from visible cases."""

from tests.helpers import process_latest_job, signed_in, upload

CALLS_CSV = (
    b"caller,callee,started_at,duration_s\n"
    b"+1-202-555-0101,+1-202-555-0102,2026-09-28T20:33:00+05:30,95\n"
)


def test_dashboard_counts_only_my_cases(team, make_user):
    officer, case = team["officer"], team["case"]
    upload(officer, case, CALLS_CSV, "calls.csv", "call_records")
    process_latest_job(case, "CALL-001")
    officer.post(
        f"/api/investigations/{case}/tasks",
        json={"title": "Check the call log", "due_date": "2020-01-01"},
    )

    board = officer.get("/api/dashboard").json()
    m = board["metrics"]
    assert m["evidence_items"] == 1 and m["events"] == 1 and m["entities"] == 2
    assert m["open_tasks"] == 1 and m["requires_review"] >= 3  # 2 entities + 1 event pending
    assert board["evidence_by_type"] == {"call_records": 1}
    assert board["event_activity"]["unit"] == "hour"
    assert any(b["count"] == 1 for b in board["event_activity"]["buckets"])
    assert any("overdue" in a["title"] for a in board["alerts"])
    assert board["recent_investigations"][0]["reference"] == case

    stranger = signed_in(make_user("investigation_officer")).get("/api/dashboard").json()
    assert stranger["metrics"]["evidence_items"] == 0  # someone else's case is invisible
    admin = signed_in(make_user("system_admin"))
    assert admin.get("/api/dashboard").status_code == 403  # administrators do not read cases


def test_global_search_across_kinds_and_cases(team, make_user):
    officer, case = team["officer"], team["case"]
    upload(officer, case, CALLS_CSV, "calls.csv", "call_records")
    process_latest_job(case, "CALL-001")
    hits = officer.get("/api/search", params={"q": "202 555 0102"}).json()
    assert [h["kind"] for h in hits] == ["entity"] and hits[0]["link"].endswith("/entities/PH002")
    kinds = {h["kind"] for h in officer.get("/api/search", params={"q": "CALL"}).json()}
    assert "evidence" in kinds
    other = signed_in(make_user("investigation_officer"))
    assert other.get("/api/search", params={"q": "CALL-001"}).json() == []
