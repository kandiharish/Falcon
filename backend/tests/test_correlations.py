"""Correlation service + API tests: automatic runs, explanations, review rules, stale results."""

from tests.helpers import process_latest_job, signed_in, upload

# Valid-format fictional numbers (555-01xx): free-text detection only accepts VALID numbers.
CALLS_CSV = (
    b"caller,callee,started_at,duration_s\n"
    b"+1-202-555-0101,+1-202-555-0102,2026-09-28T20:33:00+05:30,95\n"
)
REPORT = b"Report: the caller used +1 202-555-0102 that night.\n"


def sightings(minute: int, lat_offset: float = 0.0) -> bytes:
    return (
        f"plate,seen_at,camera,latitude,longitude\n"
        f"ZZ99 ZZ 0001,2026-09-28T20:{minute:02d}:00+05:30,GATE-02,"
        f"{17.43862 + lat_offset:.5f},78.39215\n"
    ).encode()


def correlations(client, case, **params):
    return client.get(f"/api/investigations/{case}/correlations", params=params).json()["items"]


def test_shared_vehicle_close_in_time_and_place_is_high_and_explained(team):
    client, case = team["officer"], team["case"]
    upload(client, case, sightings(37), "anpr_gate.csv", "vehicle")
    upload(client, case, sightings(38, 0.0004), "anpr_cam2.csv", "vehicle")
    process_latest_job(case, "VEH-001")
    process_latest_job(case, "VEH-002")  # processing re-runs correlation automatically

    [found] = correlations(client, case)
    assert {found["evidence_a"]["reference"], found["evidence_b"]["reference"]} == {
        "VEH-001",
        "VEH-002",
    }
    assert found["level"] == "high"
    kinds = {f["kind"]: f for f in found["factors"]}
    assert set(kinds) == {"entity", "time", "location"}
    assert kinds["time"]["details"]["seconds_apart"] == 60
    assert 40 <= kinds["location"]["details"]["metres_apart"] <= 48
    assert "ZZ99 ZZ 0001" in kinds["entity"]["explanation"]
    assert round(sum(f["contribution"] for f in found["factors"]), 3) == round(found["score"], 3)

    detail = client.get(f"/api/investigations/{case}/correlations/{found['reference']}").json()
    assert len(detail["supporting_events"]) == 2  # the two sightings behind the time/place factors


def test_shared_phone_alone_gives_a_low_entity_only_correlation(team):
    client, case = team["officer"], team["case"]
    upload(client, case, CALLS_CSV, "calls.csv", "call_records")
    upload(client, case, REPORT, "report.txt", "document")
    process_latest_job(case, "CALL-001")
    process_latest_job(case, "DOC-001")
    [found] = correlations(client, case)
    assert [f["kind"] for f in found["factors"]] == ["entity"]
    assert found["level"] == "low"


def test_rerunning_changes_nothing_when_nothing_changed(team):
    client, case = team["officer"], team["case"]
    upload(client, case, sightings(37), "a.csv", "vehicle")
    upload(client, case, sightings(39), "b.csv", "vehicle")
    process_latest_job(case, "VEH-001")
    process_latest_job(case, "VEH-002")
    result = client.post(f"/api/investigations/{case}/correlations/run").json()
    assert result == {"created": 0, "updated": 0, "removed": 0, "stale": 0, "total": 1}


def test_review_rules(team, make_user):
    client, case = team["officer"], team["case"]
    upload(client, case, sightings(37), "a.csv", "vehicle")
    upload(client, case, sightings(39), "b.csv", "vehicle")
    process_latest_job(case, "VEH-001")
    process_latest_job(case, "VEH-002")
    ref = correlations(client, case)[0]["reference"]
    url = f"/api/investigations/{case}/correlations/{ref}/review"

    assert client.post(url, json={"review_status": "rejected"}).status_code == 422  # reason needed
    evidence_analyst = make_user("evidence_analyst")
    client.post(f"/api/investigations/{case}/members", json={"email": evidence_analyst.email})
    assert (
        signed_in(evidence_analyst).post(url, json={"review_status": "confirmed"}).status_code
        == 403
    )

    confirmed = (
        team["analyst"].post(url, json={"review_status": "confirmed", "note": "Same van"}).json()
    )
    assert confirmed["review_status"] == "confirmed"
    assert confirmed["reviewed_by"] is not None
    history = client.get(f"/api/investigations/{case}").json()
    assert history["counts"]["correlations"] == 1


def test_reviewed_correlations_become_stale_instead_of_disappearing(team):
    client, case = team["officer"], team["case"]
    upload(client, case, CALLS_CSV, "calls.csv", "call_records")
    upload(client, case, REPORT, "report.txt", "document")
    process_latest_job(case, "CALL-001")
    process_latest_job(case, "DOC-001")
    ref = correlations(client, case)[0]["reference"]
    team["analyst"].post(
        f"/api/investigations/{case}/correlations/{ref}/review", json={"review_status": "confirmed"}
    )

    # The analyst rejects the shared phone: the relationship no longer holds…
    phone = client.get(f"/api/investigations/{case}/entities", params={"search": "5550102"}).json()
    team["analyst"].post(
        f"/api/investigations/{case}/entities/{phone['items'][0]['reference']}/review",
        json={"review_status": "rejected", "note": "OCR misread"},
    )
    [kept] = correlations(client, case)
    assert (
        kept["stale"] is True and kept["review_status"] == "confirmed"
    )  # …but the decision is kept
    assert correlations(client, case, include_stale="false") == []


def test_pending_correlations_disappear_when_no_longer_supported(team):
    client, case = team["officer"], team["case"]
    upload(client, case, CALLS_CSV, "calls.csv", "call_records")
    upload(client, case, REPORT, "report.txt", "document")
    process_latest_job(case, "CALL-001")
    process_latest_job(case, "DOC-001")
    phone = client.get(f"/api/investigations/{case}/entities", params={"search": "5550102"}).json()
    team["analyst"].post(
        f"/api/investigations/{case}/entities/{phone['items'][0]['reference']}/review",
        json={"review_status": "rejected", "note": "wrong number"},
    )
    assert correlations(client, case) == []


def test_non_members_cannot_see_correlations(team, make_user):
    outsider = signed_in(make_user("investigation_officer"))
    assert outsider.get(f"/api/investigations/{team['case']}/correlations").status_code == 404
