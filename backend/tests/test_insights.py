"""Insights: the pure rules (clock drift, gaps, owners) and cross-case privacy via the API."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.insights import engine as ins
from tests.helpers import process_latest_job, signed_in, upload

IST = ZoneInfo("Asia/Kolkata")
T = datetime(2026, 10, 7, 14, 12, 15, tzinfo=UTC)  # 19:42:15 in India
SCENE = (17.48720, 78.39010)
BIKE = ins.EntityRef("V001", "vehicle", "TG 09 ZZ 0001")


def event(ref, evidence, kind, when, place=SCENE, who=(BIKE,), event_type="vehicle_detected"):
    lat, lon = place if place else (None, None)
    return ins.EventInfo(ref, evidence, kind, event_type, when, lat, lon, "", tuple(who))


def kinds(insights):
    return [i.kind for i in insights]


def test_a_camera_clock_running_fast_is_spotted_and_explained():
    anpr = event("E1", "VEH-001", "vehicle", T)
    cctv = event("E2", "CCTV-001", "video", T + timedelta(seconds=117), (17.48745, 78.39030))
    [drift] = ins.analyse(ins.CaseFacts(IST, events=[anpr, cctv]))

    assert drift.kind == "clock_drift" and drift.severity == "high"
    assert drift.title == "CCTV-001's clock appears to run 1 min 57 s fast (ahead)"
    assert "19:42:15" in drift.detail and "19:44:12" in drift.detail  # case-local times
    assert drift.evidence == ["CCTV-001", "VEH-001"] and drift.entities == ["V001"]
    assert "does not change the times" in drift.action


def test_small_differences_far_places_and_two_network_clocks_are_not_drift():
    anpr = event("E1", "VEH-001", "vehicle", T)
    seconds_apart = event("E2", "CCTV-001", "video", T + timedelta(seconds=10))
    far_away = event("E3", "IMG-001", "image", T + timedelta(minutes=2), (17.50, 78.40))
    gps = event("E4", "GPS-001", "gps", T + timedelta(seconds=20))  # vs ANPR: both network
    found = ins.analyse(ins.CaseFacts(IST, events=[anpr, seconds_apart, far_away, gps]))
    assert "clock_drift" not in kinds(found)


def test_a_long_unexplained_gap_in_sightings_asks_for_cctv():
    at_jntu = event("E1", "VEH-001", "vehicle", T, (17.49380, 78.39190))
    an_hour_later = event(
        "E2", "VEH-001", "vehicle", T + timedelta(minutes=61), (17.48390, 78.41210)
    )
    [gap] = ins.analyse(ins.CaseFacts(IST, events=[at_jntu, an_hour_later]))

    assert gap.kind == "sighting_gap" and gap.title == "TG 09 ZZ 0001 is not seen for 1 h 1 min"
    assert "2.4 km away" in gap.detail
    assert gap.letter["kind"] == "cctv_preservation" and gap.letter["entity"] == "V001"


def test_unknown_phone_account_and_handset_owners_suggest_the_right_request():
    a = ins.EntityRef("PH001", "phone_number", "+91 90000 01111")
    b = ins.EntityRef("PH002", "phone_number", "+91 90000 02222")
    upi = ins.EntityRef("A001", "account", "suresh.k.demo@upi")
    imei = ins.EntityRef("D001", "device", "IMEI-860000000000011")
    events = [
        event("E1", "CALL-001", "call_records", T, None, (a, b), "call_made"),
        event("E2", "TXN-001", "financial", T, None, (upi,), "transaction_completed"),
        event("E3", "GPS-001", "gps", T, SCENE, (imei,), "location_recorded"),
    ]
    letters = {i.entities[0]: i.letter["kind"] for i in ins.analyse(ins.CaseFacts(IST, events))}
    assert letters == {
        "PH001": "telecom_subscriber",
        "PH002": "telecom_subscriber",
        "A001": "bank_kyc",
        "D001": "telecom_imei",
    }


def test_another_case_is_named_only_if_the_user_may_open_it():
    facts = ins.CaseFacts(
        IST,
        other_cases=[
            ins.OtherCase(BIKE, "CASE-2026-003", "Two-wheeler thefts"),
            ins.OtherCase(BIKE, None, None),
        ],
    )
    named, hidden = ins.analyse(facts)
    assert named.title == "TG 09 ZZ 0001 also appears in CASE-2026-003"
    assert hidden.title == "TG 09 ZZ 0001 appears in 1 other investigation you cannot open"
    assert "CASE" not in hidden.detail and "supervisor" in hidden.action


ANPR = (
    b"plate,seen_at,camera,latitude,longitude\n"
    b"TG 09 ZZ 0001,2026-10-07T19:42:15+05:30,CC03,17.4872,78.3901\n"
)


def test_cross_case_matches_respect_case_membership(make_user):
    officer_user, analyst_user = make_user("investigation_officer"), make_user("forensic_analyst")
    officer = signed_in(officer_user)
    case_a = officer.post(
        "/api/investigations", json={"title": "Snatching", "case_type": "Robbery"}
    )
    case_b = officer.post("/api/investigations", json={"title": "Bike theft", "case_type": "Theft"})
    case_a, case_b = case_a.json()["reference"], case_b.json()["reference"]
    officer.post(f"/api/investigations/{case_a}/members", json={"email": analyst_user.email})
    for case in (case_a, case_b):
        assert upload(officer, case, ANPR, "anpr.csv", "vehicle").status_code == 201
        process_latest_job(case, "VEH-001")

    def other_case_titles(client):
        response = client.get(f"/api/investigations/{case_a}/insights")
        assert response.status_code == 200
        return [i["title"] for i in response.json()["items"] if i["kind"] == "other_case"]

    assert other_case_titles(officer) == [f"TG 09 ZZ 0001 also appears in {case_b}"]
    assert other_case_titles(signed_in(analyst_user)) == [
        "TG 09 ZZ 0001 appears in 1 other investigation you cannot open"
    ]
