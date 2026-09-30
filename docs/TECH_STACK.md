# FALCON — Technology Stack

Every tool, library and AI model FALCON uses, why it was chosen, and when it arrives.
Everything is **free and open source** (or free for personal/education use). Total cost: **$0**.

Legend: ✅ in use now · 🔜 planned (phase)

```
 ┌────────────────────────────────────────────────────────────────────────────┐
 │ BROWSER   React 19 · TypeScript · Vite · Tailwind · shadcn/ui (Radix)       │
 │           React Router · TanStack Query · Zustand · Cytoscape · Leaflet     │
 └───────────────────────────────┬────────────────────────────────────────────┘
                                 │ /api  (JSON over HTTP, same origin via proxy)
 ┌───────────────────────────────▼────────────────────────────────────────────┐
 │ BACKEND   Python 3.12 · FastAPI · Pydantic · SQLAlchemy 2 · Alembic          │
 │           Worker process (Postgres job queue) · processing plugins          │
 │           AI: Tesseract · spaCy · sentence-transformers · Ollama (Qwen3)    │
 └───────────────┬───────────────────────────────┬────────────────────────────┘
                 │                               │
 ┌───────────────▼──────────────┐   ┌────────────▼───────────────┐
 │ PostgreSQL 17 (Docker)        │   │ Local disk storage          │
 │ + PostGIS + pgvector + pg_trgm│   │ (StorageService interface)  │
 └──────────────────────────────┘   └────────────────────────────┘
```

## 1. Frontend

| Tool | Version | Status | Job | Why this, not others |
|---|---|---|---|---|
| React | 19 | ✅ P1 | UI library | Largest ecosystem for graphs, tables, maps. Vue/Angular have fewer investigation-grade libraries. |
| TypeScript | 6 | ✅ P1 | Types for JavaScript | Catches mistakes before running; essential with 16 domain entities. `strict` mode on. |
| Vite | 8 | ✅ P1 | Dev server + build | Very fast; plain single-page app. Next.js adds server rendering we don't need (login-only app, no SEO). |
| Tailwind CSS | 4 | ✅ P2 | Styling with utility classes | Styles live next to markup; design tokens as CSS variables. |
| shadcn/ui (Radix base, Nova preset) | 4 | ✅ P2 | Component source copied into `src/components/ui` | We own and restyle the code. Radix gives keyboard + screen-reader support. MUI/Ant Design look generic. |
| lucide-react | 1.x | ✅ P2 | Icons | Consistent line icons; tree-shaken (only used icons ship). |
| React Router | 7 | ✅ P2 | Pages / URLs, lazy loading | Standard; route-level code splitting. |
| TanStack Query | 5 | ✅ P2 | Server data: loading, caching, retry | Removes hand-written loading/error code on every screen. |
| Zustand | 5 | ✅ P2 | Tiny global UI state (current investigation) | Redux is far heavier than needed. |
| sonner | 2 | ✅ P2 | Toast notifications | Accessible, small. |
| cmdk | 1 | ✅ P2 | Ctrl+K command/search palette | Fast fuzzy matching, keyboard-first. |
| Geist + JetBrains Mono | — | ✅ P2 | Fonts (sans + mono for IDs) | Self-hosted via @fontsource: no Google Fonts request. |
| oxlint | 1.x | ✅ P1 | Linter | Very fast Rust-based linter shipped with the Vite template. |
| TanStack Table + Virtual | — | 🔜 P4–P5 | Large data tables | Renders only visible rows (thousands of evidence items). |
| React Hook Form + Zod | 7 / 4 | ✅ P3 | Forms + validation | One schema = type + runtime validation. |
| openapi-typescript | — | 🔜 P4 | Generate TS types from the API | Frontend and backend types can never drift apart. |
| Recharts | — | 🔜 P11 | Dashboard charts | Simple, good for aggregate statistics. |
| vis-timeline | — | 🔜 P7 | Zoomable timeline | Built-in zoom, grouping, ranges. |
| Leaflet + OpenStreetMap | — | 🔜 P7 | Maps | Free, no API key. Google Maps requires billing. |
| Cytoscape.js | — | 🔜 P9 | Relationship graph | Built for network analysis (layouts, shortest path, centrality). React Flow is for flowcharts; D3 means building everything. |

## 2. Backend

| Tool | Version | Status | Job | Why |
|---|---|---|---|---|
| Python | 3.12 | ✅ P1 | Language | The free AI/forensics tools (OCR, NER, embeddings, EXIF) are all Python → one backend language. |
| uv | 0.10 | ✅ P1 | Package manager + lockfile | 10–100× faster than pip. |
| FastAPI | 0.14x | ✅ P1 | Web API | Type-hint based validation, automatic OpenAPI docs at `/api/docs`. Django is HTML-first; Spring Boot is heavy. |
| Uvicorn | 0.54 | ✅ P1 | Runs the FastAPI app | Standard ASGI server. |
| Pydantic + pydantic-settings | 2 | ✅ P1 | Validation + typed config from `.env` | `SecretStr` hides passwords in logs. |
| SQLAlchemy | 2 | ✅ P1 | Database toolkit / ORM | Industry standard; raw SQL when needed. |
| psycopg | 3 | ✅ P1 | PostgreSQL driver | Modern, maintained. |
| pytest + httpx2 | — | ✅ P1 | Backend tests | Standard Python testing. |
| Ruff | 0.16 | ✅ P1 | Lint + format | One fast tool replaces flake8 + isort + black. |
| Alembic | 1.x | ✅ P3 | Database migrations | Version control for the database structure; migrations also build the test database. |
| argon2-cffi | — | ✅ P3 | Password hashing | Current best practice (Argon2id), OWASP-recommended. |
| pyotp | — | 🔜 P11 | TOTP multi-factor codes | Works with any authenticator app. The user table is already MFA-ready. |
| Server-side sessions (httpOnly cookie) | — | ✅ P3 | Sign-in state | Revocable instantly; the database stores only a SHA-256 hash of each token. Chosen over JWT, which cannot be revoked before it expires. |
| Postgres job queue (`FOR UPDATE SKIP LOCKED`) | — | 🔜 P5 | Background processing | The ProcessingJob table *is* the queue — no Redis/Celery to run. |

## 3. Data & infrastructure

| Tool | Version | Status | Job | Why |
|---|---|---|---|---|
| PostgreSQL | 17.5 | ✅ P0 | Main database | Relational data (case → evidence → entity → event). MongoDB suits documents, not relationships. |
| PostGIS | 3.5 | ✅ P0 | Geo queries ("within 200 m") | Location correlation in one SQL line. |
| pgvector | 0.8 | ✅ P0 | Vector similarity search | Duplicate/similar evidence without a separate vector DB. |
| pg_trgm | 1.6 | ✅ P0 | Fuzzy text search | "CCTV-01" finds "CCTV-001". Replaces Elasticsearch for our scale. |
| Graph in PostgreSQL | — | 🔜 P9 | Relationships table + recursive SQL | One database = no sync problems. Neo4j only if ever justified. |
| Docker Desktop + Compose | 29 / v5 | ✅ P0 | Runs PostgreSQL in a container | Same setup on any machine; nothing installed into Windows. |
| WSL 2 | 2.7 | ✅ P0 | Linux kernel for Docker on Windows | Containers are Linux programs. |
| Local disk storage | — | 🔜 P5 | Evidence files (`storage/`, git-ignored) | MinIO's free edition was archived in 2026; a `StorageService` interface lets us move to S3-compatible cloud storage later. |
| Git + GitHub | — | ✅ P0 | Version control + backup | github.com/kandiharish/Falcon |
| GitHub Actions | — | 🔜 P12 | Automatic tests on every push | Free for public repos. |

## 4. AI & processing — every model

AI **suggests**, humans **decide**. Every AI output is labelled (Extracted / Detected / Inferred), carries a confidence and links to its source evidence. All models run **locally** — evidence never leaves the machine.

| Capability | Model / tool | Type | Size | Status | Why |
|---|---|---|---|---|---|
| OCR (text in images/scans) | **Tesseract 5** with the `eng` LSTM model | Neural OCR | ~20 MB | 🔜 P6 | Free, mature, CPU-only. |
| PDF text | **PyMuPDF** | Parser (no ML) | — | 🔜 P6 | Exact text from digital PDFs; OCR only for scans. |
| Photo metadata (GPS, time, camera) | **Pillow** EXIF reader | Parser (no ML) | — | 🔜 P5 | Facts, not guesses → labelled *Extracted*. |
| Video metadata | **FFmpeg `ffprobe`** | Parser (no ML) | — | 🔜 P6 | Duration, codec, creation time. |
| Names, places, organisations in text | **spaCy `en_core_web_sm`** | Named-entity recognition model | ~12 MB | 🔜 P6 | Small, fast on CPU; upgradeable to `en_core_web_trf` for accuracy. |
| Phone numbers, emails, plates, account IDs | **Regex + `phonenumbers`** (port of Google libphonenumber) | Rules (no ML) | — | 🔜 P6 | 100% explainable, no false "AI" confidence. |
| Text similarity / duplicate documents | **sentence-transformers `all-MiniLM-L6-v2`** | Embedding model (384-dim vectors) | ~90 MB | 🔜 P10 | Small, CPU-friendly; vectors stored in pgvector. |
| Near-duplicate images | **imagehash** (perceptual hash) | Algorithm (no ML) | — | 🔜 P10 | Detects resized/re-encoded copies. |
| Natural-language search, summaries, Investigation Assistant agent | **Qwen3 8B** (`qwen3:8b`) via **Ollama** | Large language model with tool calling | ~5 GB (4-bit) | 🔜 P10 | Runs on 16 GB RAM; good tool calling. Fallback: `qwen3:4b` (~2.5 GB) on weaker machines. |
| Correlation scoring | **FALCON correlation engine** (our own Python rules) | Deterministic scoring, no ML | — | 🔜 P8 | Same input → same output; every score explained factor by factor. |

**Deliberately not used:** face recognition (ethically risky, biased, plan §52) and any cloud AI
that would send evidence to a third party. The `AIProvider` interface allows swapping in a stronger
model later without changing FALCON.

**The Investigation Assistant (agent, P10)** is our own ~150-line tool-calling loop — no LangChain.
Read-only tools, acts with the user's permissions, must cite evidence IDs, max 8 steps, every tool
call audited, output labelled *AI-Assisted · Requires Review*.

## 5. How FALCON is being built

| Tool | Role |
|---|---|
| **Claude Opus 5.5** (Anthropic), via Claude Code in VS Code | Development assistant: writes code, runs tests, explains. **Not part of FALCON** — it never runs inside the product. |
| Playwright | Drives a real browser to test screens (used during development; automated E2E tests in P12). |

## 6. Ports on this machine

| Service | Port |
|---|---|
| Frontend (Vite) | 5190 |
| Backend (FastAPI) | 8010 |
| Database (Docker) | 5434 |
