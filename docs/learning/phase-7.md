# Phase 7 — Timeline, Map and Time Zones

## 1. What we built

```
 Timeline page ─┬─ Timeline view: lanes (evidence source | kind of event | entity), zoom, pan
                ├─ Map view: OpenStreetMap, clustered pins, an entity's movement path, replay slider
                ├─ shared filters: kind of event · entity · evidence source · show rejected
                └─ click any point → drawer: details, review, "Open evidence", entity profiles
 Investigations get a time zone; every time is shown (and typed times read) in it.
```

## 2. Time zones — the most common evidence-timeline bug

```
 stored   2026-09-28 15:00:00 UTC          ← one true moment, in the database
 shown    20:30 in Asia/Kolkata (+05:30)   ← the case's zone, for EVERY viewer
 typed    "20:30" in a form                ← read in the case's zone → 15:00 UTC
 no zone  "2026-09-28 20:33" in a CSV      ← read in the case's zone, flagged, confidence 0.8
```

Why the case's zone and not the viewer's? An analyst in London and one in Hyderabad must
both see "20:30" for the break-in, and "28 Sept" must not become "29 Sept" for one of them.

The browser's `Intl` API does all of this — no date library:
`new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', … })`.
Python on Windows needs `tzdata` for zone names.

## 3. How the timeline works (our own component)

```
 x = (time − viewStart) / (viewEnd − viewStart) × width
 zoom: shrink/grow [viewStart, viewEnd] around the mouse     pan: shift it sideways
 ticks: pick a step (1 s … 30 days) so labels are ~110 px apart, aligned to LOCAL round times
 lanes: one row per group; close points stack into sub-rows (greedy)
```

Design decisions:
- The view is **derived**: "the user's zoom for this data set, otherwise fit-all". New filters
  → new data → fit-all automatically, with no effect that copies props into state.
- Each point is a real `<button>` with a full description (`aria-label`) — keyboard and
  screen-reader friendly, which canvas/SVG timeline libraries often are not.
- The wheel listener is native and non-passive, so zooming does not also scroll the page.
- Filled dots = automatic results; hollow rings = entered by a person.

## 4. How the map works

- **Leaflet** draws OpenStreetMap tiles (free, attribution shown). In dark mode the tiles are
  darkened with a CSS filter instead of loading a second map style.
- **Clustering** groups nearby pins into numbered bubbles.
- **Movement**: choose an entity → its located events in time order become a dashed path.
- **Replay**: the slider shows only events up to a moment; ▶ steps through the case.
- Event text inside map tooltips is HTML-escaped — evidence content must never become code (XSS).
- The map code (~55 kB gzipped) loads only when someone opens the Map view.

## 5. PostGIS, for the first time

```sql
ST_DWithin(geography(ST_MakePoint(lon, lat)), geography(ST_MakePoint(78.39215, 17.43862)), 100)
```
"Is this event within 100 m of the warehouse?" — measured on the Earth's surface in metres.
The API's `near_lat/near_lon/radius_m` filter uses it; Phase 8's location correlation builds on it.
Note: `ST_MakePoint(longitude, latitude)` — **longitude first** (x, y), a classic mistake.

## 6. Problems we hit (and the lesson)

| Problem | Lesson |
|---|---|
| vis-timeline needs 9 extra packages incl. moment | Check a library's dependencies before adopting it; small focused components can be better |
| Axis labels at 20:30, 23:30 | Ticks were aligned to UTC; align to the *zone's* round times |
| Login page stuck on "Loading" after installing Leaflet | Vite re-optimised dependencies; the test browser held stuck requests. Restart Vite with a cleared `node_modules/.vite`, use a fresh browser |
| Event details squashed to one word per line in the drawer | Components need a compact layout for narrow places |
| Drawer opened with a tooltip already showing | Control initial focus in dialogs |
| A rejected-looking "dashed" marker | Hollow rings read more clearly than dashed borders |
| `useEffect(() => setState(...))` warnings | Derive values during render instead of syncing state in effects |

## 7. Improvements for later

- Map clusters / heat-map for thousands of points; map layers per entity. *(P12 performance)*
- Timeline mini-map (overview strip) and keyboard zoom shortcuts. *(later)*
- "Events near here" by clicking the map (the API filter exists). *(P8)*
- Per-user choice to also show times in their own zone. *(P11)*

## 8. Try it yourself

1. Sign in as `a.kumar@…`, CASE-2026-001 → **Timeline**.
2. Scroll on the timeline to zoom, drag to move, "Fit all" to reset. Try *Lanes: entity*.
3. Click a point → the drawer → "Open evidence".
4. **Map** → choose entity *D001* → the device's path; press ▶ to replay.
5. Investigation page → change the **Time zone** → the timeline's labels change.
