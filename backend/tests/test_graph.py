"""Relationship graph: pure builder rules + the API on real processed evidence."""

from datetime import UTC, datetime

from app.graph import builder as g
from tests.helpers import process_latest_job, signed_in, upload

T = datetime(2026, 9, 28, 15, 0, tzinfo=UTC)


def facts():
    entities = [
        g.EntityIn("PH001", "phone_number", "+1 202-555-0101", "pending"),
        g.EntityIn("PH002", "phone_number", "+1 202-555-0102", "confirmed"),
        g.EntityIn("P001", "person", "Ravi", "rejected"),
    ]
    evidence = [
        g.EvidenceIn("CALL-001", "call_records", "Calls", "processed"),
        g.EvidenceIn("DOC-001", "document", "Report", "processed"),
    ]
    mentions = [
        g.MentionIn("PH002", "DOC-001", "detected", 0.7, "page 1"),
        g.MentionIn("P001", "DOC-001", "detected", 0.5, "page 1"),
    ]
    events = [
        g.EventIn(
            "E001",
            "call_made",
            "Call",
            T,
            "CALL-001",
            "extracted",
            0.95,
            "pending",
            (("PH001", "caller"), ("PH002", "callee")),
        )
    ]
    correlations = [
        g.CorrelationIn(
            "COR-001", "CALL-001", "DOC-001", 0.41, "low", ("entity",), "pending", False
        ),
        g.CorrelationIn(
            "COR-002", "CALL-001", "DOC-001", 0.9, "high", ("time",), "rejected", False
        ),
    ]
    return entities, evidence, mentions, events, correlations


def test_edges_explain_themselves_and_rejected_facts_are_hidden():
    graph = g.build(*facts())
    ids = {n.id for n in graph.nodes}
    assert "entity:P001" not in ids  # rejected entity
    by_type = {e.type: e for e in graph.edges}
    assert set(by_type) == {"appears_in", "communicated_with", "related_evidence"}
    call = by_type["communicated_with"]
    assert call.supporting_events == ["E001"] and call.supporting_evidence == ["CALL-001"]
    assert "communicated 1 time" in call.why
    # PH002 appears in CALL-001 (as callee) and DOC-001 (mentioned)
    appears = [e for e in graph.edges if e.type == "appears_in" and e.source == "entity:PH002"]
    assert {e.target for e in appears} == {"evidence:CALL-001", "evidence:DOC-001"}
    # the rejected correlation is not drawn
    assert [e.details["correlation"] for e in graph.edges if e.type == "related_evidence"] == [
        "COR-001"
    ]


def test_options_events_rejected_levels_and_types():
    with_events = g.build(*facts(), options=g.Options(include_events=True))
    types = {e.type for e in with_events.edges}
    assert {"involved_in", "recorded_in"} <= types

    everything = g.build(*facts(), options=g.Options(include_rejected=True))
    assert "entity:P001" in {n.id for n in everything.nodes}

    high_only = g.build(*facts(), options=g.Options(min_level="medium"))
    assert not [e for e in high_only.edges if e.type == "related_evidence"]

    phones = g.build(*facts(), options=g.Options(entity_types=frozenset({"person"})))
    assert not [n for n in phones.nodes if n.type == "phone_number"]


def test_focus_keeps_only_the_neighbourhood():
    graph = g.build(*facts(), options=g.Options(include_evidence=False, focus="entity:PH001"))
    assert {n.id for n in graph.nodes} == {"entity:PH001", "entity:PH002"}


def test_large_graphs_are_truncated_to_the_best_connected_nodes():
    graph = g.build(*facts(), options=g.Options(max_nodes=2))
    assert graph.truncated and len(graph.nodes) == 2 and graph.total_nodes == 4
    assert all(e.source in {n.id for n in graph.nodes} for e in graph.edges)


CALLS_CSV = (
    b"caller,callee,started_at,duration_s\n"
    b"+1-202-555-0101,+1-202-555-0102,2026-09-28T20:33:00+05:30,95\n"
)


def test_graph_api_on_processed_evidence(team, make_user):
    client, case = team["officer"], team["case"]
    upload(client, case, CALLS_CSV, "calls.csv", "call_records")
    process_latest_job(case, "CALL-001")

    graph = client.get(f"/api/investigations/{case}/graph").json()
    kinds = {e["type"] for e in graph["edges"]}
    assert {"appears_in", "communicated_with"} <= kinds
    call = next(e for e in graph["edges"] if e["type"] == "communicated_with")
    assert "15:03" in call["why"]  # 20:33 +05:30 shown in the test case's zone (UTC)

    focused = client.get(
        f"/api/investigations/{case}/graph", params={"focus": "evidence:CALL-001", "depth": 1}
    ).json()
    assert {n["kind"] for n in focused["nodes"]} == {"evidence", "entity"}

    bad = client.get(f"/api/investigations/{case}/graph", params={"focus": "CALL-001"})
    assert bad.status_code == 422
    outsider = signed_in(make_user("investigation_officer"))
    assert outsider.get(f"/api/investigations/{case}/graph").status_code == 404
