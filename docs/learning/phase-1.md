# Phase 1 — Skeleton: Browser ↔ API ↔ Database

## 1. What we built

A page with one button. Pressing it proves that all three layers of FALCON can talk.

```
 ┌──────────────────┐  GET /api/health   ┌──────────────────┐  SQL   ┌──────────────────┐
 │ BROWSER          │ ─────────────────► │ BACKEND          │ ─────► │ DATABASE         │
 │ React page       │                    │ FastAPI          │        │ PostgreSQL       │
 │ localhost:5190   │ ◄───────────────── │ localhost:8010   │ ◄───── │ localhost:5434   │
 └──────────────────┘   JSON answer      └──────────────────┘ rows   └──────────────────┘
     what you SEE                           the BRAIN                    the MEMORY
```

## 2. How one click travels (the full journey)

```
 ① You click "Check system"
        │
 ② App.tsx calls SystemService.getHealth()          ← UI never calls fetch() itself
        │
 ③ apiClient.ts does fetch("/api/health")
        │
 ④ Vite dev server sees "/api" → forwards to 127.0.0.1:8010   (the "proxy")
        │
 ⑤ FastAPI routes /api/health → health() in api/health.py
        │
 ⑥ get_db() lends a database session from the connection pool
        │
 ⑦ SQL: SHOW server_version; SELECT … FROM pg_extension
        │
 ⑧ Pydantic turns the result into JSON: {"status":"ok","database":{…}}
        │
 ⑨ Back through the proxy to the browser
        │
 ⑩ React updates state → the ✓ rows appear
```

## 3. The files and what each one does

### Backend (`backend/`)

| File | Job | One-line idea |
|---|---|---|
| `pyproject.toml` | project + dependency list | like a shopping list for Python packages |
| `uv.lock` | exact versions installed | everyone gets identical packages |
| `app/core/config.py` | settings from `.env` | secrets come from the environment, never code |
| `app/db/session.py` | database connection | one shared engine, one session per request |
| `app/api/health.py` | the `/api/health` endpoint | asks the DB "are you alive? which extensions?" |
| `app/main.py` | creates the app | plugs routers in under `/api` |
| `tests/test_health.py` | automatic test | proves the endpoint works, in 5 seconds |

### Frontend (`frontend/`)

| File | Job |
|---|---|
| `vite.config.ts` | dev server on port 5190 + proxy `/api` → backend |
| `src/services/apiClient.ts` | the ONLY place that does HTTP; turns failures into human messages |
| `src/services/systemService.ts` | "SystemService" + the `SystemHealth` type |
| `src/App.tsx` | the page: idle → loading → success / error |
| `src/index.css` | temporary styling (replaced by the design system in P2) |

## 4. Key ideas, explained

### 4.1 Frontend and backend are two separate programs

```
 Frontend = the restaurant's dining room   (menus, tables, what guests see)
 Backend  = the kitchen                    (does the real work, guests never enter)
 API      = the waiter's order slip         (a fixed format both sides agree on: JSON)
```

### 4.2 The proxy (why no CORS)

Browsers block a page on one address from reading answers from another address
(this protection is called **CORS**). Our page is on `:5190` and the API on `:8010` —
two different addresses. The proxy makes the browser think everything comes from `:5190`:

```
 Browser ──/api/health──► Vite :5190 ──forwards──► FastAPI :8010
         (same address,             (server-to-server,
          no CORS problem)           browsers' rules don't apply)
```

Bonus: in P3, login cookies will just work, because everything is one address.

### 4.3 The layers we started (plan §40, §49)

```
 App.tsx  ──►  SystemService  ──►  apiClient  ──►  HTTP
 (UI)          (what to ask)       (how to ask)
```

If one day the API changes, only the service changes — not every screen.
Backend mirror: `api/` (HTTP) → `db/` (data access). `services/` and `domain/` arrive in P4.

### 4.4 Dependency injection (`Depends(get_db)`)

`health()` never opens a DB connection itself. It *declares* "I need a session",
and FastAPI hands one over and closes it afterwards. That makes code easy to test
(a test can hand in a fake session) and impossible to forget closing.

### 4.5 Connection pool

Opening a database connection is slow (~50 ms). The engine keeps a few open and lends
them out, like a library lending books instead of printing a new one per reader.

### 4.6 UI states

Every screen that loads data has four states. We handle all of them:

```
 idle ──click──► loading ──┬──► success (✓ rows)
                           └──► error   (human-readable message)
```

## 5. Why these choices

| Choice | Why | Why not the alternative |
|---|---|---|
| **uv** for Python | 10–100× faster than pip; lockfile built in | pip + venv: slower, no lockfile by default |
| **psycopg 3** driver | modern, maintained PostgreSQL driver | psycopg2: older generation |
| **SQLAlchemy 2** | industry standard; raw SQL now, ORM models in P4 | writing all SQL by hand gets messy at scale |
| **pydantic-settings** | typed config; `SecretStr` hides the password in logs | `os.environ[...]` everywhere: untyped, easy to leak |
| **Vite proxy** | same-origin → no CORS, cookies work | enabling CORS on the API: more config, weaker default |
| **Service layer now** | mock/real data can swap later without UI changes | calling `fetch` in components: scattered, hard to change |
| Own ports 8010 / 5190 | other projects on this PC use 8000 and 5173 | defaults would clash; `strictPort` fails loudly |

## 6. Problems we hit (and the lesson)

| Problem | Lesson |
|---|---|
| Port 8000 and 5173 already used by other projects | Each program needs its own port. `strictPort: true` = fail loudly instead of silently moving |
| First test took 45 s, then 5 s | First runs are slow (Python compiles files, antivirus scans new packages) — measure before "fixing" |
| Test client warned "install httpx2" | Read warnings: they tell you about changes before they become errors |
| Backend down showed "error (502)" | 502 comes from the proxy, not our API. Translate codes into messages a person understands |

## 7. Improvements for later

- **Generate TypeScript types from the API** (openapi-typescript) so `SystemHealth` can't drift from Python's `HealthResponse`. *(P2/P3)*
- **TanStack Query** for loading/caching/retries instead of hand-written state. *(P2)*
- **Design system + Tailwind** to replace the temporary CSS. *(P2)*
- **Separate liveness vs readiness** (`/health/live`, `/health/ready`) — hosting platforms use these. *(P12)*
- **One command to start everything** (e.g. a small script or `docker compose` for all three). *(later)*
- **Structured logging** with request IDs so a click can be traced through the backend logs. *(P11)*

## 8. Try it yourself

```sh
docker compose up -d
cd backend  && uv run uvicorn app.main:app --reload --port 8010
cd frontend && npm run dev
```

- Open http://localhost:5190 → **Check system**.
- Open http://localhost:8010/api/docs → FastAPI's free interactive docs. Try `/api/health` there.
- Stop the backend (Ctrl+C) and press the button again → see the friendly error.
