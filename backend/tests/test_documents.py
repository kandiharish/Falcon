"""Section 63 certificates, requisition letters and the court bundle."""

import hashlib
import io
import zipfile

from app.db.session import SessionLocal
from app.models import AuditLog
from tests.helpers import CALLS_CSV, process_latest_job, signed_in, upload


def fields_of(doc) -> dict[str, str]:
    return {k: v for section in doc["sections"] for k, v in section["fields"]}


def test_certificate_is_prefilled_from_the_record_and_audited(team):
    officer, case = team["officer"], team["case"]
    upload(officer, case, CALLS_CSV, "calls.csv", "call_records")
    sha = hashlib.sha256(CALLS_CSV).hexdigest()

    response = officer.get(f"/api/investigations/{case}/evidence/CALL-001/certificate")
    assert response.status_code == 200
    doc = response.json()
    assert doc["title"].startswith("CERTIFICATE UNDER SECTION 63(4)(c)")
    assert fields_of(doc)["HASH value"] == sha
    assert fields_of(doc)["Device / record source"] == "Server (telecom operator)"
    assert "DRAFT" in doc["notice"] and doc["to_check"]
    text = " ".join(p for s in doc["sections"] for p in s["paragraphs"])
    assert f"HASH value of the electronic/digital record is {sha}" in text
    with SessionLocal() as db:
        assert db.query(AuditLog).filter_by(action="document.drafted").count() >= 1


def test_letter_covers_the_period_the_number_was_active(team):
    officer, case = team["officer"], team["case"]
    upload(officer, case, CALLS_CSV, "calls.csv", "call_records")
    process_latest_job(case, "CALL-001")
    phone = officer.get(f"/api/investigations/{case}/entities?entity_type=phone_number").json()
    first = phone["items"][0]["reference"]

    doc = officer.get(f"/api/investigations/{case}/letters/telecom_subscriber?entity={first}")
    assert doc.status_code == 200
    items = [i for s in doc.json()["sections"] for i in s["items"]]
    assert "25/09/2026 to 29/09/2026" in items[1]  # 3 days before the calls, 1 day after
    assert "Section 94 of the Bharatiya Nagarik Suraksha Sanhita" in doc.json()["subtitle"]
    unknown = officer.get(f"/api/investigations/{case}/letters/fax_machine?entity={first}")
    assert unknown.status_code == 422


def test_bundle_contains_verifiable_originals_and_is_for_officers_only(team):
    officer, analyst, case = team["officer"], team["analyst"], team["case"]
    upload(officer, case, CALLS_CSV, "calls.csv", "call_records")
    process_latest_job(case, "CALL-001")

    assert analyst.get(f"/api/investigations/{case}/bundle").status_code == 403
    response = officer.get(f"/api/investigations/{case}/bundle")
    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith(f'attachment; filename="{case}_')
    bundle = zipfile.ZipFile(io.BytesIO(response.content))
    names = set(bundle.namelist())
    assert {"README.txt", "SHA256SUMS.txt", "manifest.csv", "timeline.csv"} <= names
    original = bundle.read("originals/CALL-001_calls.csv")
    assert original == CALLS_CSV
    assert (
        f"{hashlib.sha256(original).hexdigest()}  originals/CALL-001_calls.csv"
        in bundle.read("SHA256SUMS.txt").decode()
    )
    assert "ALL originals matched" in bundle.read("README.txt").decode()


def test_outsiders_get_no_documents(team, make_user):
    officer, case = team["officer"], team["case"]
    upload(officer, case, CALLS_CSV, "calls.csv", "call_records")
    outsider = signed_in(make_user("investigation_officer"))
    assert (
        outsider.get(f"/api/investigations/{case}/evidence/CALL-001/certificate").status_code == 404
    )
    assert outsider.get(f"/api/investigations/{case}/bundle").status_code == 404
