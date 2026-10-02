# Phase 4 — Investigation Management

## 1. What we built

```
 Investigations list ──► search · status · priority · pages (filters live in the URL)
        │  New investigation ──► CASE-2026-005 (draft, you are lead)
        ▼
 Investigation detail
   ├─ Overview   summary · details · tags · workflow · case contents (0 until P5+)
   ├─ Team       members · add member (audited)
   └─ Activity   who changed what: "Status: Draft → Active"
```

The mock data is gone: everything comes from PostgreSQL through the API.

## 2. The layers, now complete for one feature

```
 InvestigationsPage.tsx          screen          (what the user sees)
        │ useInvestigations()
 queries.ts                      cache           (TanStack Query)
        │ InvestigationService.list()
 investigationService.ts         client service  (HTTP, snake_case → camelCase)
        │ GET /api/investigations?search=…
 api/investigations.py           API route       (validate input, shape output)
        │ service.list_investigations()
 services/investigation_service  business rules  (isolation, transitions, audit)
        │ repo.list_visible()
 repositories/investigation_…    data access     (the only place with SQL)
        │
 PostgreSQL
```

Each layer has one job. To change *how* data is stored, edit the repository. To change a
*rule*, edit the service. Screens never change for either.

## 3. Key ideas

### 3.1 Data isolation — "need to know"
```
 Officer Varma ──member of──► CASE-001, CASE-003, CASE-005
                ──not member──► CASE-002  →  404 "does not exist or you are not on its team"
 Supervisor    ──sees all (oversight)
 Admin         ──sees none (no investigation:read)
```
A case you may not see answers **404, not 403** — "forbidden" would confirm it exists.

### 3.2 Case numbers that never collide
```sql
INSERT INTO investigation_reference_counters (year, last_value) VALUES (2026, 1)
ON CONFLICT (year) DO UPDATE SET last_value = counters.last_value + 1
RETURNING last_value;     -- one atomic statement → CASE-2026-005
```
Two people pressing "Create" at the same moment cannot get the same number: the database
locks the counter row while incrementing it. ("Read max, add 1" in Python would race.)

### 3.3 Status as a state machine
```
 draft ──► active ──► under_review ──► closed ──► archived (read-only, final)
   │         │  ▲         │              │
   │         ▼  │         ▼              └──► active (reopen)
   │      suspended ──► closed
   └──► archived
```
The server enforces it (409 with "Allowed next: …"); the UI only offers valid moves.

### 3.4 Audit with before/after
Every change stores only the fields that changed:
`previous_state {"status":"draft"}` → `new_state {"status":"active"}`.
The Activity tab turns that into "Status: Draft → Active".

### 3.5 Generated API types
`npm run api:types` reads the backend's OpenAPI description and writes `src/api/schema.d.ts`.
If the backend renames a field, TypeScript shows every screen that breaks — before users do.

### 3.6 Filters in the URL
`/investigations?search=dock&status=active&page=2` — bookmarkable, shareable, Back button works.
Typing waits 300 ms after the last key before searching (debounce) to avoid one request per key.

## 4. Why these choices

| Choice | Why | Instead of |
|---|---|---|
| Repository layer | SQL in one place; services stay readable rules | queries scattered through routes |
| Domain errors → one handler | services say *what* went wrong; API decides the HTTP code | HTTPException deep in business code |
| Atomic counter (`ON CONFLICT … RETURNING`) | correct under concurrency | `SELECT max()+1` (race condition) |
| 404 for hidden cases | doesn't reveal that a case exists | 403 |
| Trigram index on titles | fast `ILIKE '%dock%'` on large tables | full table scans |
| Server-side pagination | the browser never loads thousands of rows (plan §39) | fetch everything, filter in JS |
| `dev.ps1` | one command starts the whole stack | 5 manual steps after every reboot |

## 5. Problems we hit (and the lesson)

| Problem | Lesson |
|---|---|
| `openapi-typescript` refused to install (wants TypeScript 5, we have 6) | Don't force peer dependencies; run build-time tools in isolation with `npx pkg@version` |
| PowerShell 5.1 script stopped on Docker's normal progress output | Native tools write progress to stderr; check `$LASTEXITCODE`, not the error stream |
| Test browser locked by a leftover process | Clean up only processes you can positively identify (by profile path) |
| Lint: "missing dependencies" in the search effect | Effects with stale values cause subtle bugs; moved the delay into the event handler and used functional URL updates |
| Signed out after closing the browser | Correct! Without "Remember", the session cookie ends with the browser |

## 6. Improvements for later

- Remove a member / transfer lead role (with audit). *(P11)*
- Show actor display names (not emails) in Activity. *(P11)*
- Investigation types managed by administrators instead of a fixed list. *(P11)*
- Real counts once evidence, entities, events and correlations exist. *(P5–P8)*
- PostgreSQL row-level security as a second isolation layer. *(P11)*

## 7. Try it yourself

1. `.\dev.ps1` (if not already running), sign in as `r.varma@…`.
2. Investigations → only 3 cases. Sign in as `k.iyer@…` (supervisor) → all cases.
3. New investigation → note the case number; change status; add M. Das; open Activity.
4. Sign in as `m.das@…` → the new case is now visible to them.
5. Try opening `/investigations/CASE-2026-002` as Varma → "not found".
