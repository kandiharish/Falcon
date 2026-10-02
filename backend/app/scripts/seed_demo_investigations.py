"""Create the fictional demonstration investigations and their teams. Development only.

    uv run python -m app.scripts.seed_demo_investigations

Needs the demo users first (seed_demo_users). Safe to run twice: existing cases are skipped.
All names, places and cases are fictional (plan §32).
"""

import sys
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Investigation, InvestigationMember, ReferenceCounter, User
from app.services import audit_service

CASES = [
    {
        "reference": "CASE-2026-001",
        "title": "Riverside Warehouse Break-in",
        "case_type": "Burglary",
        "status": "active",
        "priority": "high",
        "stage": "correlation",
        "location": "Riverside Industrial Zone",
        "tags": ["burglary", "night", "cctv"],
        "description": (
            "Forced entry at a logistics warehouse between 20:00 and 22:00. CCTV, GPS, call "
            "records and a card transaction are under analysis to establish the sequence of events."
        ),
        "lead": "r.varma@falcon.example",
        "members": ["a.kumar@falcon.example", "m.das@falcon.example"],
        "created_at": "2026-09-12T08:30:00+00:00",
        "updated_at": "2026-09-29T17:42:00+00:00",
    },
    {
        "reference": "CASE-2026-002",
        "title": "Harbor Street Card Fraud",
        "case_type": "Financial fraud",
        "status": "under_review",
        "priority": "medium",
        "stage": "review",
        "location": "Harbor Street Market",
        "tags": ["fraud", "cards"],
        "description": "Series of cloned-card purchases at market stalls over three weekends.",
        "lead": "k.iyer@falcon.example",
        "members": ["a.kumar@falcon.example"],
        "created_at": "2026-08-30T10:00:00+00:00",
        "updated_at": "2026-09-28T09:15:00+00:00",
    },
    {
        "reference": "CASE-2026-003",
        "title": "Northgate Vehicle Theft Series",
        "case_type": "Vehicle theft",
        "status": "active",
        "priority": "critical",
        "stage": "extraction",
        "location": "Northgate District",
        "tags": ["vehicles", "series"],
        "description": (
            "Five vehicles taken from residential streets; plate-reader data under review."
        ),
        "lead": "r.varma@falcon.example",
        "members": ["a.kumar@falcon.example"],
        "created_at": "2026-09-20T07:10:00+00:00",
        "updated_at": "2026-09-30T06:05:00+00:00",
    },
    {
        "reference": "CASE-2026-004",
        "title": "Office Network Data Exfiltration",
        "case_type": "Cyber incident",
        "status": "draft",
        "priority": "medium",
        "stage": "intake",
        "location": "Eastline Business Park",
        "tags": ["cyber", "insider"],
        "description": "Unusual outbound transfers from a design firm's file server.",
        "lead": "a.menon@falcon.example",
        "members": [],
        "created_at": "2026-09-30T11:20:00+00:00",
        "updated_at": "2026-09-30T11:20:00+00:00",
    },
    {
        "reference": "CASE-2025-017",
        "title": "Central Metro Station Assault",
        "case_type": "Assault",
        "status": "closed",
        "priority": "high",
        "stage": "closed",
        "location": "Central Metro Station",
        "tags": ["assault", "transit"],
        "description": "Platform altercation; closed after report submission.",
        "lead": "k.iyer@falcon.example",
        "members": ["m.das@falcon.example"],
        "created_at": "2025-11-02T19:00:00+00:00",
        "updated_at": "2026-08-14T15:30:00+00:00",
    },
]


def main() -> int:
    if get_settings().environment != "development":
        print("Refusing to seed demo data outside development.")
        return 1

    with SessionLocal() as db:
        users = {u.email: u for u in db.scalars(select(User))}
        if "r.varma@falcon.example" not in users:
            print("Run seed_demo_users first.")
            return 1

        for case in CASES:
            if db.scalar(select(Investigation).where(Investigation.reference == case["reference"])):
                print(f"exists   {case['reference']}")
                continue
            lead = users[case["lead"]]
            investigation = Investigation(
                reference=case["reference"],
                title=case["title"],
                case_type=case["case_type"],
                status=case["status"],
                priority=case["priority"],
                stage=case["stage"],
                location=case["location"],
                tags=case["tags"],
                description=case["description"],
                lead_investigator_id=lead.id,
                created_by_id=lead.id,
                created_at=datetime.fromisoformat(case["created_at"]),
                updated_at=datetime.fromisoformat(case["updated_at"]),
            )
            investigation.members.append(InvestigationMember(user_id=lead.id, role_in_case="lead"))
            for email in case["members"]:
                investigation.members.append(InvestigationMember(user_id=users[email].id))
            db.add(investigation)
            audit_service.record(
                db,
                "investigation.created",
                actor_email="seed-script",
                object_type="investigation",
                object_id=case["reference"],
                new_state={"title": case["title"], "status": case["status"]},
                note="demo data",
            )
            print(f"created  {case['reference']}  {case['title']}")

        # Keep the case-number counters ahead of the seeded numbers.
        for year, last in ((2026, 4), (2025, 17)):
            db.execute(
                insert(ReferenceCounter)
                .values(year=year, last_value=last)
                .on_conflict_do_nothing(index_elements=[ReferenceCounter.year])
            )
        db.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
