# Phase 5 — Evidence: Upload, Integrity, Background Processing

## 1. What we built

```
 Browser ──upload (with progress bar)──► API ──────────────► storage/originals/…  (read-only)
                                          │ sniff real type      ▲
                                          │ SHA-256 while saving │
                                          │ reject duplicates    │
                                          ▼                      │
                                   evidence row + ProcessingJob (queued)
                                          │
              ┌───────────────────────────┘
              ▼
 Worker (separate program) ── claims job ──► Validation → Metadata → Preview
              │                               (progress committed after each step)
              ▼
     evidence: processed / requires review  ──► audit log
              ▲
 Browser polls every 2 s while processing: "72% · Metadata extraction"
```

## 2. Integrity: how FALCON proves a file wasn't changed

```
 upload:   bytes ──SHA-256──► 7d1b4b05…  (stored with the evidence)
 later:    bytes ──SHA-256──► 7d1b4b05…  ✓ match      or   a93f…  ✗ MISMATCH → requires review
```

- Change one byte of a file and the SHA-256 fingerprint changes completely.
- The original is saved once, through a temp file + atomic rename, then made **read-only**.
- It is stored under an ID we generate — never the uploader's file name (so a name like
  `..\..\app\main.py` cannot write anywhere).
- Previews and extracted values are **derived** copies, stored separately.
- Downloading the original is recorded in the audit log (plan §25 "evidence viewed").

## 3. What a file *really* is

```
 holiday.jpg  ──first bytes──►  4D 5A …  =  "MZ" = Windows program  →  rejected
 calls.csv    ──first bytes──►  text, no NUL bytes                  →  text/csv
```

The extension is a label anyone can change; the first bytes ("magic numbers") are not.
The detected type must also fit the chosen evidence type (a CSV is not an "image").

## 4. The job queue inside PostgreSQL

```sql
SELECT … FROM processing_jobs WHERE status = 'queued'
ORDER BY created_at LIMIT 1
FOR UPDATE SKIP LOCKED;   -- lock it; other workers skip locked rows instead of waiting
```

- Several workers can run safely; a test starts two at the same moment and checks no job
  is handed out twice.
- A crashed worker leaves its job "running" without heartbeats → re-queued after 2 minutes
  (failed after 3 attempts).
- A partial index (`WHERE status = 'queued'`) keeps "find the next job" instant.

## 5. Pipeline steps are plugins

```python
STEPS = [
    Step("integrity",      "Validation",          validate_integrity),
    Step("image_metadata", "Metadata extraction", extract_image_metadata, is_image),
    Step("text_metadata",  "Metadata extraction", extract_text_metadata,  is_text),
    Step("image_preview",  "Preview generation",  build_image_preview,    is_image),
]
```

Each step decides from the file's **real content** whether it applies. Phase 6 adds OCR and
entity/event extraction by appending steps — nothing else changes (plan §40).

## 6. Provenance: who said this?

| Field | If the person typed it | If read from the file |
|---|---|---|
| Collected at | `USER ENTERED` | `EXTRACTED` (EXIF DateTimeOriginal) |
| Coordinates | `USER ENTERED` | `EXTRACTED` (EXIF GPS) |

Extracted values only fill **empty** fields — they never overwrite what a person entered.

### Time zones (a classic evidence bug)
EXIF stores the camera's *clock* time with no zone. Newer cameras add `OffsetTimeOriginal`
(e.g. `+05:30`); FALCON uses it. Without it, FALCON stores the time as UTC, says so in the
provenance, and marks the evidence **Requires Review**. All times are stored in UTC and shown
in the viewer's local zone.

## 7. Why these choices

| Choice | Why | Instead of |
|---|---|---|
| Postgres job table | the ProcessingJob entity is the queue; one less service | Celery + Redis |
| Polling every 2 s while busy | simple, reliable, stops when idle | WebSockets (later, if needed) |
| XMLHttpRequest for upload | reports upload progress | fetch (cannot report upload progress) |
| `filetype` (pure Python) | works on Windows without system libraries | python-magic |
| Unique (case, SHA-256) in the DB | duplicates blocked even when two uploads race | checking in Python only |
| Content-based step selection | a `.txt` document gets text processing too | choosing steps by evidence type |

## 8. Problems we hit (and the lesson)

| Problem | Lesson |
|---|---|
| Alembic autogenerate **dropped** the trigram index from P4 | Always read generated migrations. Declare hand-made indexes in the models so tools know about them |
| A test failed only in the full run | Test data from earlier runs leaked in → recreate the test database every run |
| Reprocess returned the *old* job | The ORM session cached the job list; `populate_existing` refreshes it |
| `\b` and `\x00` in Python strings broke files | Escape sequences inside generated code are dangerous; prefer direct edits |
| `uv` "module not found" once | Two `uv` commands touched the environment at the same moment; retry |
| Demo photo showed 02:11 instead of 20:41 | Time zones: EXIF has no zone unless the camera records one |
| Worker loop could die on a DB restart | Long-running workers must catch errors, wait, and continue |

## 9. Improvements for later

- PDF/DOCX text and page counts, video metadata (ffprobe), OCR. *(P6)*
- Investigation time zone; show times in the case's zone. *(P7)*
- Near-duplicate detection (resized photo, re-saved PDF). *(P10)*
- Resumable uploads for multi-GB video; antivirus scan step. *(P11–P12)*
- Push progress to the browser (Server-Sent Events) instead of polling. *(later)*

## 10. Try it yourself

1. `.\dev.ps1` → three windows: backend, **worker**, frontend.
2. Sign in as `r.varma@…`, open CASE-2026-001 → Evidence: 5 demo items.
3. Add evidence: drop any CSV, choose "Vehicle records" → watch it process.
4. Open IMG-001 → note the EXTRACTED labels; Integrity → "Check integrity now".
5. Try uploading the same file again → "already in the investigation as …".
6. Sign in as `a.kumar@…` (Forensic Analyst) → "Mark verified" appears.
7. Reset everything: `cd backend; uv run python -m app.scripts.reset_demo_data --yes`.
