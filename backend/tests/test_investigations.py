"""Investigation management tests: isolation, permissions, numbering, transitions, audit."""

import re

import pytest

from tests.helpers import create_case, signed_in


def test_officer_creates_draft_case_with_next_reference_and_is_lead(make_user):
    officer = signed_in(make_user("investigation_officer"))
    first = create_case(officer, tags=["Burglary", "burglary", " night "])
    second = create_case(officer)

    assert re.fullmatch(r"CASE-\d{4}-\d{3}", first["reference"])
    assert int(second["reference"][-3:]) == int(first["reference"][-3:]) + 1
    assert first["status"] == "draft" and first["stage"] == "intake"
    assert first["my_role_in_case"] == "lead" and first["team_size"] == 1
    assert first["tags"] == ["burglary", "night"]  # cleaned + de-duplicated


def test_roles_without_write_permission_cannot_create(make_user):
    analyst = signed_in(make_user("forensic_analyst"))
    response = analyst.post("/api/investigations", json={"title": "Case", "case_type": "Fraud"})
    assert response.status_code == 403


def test_admin_cannot_see_investigations_at_all(make_user):
    admin = signed_in(make_user("system_admin"))
    assert admin.get("/api/investigations").status_code == 403


def test_data_isolation_non_members_get_404_not_403(make_user):
    owner = signed_in(make_user("investigation_officer"))
    outsider = signed_in(make_user("investigation_officer"))
    case = create_case(owner, title="Isolation check case")

    # Not in the list, and opening it directly looks exactly like "does not exist".
    listed = outsider.get("/api/investigations", params={"search": "Isolation check"}).json()
    assert case["reference"] not in [i["reference"] for i in listed["items"]]
    assert outsider.get(f"/api/investigations/{case['reference']}").status_code == 404
    assert outsider.get("/api/investigations/CASE-1999-999").status_code == 404


def test_supervisor_sees_every_case(make_user):
    owner = signed_in(make_user("investigation_officer"))
    supervisor = signed_in(make_user("supervisor"))
    case = create_case(owner)
    response = supervisor.get(f"/api/investigations/{case['reference']}")
    assert response.status_code == 200
    assert response.json()["my_role_in_case"] is None


def test_added_member_can_see_the_case(make_user):
    owner = signed_in(make_user("investigation_officer"))
    analyst_user = make_user("forensic_analyst")
    analyst = signed_in(analyst_user)
    case = create_case(owner)
    ref = case["reference"]

    assert analyst.get(f"/api/investigations/{ref}").status_code == 404
    added = owner.post(f"/api/investigations/{ref}/members", json={"email": analyst_user.email})
    assert added.status_code == 201
    assert analyst.get(f"/api/investigations/{ref}").json()["my_role_in_case"] == "member"

    duplicate = owner.post(f"/api/investigations/{ref}/members", json={"email": analyst_user.email})
    assert duplicate.status_code == 409


def test_admins_cannot_be_added_to_case_teams(make_user):
    owner = signed_in(make_user("investigation_officer"))
    admin_user = make_user("system_admin")
    case = create_case(owner)
    response = owner.post(
        f"/api/investigations/{case['reference']}/members", json={"email": admin_user.email}
    )
    assert response.status_code == 409


@pytest.mark.parametrize(
    ("path", "allowed"),
    [
        (["active", "under_review", "closed", "archived"], True),
        (["active", "closed", "active"], True),  # reopen
    ],
)
def test_allowed_status_paths(make_user, path, allowed):
    owner = signed_in(make_user("investigation_officer"))
    ref = create_case(owner)["reference"]
    for status in path:
        response = owner.patch(f"/api/investigations/{ref}", json={"status": status})
        assert (response.status_code == 200) is allowed, response.text


def test_invalid_status_transition_is_rejected_with_explanation(make_user):
    owner = signed_in(make_user("investigation_officer"))
    ref = create_case(owner)["reference"]
    response = owner.patch(f"/api/investigations/{ref}", json={"status": "closed"})
    assert response.status_code == 409
    assert "Allowed next" in response.json()["detail"]


def test_archived_cases_are_read_only(make_user):
    owner = signed_in(make_user("investigation_officer"))
    ref = create_case(owner)["reference"]
    owner.patch(f"/api/investigations/{ref}", json={"status": "archived"})
    response = owner.patch(f"/api/investigations/{ref}", json={"title": "Changed title"})
    assert response.status_code == 409


def test_members_without_write_permission_cannot_edit(make_user):
    owner = signed_in(make_user("investigation_officer"))
    analyst_user = make_user("forensic_analyst")
    ref = create_case(owner)["reference"]
    owner.post(f"/api/investigations/{ref}/members", json={"email": analyst_user.email})
    response = signed_in(analyst_user).patch(f"/api/investigations/{ref}", json={"priority": "low"})
    assert response.status_code == 403


def test_updates_are_audited_with_previous_and_new_values(make_user):
    owner = signed_in(make_user("investigation_officer"))
    ref = create_case(owner, priority="medium")["reference"]
    owner.patch(f"/api/investigations/{ref}", json={"priority": "critical", "status": "active"})

    activity = owner.get(f"/api/investigations/{ref}/activity").json()
    assert [a["action"] for a in activity] == ["investigation.updated", "investigation.created"]
    update = activity[0]
    assert update["previous_state"] == {"priority": "medium", "status": "draft"}
    assert update["new_state"] == {"priority": "critical", "status": "active"}


def test_list_filters_search_and_pagination(make_user):
    owner = signed_in(make_user("investigation_officer"))
    create_case(owner, title="Zebra crossing incident", priority="low")
    create_case(owner, title="Zebra fuel theft", priority="high")
    create_case(owner, title="Unrelated matter", priority="high")

    zebra = owner.get("/api/investigations", params={"search": "zebra"}).json()
    assert zebra["total"] == 2
    high_zebra = owner.get("/api/investigations", params={"search": "zebra", "priority": "high"})
    assert [i["title"] for i in high_zebra.json()["items"]] == ["Zebra fuel theft"]

    page = owner.get("/api/investigations", params={"limit": 1, "offset": 1}).json()
    assert len(page["items"]) == 1 and page["total"] >= 3


def test_validation_errors_are_rejected(make_user):
    owner = signed_in(make_user("investigation_officer"))
    response = owner.post("/api/investigations", json={"title": "ab", "case_type": "x"})
    assert response.status_code == 422
