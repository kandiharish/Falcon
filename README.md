# FALCON

**Forensic Analysis and Linked Crime Observation Network** — an investigation-support
platform that turns fragmented evidence into connected, explainable intelligence while
keeping the investigator in control.

> Store → Extract → Connect → Explain

This is a learning project. The product specification is in [plan.md](plan.md);
the full technology stack (including every AI model) is in [docs/TECH_STACK.md](docs/TECH_STACK.md);
phase-by-phase learning notes are in [docs/learning/](docs/learning/).

## Progress

| Phase | Status |
|---|---|
| P0 Project setup (Git, Docker, PostgreSQL + PostGIS + pgvector) | ✅ |
| P1 Skeleton (browser ↔ API ↔ database) | ✅ |
| P2 Design system + application shell | ✅ |
| P3 Authentication, roles, audit foundation | ✅ |
| P4 Investigation management (real data, team isolation, audit history) | ✅ |
| P5 Evidence upload, integrity (SHA-256), background processing | ✅ |
| P6 Information extraction: entities and events | next |

## Prerequisites

- Git, Node.js 22+, Python 3.12+, [uv](https://docs.astral.sh/uv/)
- Docker Desktop (with WSL 2 on Windows)

## Start the local infrastructure

```sh
cp .env.example .env        # then set a strong POSTGRES_PASSWORD
docker compose up -d        # starts PostgreSQL (+ PostGIS, pgvector, pg_trgm)
docker compose ps           # "db" should show (healthy)
```

The database listens on `127.0.0.1:5434` (see `POSTGRES_PORT` in `.env`).

## Run the app

**Windows, one command:** `.\dev.ps1` — starts Docker, the database, applies migrations and opens
the backend, the processing worker and the frontend in their own windows.

Or by hand, in four terminals:

```sh
docker compose up -d                                          # 1. database
cd backend  && uv run uvicorn app.main:app --reload --port 8010   # 2. API
cd backend  && uv run python -m app.worker                    # 3. processing worker
cd frontend && npm install && npm run dev                     # 4. web app
```

First time only — create the tables and the fictional demo users:

```sh
cd backend
uv run alembic upgrade head                    # create/upgrade database tables
uv run python -m app.scripts.seed_demo_users            # password = DEMO_PASSWORD in .env
uv run python -m app.scripts.seed_demo_investigations   # fictional demo cases + teams
uv run python -m app.scripts.seed_demo_evidence         # fictional evidence for CASE-2026-001
```

Start over with fresh demo data at any time (development only, deletes everything):

```sh
uv run python -m app.scripts.reset_demo_data --yes
```

Open http://localhost:5190. API docs: http://localhost:8010/api/docs

| Service  | Port | Notes |
|----------|------|-------|
| Frontend | 5190 | Vite dev server; proxies `/api` to the backend |
| Backend  | 8010 | FastAPI |
| Database | 5434 | PostgreSQL in Docker |

## Project layout

```
falcon/
├── dev.ps1             start everything (Windows)
├── backend/            FastAPI API (Python, uv)
├── frontend/           React + TypeScript web app (Vite)
├── infra/postgres/     database image (Dockerfile) + first-run SQL
├── docs/learning/      learning notes per phase
├── docker-compose.yml  local services
└── plan.md             product specification
```
