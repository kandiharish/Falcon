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
 │           AI: RapidOCR · spaCy · Ollama (all-MiniLM + Qwen3) · pgvector     │
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
| openapi-typescript | 7.13 (via npx) | ✅ P4 | Generate TS types from the API (`npm run api:types`) | Frontend and backend types can never drift apart. Run through npx because it officially supports TypeScript 5 only. |
| Own bar/column charts (plain HTML + Tailwind) | — | ✅ P11 | Dashboard charts | *Replaced Recharts:* a few bars and columns need no library (~0 kB vs ~100 kB). Each chart also states its numbers in words for screen readers. |
| FALCON TimelineChart (own component) | — | ✅ P7 | Zoomable, pannable timeline with lanes | *Replaced vis-timeline* (needs 9 peer packages incl. moment; hard to theme and make keyboard-accessible). ~250 lines, every event a real button. |
| Leaflet 1.9 + react-leaflet 5 + OpenStreetMap tiles | — | ✅ P7 | Map of located events, entity movement, replay slider | Free, no API key (Google Maps requires billing). Map code is lazy-loaded. |
| leaflet.markercluster | 1.5 | ✅ P7 | Groups nearby points into numbered bubbles | Keeps maps readable with many events. |
| Intl API (built into browsers) | — | ✅ P7 | Time zones: show/read times in the case's zone | No date library needed (moment / date-fns not required). |
| tzdata (Python) | — | ✅ P7 | IANA time-zone database for the backend | Windows has no system zone database. |
| Cytoscape.js + cytoscape-fcose | 3.34 / 2.2 | ✅ P9 | Relationship graph on a canvas; fCoSE force-directed layout | Built for network analysis (layouts, shortest path, centrality); MIT. React Flow is for flowcharts; D3 means building everything. Used directly (no unmaintained React wrapper), lazy-loaded (~178 kB gzip). |

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
| python-multipart | 0.0.x | ✅ P5 | File uploads (multipart forms) | Required by FastAPI for `UploadFile`. |
| filetype | 1.2 | ✅ P5 | Detect real file type from content ("magic bytes") | Pure Python (no system library needed on Windows), unlike python-magic. |
| Alembic | 1.x | ✅ P3 | Database migrations | Version control for the database structure; migrations also build the test database. |
| argon2-cffi | — | ✅ P3 | Password hashing | Current best practice (Argon2id), OWASP-recommended. |
| Own TOTP (RFC 6238, ~20 lines of HMAC-SHA1) | — | ✅ P11 | Multi-factor codes for any authenticator app | *Replaced pyotp:* small enough to own and to learn from; verified against the RFC's official test vectors. Replay of a used code blocked; ±30 s clock drift allowed. |
| cryptography (AES-256-GCM) | 50 | ✅ P11 | Encrypts MFA secrets at rest; key in `FALCON_SECRET_KEY` (environment only) | The standard Python crypto library; authenticated encryption detects tampering. |
| segno | 1.6 | ✅ P11 | QR code (SVG) for authenticator set-up | Pure Python, tiny, BSD licence. |
| Server-side sessions (httpOnly cookie) | — | ✅ P3 | Sign-in state | Revocable instantly; the database stores only a SHA-256 hash of each token. Chosen over JWT, which cannot be revoked before it expires. |
| Postgres job queue (`FOR UPDATE SKIP LOCKED`) | — | ✅ P5 | Background processing (`python -m app.worker`) | The ProcessingJob table *is* the queue — no Redis/Celery to run. Tested with two competing workers. |

## 3. Data & infrastructure

| Tool | Version | Status | Job | Why |
|---|---|---|---|---|
| PostgreSQL | 17.5 | ✅ P0 | Main database | Relational data (case → evidence → entity → event). MongoDB suits documents, not relationships. |
| PostGIS | 3.5 | ✅ P0, used P7 | Geo queries: `ST_DWithin` on geography points ("events within 100 m") | Real distances on the Earth's surface, in one SQL line. |
| pgvector (+ `pgvector` Python 0.5) | 0.8 | ✅ P0, used P10 | Vector similarity search: `evidence_chunks.embedding vector(384)` with an HNSW cosine index | Similar evidence and meaning-based search without a separate vector DB. |
| pg_trgm | 1.6 | ✅ P0 | Fuzzy text search | "CCTV-01" finds "CCTV-001". Replaces Elasticsearch for our scale. |
| Graph in PostgreSQL | — | ✅ P9 | Graph = a view over mentions, event participants and correlations, built per request by a pure Python builder (BFS for focus) | One database = no sync problems, no copy that can go stale. Neo4j only if cases ever reach millions of links. |
| Docker Desktop + Compose | 29 / v5 | ✅ P0 | Runs PostgreSQL in a container | Same setup on any machine; nothing installed into Windows. |
| WSL 2 | 2.7 | ✅ P0 | Linux kernel for Docker on Windows | Containers are Linux programs. |
| Local disk storage | — | ✅ P5 | Evidence files (`storage/`, git-ignored; originals read-only) | MinIO's free edition was archived in 2026; `app/storage/local.py` can be swapped for S3-compatible storage later. |
| Git + GitHub | — | ✅ P0 | Version control + backup | github.com/kandiharish/Falcon |
| GitHub Actions | — | 🔜 P12 | Automatic tests on every push | Free for public repos. |

## 4. AI & processing — every model

AI **suggests**, humans **decide**. Every AI output is labelled (Extracted / Detected / Inferred), carries a confidence and links to its source evidence. All models run **locally** — evidence never leaves the machine.

| Capability | Model / tool | Type | Size | Status | Why |
|---|---|---|---|---|---|
| OCR (text in images/scans) | **RapidOCR** (`rapidocr-onnxruntime` 1.4, PP-OCR models on ONNX Runtime) | Neural OCR | ~15 MB, bundled | ✅ P6 | *Replaced Tesseract:* pip-only (no Windows installer), Apache-2.0, offline. Spacing repaired for joined words. |
| PDF text + page rendering for OCR | **pypdfium2** (Chrome's PDF engine) | Parser (no ML) | — | ✅ P6 | *Replaced PyMuPDF* (AGPL licence). Text layer first; pages without text go to OCR. |
| Word documents | **python-docx** | Parser (no ML) | — | ✅ P6 | Paragraphs and tables of `.docx`. |
| Photo metadata (GPS, time, camera) | **Pillow** EXIF reader | Parser (no ML) | — | ✅ P5 | Facts, not guesses → labelled *Extracted*; camera time-zone offset honoured. |
| Video metadata | **PyAV** (FFmpeg bundled in the wheel) | Parser (no ML) | — | ✅ P6 | *Replaced ffprobe:* nothing to install. Duration, codec, resolution, creation time. |
| Names, places, organisations in text | **spaCy 3.8 `en_core_web_sm` 3.8.0** | Named-entity recognition model | ~12 MB | ✅ P6 | Small, fast on CPU. Results are DETECTED (≤0.6 confidence) and filtered: names must be capitalised. Upgradeable to `en_core_web_trf`. |
| Phone numbers, emails, plates, account IDs | **`phonenumbers`** (port of Google libphonenumber) + patterns | Rules (no ML) | — | ✅ P6 | Explainable; numbers normalised to E.164 so the same phone in two files becomes one entity. |
| Structured records (calls, GPS, transactions, plates) | **FALCON CSV extractors** with column aliases | Rules (no ML) | — | ✅ P6 | Rows become EXTRACTED entities and events (0.95; 0.8 when a time has no zone). |
| Text similarity, meaning-based search | **`all-minilm`** (= all-MiniLM-L6-v2) served by **Ollama** | Embedding model (384-dim vectors) | 46 MB | ✅ P10 | *Changed:* served by Ollama instead of sentence-transformers, so no 2 GB PyTorch install; one AI runtime for everything. ~0.2 s per search on CPU. |
| Near-duplicate images | **Own dHash** (difference hash, ~15 lines with Pillow) | Algorithm (no ML) | — | ✅ P10 | *Changed:* `imagehash` needs SciPy (~40 MB); dHash is enough to catch resized/re-saved copies (≤ 10 of 64 bits differ). |
| Natural-language search, Investigation Assistant agent | **Qwen3 8B** (`qwen3:8b`) via **Ollama 0.35** | Large language model: tool calling + JSON-schema output | 5.2 GB (4-bit) | ✅ P10 | Measured on this laptop (CPU only): search ~8 s warm; agent 1–3 min per answer, all citations verified. `qwen3:4b` was tested and rejected: it ignored the answer rules as an agent. Thinking mode off; replies capped at 700 tokens. |
| Correlation scoring | **FALCON correlation engine** (our own Python rules) | Deterministic scoring, no ML | — | ✅ P8 | Same input → same output; every score explained factor by factor. Entity 0.45 · time 0.30 (30 min) · place 0.25 (500 m, haversine). |

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
