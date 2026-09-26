# FALCON

**Forensic Analysis and Linked Crime Observation Network** — an investigation-support
platform that turns fragmented evidence into connected, explainable intelligence while
keeping the investigator in control.

> Store → Extract → Connect → Explain

This is a learning project. The product specification is in [plan.md](plan.md);
phase-by-phase learning notes are in [docs/learning/](docs/learning/).

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

## Project layout

```
falcon/
├── infra/postgres/     database image (Dockerfile) + first-run SQL
├── docs/learning/      learning notes per phase
├── docker-compose.yml  local services
└── plan.md             product specification
```
