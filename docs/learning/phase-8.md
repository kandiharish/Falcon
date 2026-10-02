# Phase 8: Correlation Engine

## 1. What we built

```
 evidence processed / entity or event reviewed / "Run correlation"
            │
            ▼
 load facts ── events (time, place) + entities per evidence item, rejected ones left out
            │
            ▼
 ENGINE (pure Python, no database) ── every evidence pair → factors → score → level
            │
            ▼
 save ── upsert by pair · pending + no longer found → deleted · reviewed + no longer found → "stale"
            │
            ▼
 UI ── Correlations list · "Why this relationship exists" · evidence tab · Confirm / Reject (audited)
```

A correlation is a **potential relationship between two evidence items**, such as "the CCTV clip and
the number-plate camera log may show the same thing". It is never a conclusion. An analyst
confirms or rejects every one.

## 2. The scoring rules

```
 factor     question                                              weight   score 0–1
 ENTITY     same phone / vehicle / device / person in both?        0.45    weaker sighting's confidence
 TIME       two events within 30 min?                               0.30    1 − Δt / 30 min
 LOCATION   two events within 500 m?                                0.25    1 − distance / 500 m

 score = Σ weight × factor score         High ≥ 0.75 · Medium ≥ 0.50 · Low below
 kept only if: a shared entity, OR at least two factors agree
```

The real COR-004 example:

```
 CCTV-001 ⟷ VEH-001
   entity    V001 (ZZ99 ZZ 0001), confidence 0.95   0.95 × 0.45 = 0.43
   time      E002 20:36:50 vs E016 20:37:00 (10 s)  0.99 × 0.30 = 0.30
   location  44 m apart                             0.91 × 0.25 = 0.23
                                                         score = 0.95  → HIGH
```

Why these choices:
- **Rules, not machine learning.** We have no labelled training data, and an investigator must
  be able to explain the score in court. Rules give the same answer every time and each
  number can be traced.
- **The entity factor weighs most.** The same plate in two sources is stronger than "two things
  happened nearby".
- **Two factors are needed without an entity.** Two unrelated events at the same minute are
  a coincidence. The same minute *and* the same street is worth a look.
- **The weaker confidence counts.** A shared entity is only as reliable as its weakest sighting.
  That is why witness-OCR pairs are Low (0.68).
- **Linear falloff** is easy to explain: "10 s of a 30 min window → 0.99".

## 3. How the engine is fast

```
 naive:  every event × every other event                 n²
 ours:   sort events by time once, then compare each one only with
         the events AFTER it inside the 30-min window, and stop    ~ n log n
```

This is a **sweep line**. Because the list is sorted, the first event outside the window means
every later one is outside too (`break`). Distance uses the **haversine** formula, the same
great-circle idea as PostGIS geography. Doing it in Python keeps the engine a pure function
that we can unit-test without a database (12 engine tests).

## 4. Re-running safely (idempotency)

```
 found again  → update score/factors (no change → counted as nothing)
 new pair     → create with the next COR-### number
 gone + pending   → delete (nobody looked at it)
 gone + reviewed  → keep, mark STALE ("no longer found"), and keep the decision for the record
```

A bug we hit: the same moment written as `+05:30` once and `UTC` the next time looked like a
change. The fix is to always store times in UTC inside factor details. Lesson: compare
normalised values.

Correlation re-runs automatically after processing finishes and after any entity or event
review. If that refresh fails, it is logged and never breaks the action that triggered it.

## 5. Review and audit

- **Confirm** needs no reason. **Reject** needs a reason. The API returns 422 without one,
  and the button stays disabled until a note is written.
- Only users with `correlation:review` who are on the case team can run or review. Evidence
  analysts can read correlations but cannot judge them (403).
- `correlation.run` and `correlation.reviewed` go into the append-only audit log.

## 6. Problems we hit (and the lesson)

| Problem | Lesson |
|---|---|
| Re-run reported "updated" with nothing changed | Normalise (UTC) before storing or comparing |
| Test phone numbers like +1555… were not detected in text | Text detection accepts only *valid* numbers; use 202-555-01xx |
| Evidence IDs wrapped ("GPS-/001") on phones | Identifiers get `whitespace-nowrap` |
| Wrapped tab row overlapped the content on phones | A sideways-scrolling tab row instead of wrapping |
| Test sign-in echoed secrets into tool logs | Sign in through the API and revoke the session afterwards |

## 7. Improvements for later

- More factors: shared *communication* (A called B), the same file hash, and text similarity
  using embeddings. *(P10)*
- Per-case tunable window and radius. Show "what if 60 min?" *(later)*
- Correlation of *entities* (two phones always together), not only evidence. *(P9 graph)*
- Background run for very large cases (it is currently in-request and fast for hundreds of
  events). *(P12)*

## 8. Try it yourself

1. Sign in as `a.kumar@…`, CASE-2026-001, then **Correlations**. You will see 12, strongest first.
2. Open **COR-004** and read each factor's `score × weight = contribution`.
3. Write a note and click **Confirm relationship**. The decision shows who reviewed it and when.
4. Evidence **VEH-001**, then the **Correlations** tab, shows every relationship of that item.
5. Reject entity *V001* on the Entities page. The confirmed COR-004 becomes "No longer found",
   and pending ones that depended on it disappear.
