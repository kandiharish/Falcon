# Phase 9: Relationship Graph

## 1. What we built

```
 Graph page ─┬─ canvas: entities (coloured circles), evidence (squares), events (diamonds)
             ├─ toolbar: find · entity types · correlation strength · evidence / events / rejected
             ├─ click an item → details, Profile, Timeline, "Focus on this item" (1–3 steps)
             ├─ click a link  → WHY THIS RELATIONSHIP EXISTS: reason, confidence, review,
             │                   how we know, supporting evidence and events
             └─ List view: the same links as a table (screen readers, phones, printing)
```

## 2. Where the links come from (no graph database)

```
 table                 →  link in the graph
 entity_mentions       →  ENTITY ──appears in──► EVIDENCE
 event_participants    →  ENTITY ──communicated with / connected to──► ENTITY   (same call / payment)
                          ENTITY ──involved in──► EVENT ──recorded in──► EVIDENCE
 correlations (P8)     →  EVIDENCE ──related evidence──► EVIDENCE
```

The graph is **computed when asked for**, from tables we already have. It is not stored a second
time.
- **Why not Neo4j?** It would mean a second database to install, back up and keep in sync, and
  a copy of the links that can go stale. Our cases have hundreds of links. Neo4j pays off at
  millions.
- **Why not a `relationships` table?** It would be another copy that must be updated on every
  extraction and review. Computing the graph is cheap: 5 queries, about 20 ms for the demo case.
- Rejected entities, events and correlations are hidden by default. "Rejected" shows them,
  dashed and faded.

## 3. The builder (pure, like the correlation engine)

```
 plain facts ──► build(options) ──► nodes + edges (each edge has: why, confidence,
                                                    review, assertion kinds, evidence, events)
 options: include events / evidence / rejected · entity types · min correlation level
          focus + depth · max_nodes (300)
```

**Focus** uses a **breadth-first search (BFS)**: start at one node, visit its neighbours
(step 1), then their neighbours (step 2), and so on. Only what is reached is returned. This is
how an analyst explores a huge case: one person, then one or two steps out.

**Too big?** If more than 300 items would be drawn, the best-connected ones are kept and the
page says so. The plan's rule is: "do not load thousands of records into the browser."

## 4. The canvas (Cytoscape.js)

```
 React owns the DATA (nodes, edges, selection)  ─►  mirrored into ─►  Cytoscape owns the DRAWING
                                                                       (positions, zoom, pan)
```
- Cytoscape is created **once**. New data replaces its elements and runs the layout again. We
  never re-create it on each React render.
- **fCoSE layout** (force-directed): links act like springs and nodes push each other apart.
  Connected things end up close together.
- **Colours** come from our design tokens. Cytoscape cannot read `oklch(...)`, so we paint the
  colour on a 1×1 canvas and read back rgb. The colours are re-read when the theme changes.
- **Selection** fades everything except the item and its neighbours. **Search** dims
  non-matching items. Enter jumps to the first match.
- Every link is clickable in **three places**: the canvas, the inspector's link list, and the
  List view table. The canvas alone is not accessible, so the table carries the same
  information.

## 5. Problems we hit (and the lesson)

| Problem | Lesson |
|---|---|
| Page stuck on "Loading FALCON…" after installing Cytoscape | Known Vite issue: stop Vite, delete `node_modules/.vite`, restart |
| Page froze on a phone | Resize loop: the canvas widened its grid column, which triggered another resize. Fixed by fixing the column width (`minmax(0,1fr)`) and acting only on real size changes, once per frame |
| Selected item faded when it didn't match the search | Later CSS-like rules win; the "selected" rule must override "unmatched" |
| Whole-case graph unreadable on a phone | Phones open the List view first; Focus makes the graph small enough to read |
| Times in "why" texts were UTC | Format with the case's time zone, like everywhere else |
| Cytoscape warned about custom wheel speed | Keep library defaults unless you can test every mouse/touchpad |

## 6. Improvements for later

- **Shortest path** between two items ("how is PH004 linked to V001?"); Cytoscape has it built in. *(later)*
- **Centrality** ("who is the hub?"), shown as node size. *(P10)*
- Remember positions so the layout does not change on each filter. *(later)*
- Export the graph as PNG for reports. *(P11)*
- Links from AI similarity (similar documents, near-duplicate images). *(P10)*

## 7. Try it yourself

1. Sign in as `a.kumar@…`, CASE-2026-001, then **Relationship Graph**.
2. Type `V001` and press Enter. The van is selected and its neighbours highlighted.
3. In the panel, click **Appears in → CCTV-001** to read why that link exists.
4. Click **CCTV-001**, then **Focus**, then tick **Events**. You see only the break-in camera's world.
5. Open **List**, then click a **Related evidence** row, then **Full explanation and review**.
6. Click **PH001**, then **Timeline**. The timeline opens filtered to that phone.
