"""The relationship graph (plan §20): nodes + edges, every edge with the reason it exists.

Pure like the correlation engine: plain facts in, a graph out. No graph database. The graph
is a VIEW over tables we already have:

    entity_mentions ─────────► ENTITY ──appears in──► EVIDENCE
    event_participants ──────► ENTITY ──communicated with / connected to──► ENTITY
                               ENTITY ──involved in──► EVENT ──recorded in──► EVIDENCE
    correlations ────────────► EVIDENCE ──related evidence──► EVIDENCE
"""

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

COMMUNICATION = {"call_made", "message_sent", "communication"}
LEVEL_RANK = {"low": 0, "medium": 1, "high": 2}

# ---------- Input ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EntityIn:
    reference: str
    entity_type: str
    label: str
    review_status: str


@dataclass(frozen=True)
class EvidenceIn:
    reference: str
    evidence_type: str
    label: str
    status: str


@dataclass(frozen=True)
class MentionIn:
    entity: str  # entity reference
    evidence: str  # evidence reference
    assertion_kind: str
    confidence: float
    source_location: str


@dataclass(frozen=True)
class EventIn:
    reference: str
    event_type: str
    description: str
    occurred_at: datetime | None
    evidence: str
    assertion_kind: str
    confidence: float
    review_status: str
    participants: tuple[tuple[str, str], ...]  # (entity reference, role)


@dataclass(frozen=True)
class CorrelationIn:
    reference: str
    evidence_a: str
    evidence_b: str
    score: float
    level: str
    factor_kinds: tuple[str, ...]
    review_status: str
    stale: bool


@dataclass(frozen=True)
class Options:
    include_events: bool = False
    include_evidence: bool = True
    include_rejected: bool = False
    include_stale: bool = False
    entity_types: frozenset[str] | None = None  # None = all
    min_level: str = "low"
    focus: str | None = None  # node id, e.g. "entity:V001"
    depth: int = 1
    max_nodes: int = 300


# ---------- Output --------------------------------------------------------------------------


@dataclass
class Node:
    id: str
    kind: str  # entity | evidence | event
    type: str  # person / vehicle … | video / gps … | call_made …
    reference: str
    label: str
    review_status: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    degree: int = 0


@dataclass
class Edge:
    id: str
    source: str
    target: str
    type: str  # appears_in | communicated_with | connected_to | related_evidence | …
    why: str
    confidence: float
    review_status: str
    assertion_kinds: list[str]
    supporting_evidence: list[str]
    supporting_events: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class Graph:
    nodes: list[Node]
    edges: list[Edge]
    total_nodes: int
    total_edges: int
    truncated: bool


def entity_id(ref: str) -> str:
    return f"entity:{ref}"


def evidence_id(ref: str) -> str:
    return f"evidence:{ref}"


def event_id(ref: str) -> str:
    return f"event:{ref}"


# ---------- Building ------------------------------------------------------------------------


def build(
    entities: list[EntityIn],
    evidence: list[EvidenceIn],
    mentions: list[MentionIn],
    events: list[EventIn],
    correlations: list[CorrelationIn],
    options: Options | None = None,
    describe_time: Callable[[datetime], str] = lambda t: t.isoformat(),
) -> Graph:
    options = options or Options()
    kept_entities = {
        e.reference: e
        for e in entities
        if (options.include_rejected or e.review_status != "rejected")
        and (options.entity_types is None or e.entity_type in options.entity_types)
    }
    kept_events = [e for e in events if options.include_rejected or e.review_status != "rejected"]
    nodes: dict[str, Node] = {}
    for e in kept_entities.values():
        nodes[entity_id(e.reference)] = Node(
            entity_id(e.reference), "entity", e.entity_type, e.reference, e.label, e.review_status
        )
    if options.include_evidence:
        for ev in evidence:
            nodes[evidence_id(ev.reference)] = Node(
                evidence_id(ev.reference),
                "evidence",
                ev.evidence_type,
                ev.reference,
                ev.label,
                details={"status": ev.status},
            )
    if options.include_events:
        for ev in kept_events:
            nodes[event_id(ev.reference)] = Node(
                event_id(ev.reference),
                "event",
                ev.event_type,
                ev.reference,
                ev.description or ev.event_type.replace("_", " "),
                ev.review_status,
                details={"occurred_at": ev.occurred_at.isoformat() if ev.occurred_at else None},
            )

    edges: list[Edge] = []
    if options.include_evidence:
        edges += _appears_in(kept_entities, mentions, kept_events)
        edges += _related_evidence(correlations, options)
    edges += _entity_links(kept_entities, kept_events, describe_time)
    if options.include_events:
        edges += _event_edges(kept_entities, kept_events, options.include_evidence)
    edges = [e for e in edges if e.source in nodes and e.target in nodes]

    if options.focus:
        nodes, edges = _neighbourhood(nodes, edges, options.focus, options.depth)

    total_nodes, total_edges = len(nodes), len(edges)
    for edge in edges:
        nodes[edge.source].degree += 1
        nodes[edge.target].degree += 1
    truncated = len(nodes) > options.max_nodes
    if truncated:
        # Too much to draw usefully: keep the best-connected nodes (and the focus).
        keep = sorted(nodes.values(), key=lambda n: (n.id != options.focus, -n.degree, n.id))
        allowed = {n.id for n in keep[: options.max_nodes]}
        nodes = {k: v for k, v in nodes.items() if k in allowed}
        edges = [e for e in edges if e.source in allowed and e.target in allowed]

    ordered = sorted(nodes.values(), key=lambda n: (n.kind, n.reference))
    return Graph(ordered, edges, total_nodes, total_edges, truncated)


def _appears_in(
    entities: dict[str, EntityIn], mentions: list[MentionIn], events: list[EventIn]
) -> list[Edge]:
    """ENTITY appears in EVIDENCE: written in it, or taking part in an event recorded from it."""
    found: dict[tuple[str, str], list[tuple[str, float, str]]] = {}
    for m in mentions:
        if m.entity in entities:
            found.setdefault((m.entity, m.evidence), []).append(
                (m.assertion_kind, m.confidence, m.source_location or "mentioned")
            )
    for ev in events:
        for ref, role in ev.participants:
            if ref in entities:
                found.setdefault((ref, ev.evidence), []).append(
                    (ev.assertion_kind, ev.confidence, f"{role} in {ev.reference}")
                )
    edges = []
    for (ent, evd), sightings in sorted(found.items()):
        entity = entities[ent]
        best = max(c for _, c, _ in sightings)
        places = sorted({place for _, _, place in sightings})
        shown = ", ".join(places[:3]) + (f" and {len(places) - 3} more" if len(places) > 3 else "")
        edges.append(
            Edge(
                id=f"appears_in:{ent}:{evd}",
                source=entity_id(ent),
                target=evidence_id(evd),
                type="appears_in",
                why=(
                    f"{ent} ({entity.label}) was found in {evd} {len(sightings)} "
                    f"time{'s' if len(sightings) != 1 else ''}: {shown}. "
                    f"Best confidence {best:.2f}."
                ),
                confidence=round(best, 3),
                review_status=entity.review_status,
                assertion_kinds=sorted({k for k, _, _ in sightings}),
                supporting_evidence=[evd],
                details={"sightings": len(sightings), "where": places[:10]},
            )
        )
    return edges


def _entity_links(
    entities: dict[str, EntityIn], events: list[EventIn], describe_time: Callable[[datetime], str]
) -> list[Edge]:
    """ENTITY ↔ ENTITY when they took part in the same event (a call, a payment …)."""
    together: dict[tuple[str, str], list[EventIn]] = {}
    for ev in events:
        refs = sorted({ref for ref, _ in ev.participants if ref in entities})
        for i, a in enumerate(refs):
            for b in refs[i + 1 :]:
                together.setdefault((a, b), []).append(ev)
    edges = []
    for (a, b), shared in sorted(together.items()):
        communication = any(ev.event_type in COMMUNICATION for ev in shared)
        kind = "communicated_with" if communication else "connected_to"
        verb = "communicated" if communication else "took part in the same event"
        times = sorted(ev.occurred_at for ev in shared if ev.occurred_at)
        span = f", first at {describe_time(times[0])}" if times else ""
        refs = [ev.reference for ev in shared]
        listed = ", ".join(refs[:5]) + (f" and {len(refs) - 5} more" if len(refs) > 5 else "")
        edges.append(
            Edge(
                id=f"{kind}:{a}:{b}",
                source=entity_id(a),
                target=entity_id(b),
                type=kind,
                why=(
                    f"{a} ({entities[a].label}) and {b} ({entities[b].label}) {verb} "
                    f"{len(shared)} time{'s' if len(shared) != 1 else ''} ({listed}{span})."
                ),
                confidence=round(min(ev.confidence for ev in shared), 3),
                review_status=_combined_review(shared),
                assertion_kinds=sorted({ev.assertion_kind for ev in shared}),
                supporting_evidence=sorted({ev.evidence for ev in shared}),
                supporting_events=refs,
                details={"events": len(shared)},
            )
        )
    return edges


def _event_edges(
    entities: dict[str, EntityIn], events: list[EventIn], with_evidence: bool
) -> list[Edge]:
    edges = []
    for ev in events:
        for ref, role in ev.participants:
            if ref not in entities:
                continue
            edges.append(
                Edge(
                    id=f"involved_in:{ref}:{ev.reference}:{role}",
                    source=entity_id(ref),
                    target=event_id(ev.reference),
                    type="involved_in",
                    why=f"{ref} ({entities[ref].label}) took part in {ev.reference} as {role}.",
                    confidence=round(ev.confidence, 3),
                    review_status=ev.review_status,
                    assertion_kinds=[ev.assertion_kind],
                    supporting_evidence=[ev.evidence],
                    supporting_events=[ev.reference],
                    details={"role": role},
                )
            )
        if with_evidence:
            edges.append(
                Edge(
                    id=f"recorded_in:{ev.reference}",
                    source=event_id(ev.reference),
                    target=evidence_id(ev.evidence),
                    type="recorded_in",
                    why=f"{ev.reference} was recorded from {ev.evidence}.",
                    confidence=round(ev.confidence, 3),
                    review_status=ev.review_status,
                    assertion_kinds=[ev.assertion_kind],
                    supporting_evidence=[ev.evidence],
                    supporting_events=[ev.reference],
                )
            )
    return edges


def _related_evidence(correlations: list[CorrelationIn], options: Options) -> list[Edge]:
    floor = LEVEL_RANK[options.min_level]
    edges = []
    for c in correlations:
        if c.stale and not options.include_stale:
            continue
        if c.review_status == "rejected" and not options.include_rejected:
            continue
        if LEVEL_RANK[c.level] < floor:
            continue
        reasons = {"entity": "a shared entity", "time": "time", "location": "place"}
        listed = " + ".join(reasons[k] for k in c.factor_kinds)
        edges.append(
            Edge(
                id=f"related_evidence:{c.reference}",
                source=evidence_id(c.evidence_a),
                target=evidence_id(c.evidence_b),
                type="related_evidence",
                why=(
                    f"{c.reference}: {c.level} potential relationship (score {c.score:.2f}) "
                    f"from {listed}."
                ),
                confidence=round(c.score, 3),
                review_status=c.review_status,
                assertion_kinds=["correlated"],
                supporting_evidence=[c.evidence_a, c.evidence_b],
                details={
                    "correlation": c.reference,
                    "level": c.level,
                    "factors": list(c.factor_kinds),
                    "stale": c.stale,
                },
            )
        )
    return edges


def _combined_review(events: list[EventIn]) -> str:
    """A link is confirmed once any supporting event is confirmed; otherwise it awaits review."""
    statuses = {ev.review_status for ev in events}
    if "confirmed" in statuses:
        return "confirmed"
    if statuses == {"rejected"}:
        return "rejected"
    return "pending"


def _neighbourhood(
    nodes: dict[str, Node], edges: list[Edge], focus: str, depth: int
) -> tuple[dict[str, Node], list[Edge]]:
    """Breadth-first search: the focus node and everything within `depth` steps of it."""
    if focus not in nodes:
        return {}, []
    neighbours: dict[str, set[str]] = {}
    for e in edges:
        neighbours.setdefault(e.source, set()).add(e.target)
        neighbours.setdefault(e.target, set()).add(e.source)
    seen = {focus}
    queue = deque([(focus, 0)])
    while queue:
        current, distance = queue.popleft()
        if distance == depth:
            continue
        for nxt in neighbours.get(current, ()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, distance + 1))
    return (
        {k: v for k, v in nodes.items() if k in seen},
        [e for e in edges if e.source in seen and e.target in seen],
    )


def shortest_path(edges: list[Edge], start: str, goal: str, max_steps: int = 6) -> list[Edge]:
    """The fewest links from `start` to `goal` (BFS), or [] when they are not connected."""
    if start == goal:
        return []
    links: dict[str, list[tuple[str, Edge]]] = {}
    for e in edges:
        links.setdefault(e.source, []).append((e.target, e))
        links.setdefault(e.target, []).append((e.source, e))
    came_from: dict[str, tuple[str, Edge]] = {}
    seen = {start}
    queue = deque([(start, 0)])
    while queue:
        current, steps = queue.popleft()
        if steps == max_steps:
            continue
        for nxt, edge in links.get(current, ()):
            if nxt in seen:
                continue
            seen.add(nxt)
            came_from[nxt] = (current, edge)
            if nxt == goal:
                path: list[Edge] = []
                node = goal
                while node != start:
                    node, step = came_from[node]
                    path.append(step)
                return path[::-1]
            queue.append((nxt, steps + 1))
    return []
