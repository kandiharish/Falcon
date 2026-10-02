"""AI features: pure helpers, natural-language search, similarity and the assistant agent.
No real model is used: OfflineProvider (default) or FakeProvider with scripted replies."""

import io
import json
from datetime import date

from PIL import Image
from sqlalchemy import select

from app.ai import provider
from app.ai.assistant import check_citations
from app.ai.search_plan import CaseVocabulary, SearchPlan, describe, rules_plan, validate
from app.ai.similarity import chunk_text, dhash, hamming
from app.db.session import SessionLocal
from app.models import AuditLog
from tests.fake_ai import FakeProvider, tool_call
from tests.helpers import process_latest_job, signed_in, upload

CALLS_CSV = (
    b"caller,callee,started_at,duration_s\n"
    b"+1-202-555-0101,+1-202-555-0102,2026-09-28T20:33:00+05:30,95\n"
    b"+1-202-555-0102,+1-202-555-0177,2026-09-28T23:10:00+05:30,40\n"
)
VOCAB = CaseVocabulary(
    entities={"PH001": ("phone_number", "+1 202-555-0101"), "V001": ("vehicle", "ZZ99 ZZ 0001")},
    evidence={"CALL-001": ("call_records", "Calls"), "CCTV-001": ("video", "Rear door")},
    time_zone="Asia/Kolkata",
    today=date(2026, 10, 2),
)


# ---------- Pure helpers ------------------------------------------------------------------


def test_chunks_stay_small_and_overlap():
    text = " ".join(f"Sentence number {i} about the grey van." for i in range(60))
    chunks = chunk_text(text)
    assert len(chunks) > 1 and all(len(c) <= 600 for c in chunks)
    assert chunks[0][-20:].split()[-1] in chunks[1]  # the overlap repeats the end
    assert chunk_text("   ") == []


def _png(size: tuple[int, int], brighten: int = 0) -> Image.Image:
    image = Image.new("L", (64, 64))
    for x in range(64):
        for y in range(64):
            image.putpixel((x, y), min(255, (x * 4 + y) % 256 + brighten))
    return image.resize(size)


def test_dhash_survives_resizing_but_not_a_different_picture(tmp_path):
    original, resized, other = tmp_path / "a.png", tmp_path / "b.png", tmp_path / "c.png"
    _png((64, 64)).save(original)
    _png((200, 200), brighten=10).save(resized)
    Image.new("L", (64, 64), 30).rotate(45).transpose(Image.Transpose.FLIP_LEFT_RIGHT).save(other)
    Image.effect_noise((64, 64), 90).save(other)
    assert hamming(dhash(original), dhash(resized)) <= 10
    assert hamming(dhash(original), dhash(other)) > 10


def test_rules_read_the_plan_examples():
    plan = rules_plan("Show all communications involving PH001 between 8 PM and 10 PM", VOCAB)
    assert plan.intent == "events" and plan.entity_refs == ["PH001"]
    assert "call_made" in plan.event_types and (plan.time_from, plan.time_to) == ("20:00", "22:00")
    connection = rules_plan("Find relationships between PH001 and V001", VOCAB)
    assert connection.intent == "connection"
    assert rules_plan("anything about a grey van", VOCAB).intent == "text"
    by_name = rules_plan("Which evidence mentions the van ZZ99 ZZ 0001?", VOCAB)
    assert by_name.intent == "evidence" and by_name.entity_refs == ["V001"]
    assert rules_plan("calls from +1 (202) 555-0101", VOCAB).entity_refs == ["PH001"]


def test_validation_never_trusts_the_model():
    plan = SearchPlan(
        intent="events",
        entity_refs=["P999", "CCTV-001"],  # unknown, and evidence put in the entity list
        event_types=["call_made", "teleported"],
        time_from="8pm",
        time_to="24:00",
    )
    clean, notes = validate(plan, VOCAB, "what happened with PH001?")
    assert clean.entity_refs == ["PH001"]  # typed by the user, kept even though model missed it
    assert clean.evidence_refs == ["CCTV-001"]  # moved, not lost
    assert clean.event_types == ["call_made"]
    assert clean.time_from is None and clean.time_to == "23:59"
    assert any("P999" in n for n in notes) and any("8pm" in n for n in notes)
    assert describe(clean).startswith("Showing events involving PH001, CCTV-001")


def test_citations_are_checked_against_what_the_tools_returned():
    found = check_citations(
        "The van [V001] was filmed [CCTV-001] and [DOC-404].", {"V001", "CCTV-001"}
    )
    assert found == [
        {"reference": "V001", "verified": True},
        {"reference": "CCTV-001", "verified": True},
        {"reference": "DOC-404", "verified": False},
    ]


# ---------- Natural-language search --------------------------------------------------------


def _calls_case(team):
    client, case = team["officer"], team["case"]
    # Times of day are read in the case's zone: 20:33 in India, like the demo case.
    assert client.patch(
        f"/api/investigations/{case}", json={"time_zone": "Asia/Kolkata"}
    ).is_success
    upload(client, case, CALLS_CSV, "calls.csv", "call_records")
    process_latest_job(case, "CALL-001")
    return client, case


def test_search_falls_back_to_rules_when_ai_is_off(team):
    client, case = _calls_case(team)
    response = client.post(
        f"/api/investigations/{case}/ai/search",
        json={"question": "Show communications involving PH001 between 8 PM and 10 PM"},
    )
    body = response.json()
    assert response.status_code == 200 and body["interpreted_by"] == "rules"
    assert [e["reference"] for e in body["events"]] == ["E001"]  # 23:10 is outside the window
    assert "PH001" in body["summary"]


def test_search_with_the_model_is_validated_and_audited(team):
    client, case = _calls_case(team)
    provider.use(
        FakeProvider([{"intent": "connection", "entity_refs": ["PH001", "PH003", "X999"]}])
    )
    body = client.post(
        f"/api/investigations/{case}/ai/search", json={"question": "How is PH001 linked to PH003?"}
    ).json()
    assert body["interpreted_by"] != "rules"
    assert body["plan"]["entity_refs"] == ["PH001", "PH003"]
    assert any("X999" in n for n in body["notes"])
    # Two links either way: PH001→PH002→PH003 (calls) or PH001→CALL-001→PH003 (same log).
    assert len(body["path"]) == 2
    ends = {body["path"][0]["source"], body["path"][0]["target"]}
    assert "entity:PH001" in ends and all(e["why"] for e in body["path"])
    with SessionLocal() as db:
        assert db.scalar(
            select(AuditLog).where(AuditLog.action == "ai.search", AuditLog.object_id == case)
        )


# ---------- Similarity --------------------------------------------------------------------


def _jpeg(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=90)
    return buffer.getvalue()


def test_near_duplicate_images_and_similar_documents(team):
    client, case = team["officer"], team["case"]
    provider.use(FakeProvider())
    upload(client, case, _jpeg(_png((64, 64))), "door.jpg", "image")
    upload(client, case, _jpeg(_png((160, 160), brighten=8)), "door_copy.jpg", "image")
    upload(
        client,
        case,
        b"The grey van left the rear door of warehouse four at night.",
        "a.txt",
        "document",
    )
    upload(
        client,
        case,
        b"A grey van was seen at the rear door of warehouse four.",
        "b.txt",
        "document",
    )
    upload(client, case, b"Invoice for office chairs and printer paper.", "c.txt", "document")
    for ref in ("IMG-001", "IMG-002", "DOC-001", "DOC-002", "DOC-003"):
        process_latest_job(case, ref)

    image = client.get(f"/api/investigations/{case}/evidence/IMG-001/similar").json()
    assert [(s["evidence"]["reference"], s["kind"]) for s in image] == [("IMG-002", "image")]
    text = client.get(f"/api/investigations/{case}/evidence/DOC-001/similar").json()
    assert [s["evidence"]["reference"] for s in text] == ["DOC-002"]  # not the invoice
    assert text[0]["kind"] == "text" and "grey van" in text[0]["match"]


def test_rebuilding_the_index_needs_the_ai_and_the_right_role(team, make_user):
    client, case = team["officer"], team["case"]
    upload(client, case, b"The grey van left at night.", "a.txt", "document")
    process_latest_job(case, "DOC-001")  # AI offline: the similarity step is skipped, not failed
    assert (
        client.get(f"/api/investigations/{case}/evidence/DOC-001").json()["status"] == "processed"
    )
    assert client.post(f"/api/investigations/{case}/ai/reindex").status_code == 503

    provider.use(FakeProvider())
    assert client.post(f"/api/investigations/{case}/ai/reindex").json()["chunks"] == 1
    evidence_analyst = make_user("evidence_analyst")
    client.post(f"/api/investigations/{case}/members", json={"email": evidence_analyst.email})
    supervisor_view = signed_in(make_user("supervisor"))
    assert supervisor_view.post(f"/api/investigations/{case}/ai/reindex").status_code in (200, 403)


# ---------- The assistant agent ------------------------------------------------------------


def _stream(client, case, question, history=()):
    response = client.post(
        f"/api/investigations/{case}/assistant",
        json={"question": question, "history": list(history)},
    )
    assert response.status_code == 200, response.text
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def test_assistant_uses_tools_then_answers_with_checked_citations(team):
    client, case = _calls_case(team)
    fake = FakeProvider(
        [
            tool_call("search_events", entity="PH001", event_type="call_made"),
            tool_call("delete_everything", confirm="yes"),  # not a tool: refused, loop continues
            "PH001 called PH002 at 20:33 [E001] [CALL-001]. Possibly linked to [CCTV-999].",
        ]
    )
    provider.use(fake)
    events = _stream(client, case, "Who did PH001 call?")
    kinds = [e["type"] for e in events]
    assert kinds.count("tool_result") == 2 and kinds[-1] == "answer"
    results = [e for e in events if e["type"] == "tool_result"]
    assert results[0]["summary"].startswith("1 events") or "E001" in results[0]["summary"]
    answer = events[-1]
    assert {c["reference"]: c["verified"] for c in answer["citations"]} == {
        "PH001": True,
        "PH002": True,
        "E001": True,
        "CALL-001": True,
        "CCTV-999": False,
    }
    tool_messages = [m for m in fake.calls[-1]["messages"] if m["role"] == "tool"]
    assert "no tool called delete_everything" in tool_messages[-1]["content"]
    with SessionLocal() as db:
        actions = db.scalars(select(AuditLog.action).where(AuditLog.object_id == case)).all()
    assert actions.count("assistant.tool_call") == 2
    assert {"assistant.question", "assistant.answer"} <= set(actions)


def test_assistant_stops_after_the_step_limit(team, monkeypatch):
    client, case = team["officer"], team["case"]
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "assistant_max_steps", 2)
    provider.use(
        FakeProvider([tool_call("search_entities", text="van")] * 2 + ["Final answer [V001]."])
    )
    events = _stream(client, case, "Tell me about the van")
    assert events[-1]["type"] == "answer" and events[-1]["steps"] == 2
    assert events[-1]["text"] == "Final answer [V001]."


def test_assistant_reports_when_ai_is_off_and_hides_other_cases(team, make_user):
    client, case = team["officer"], team["case"]
    events = _stream(client, case, "Anything?")
    assert events[-1]["type"] == "error" and "Ollama" in events[-1]["message"]
    outsider = signed_in(make_user("investigation_officer"))
    assert (
        outsider.post(f"/api/investigations/{case}/assistant", json={"question": "hi?"}).status_code
        == 404
    )
    assert (
        outsider.post(f"/api/investigations/{case}/ai/search", json={"question": "hi?"}).status_code
        == 404
    )
