# Phase 6 — Extraction: Entities and Events ("EXTRACT")

## 1. What we built

```
 Evidence ──► processing pipeline (worker)
   CSV records ──► structured extractor ─┐
   PDF / DOCX / TXT ──► text ──┐         │
   scanned page ──► OCR ───────┴► NLP ───┼──► ExtractionSink ──► entities  P001 PH001 V001 …
   video ──► metadata (PyAV) ────────────┤        (normalise,      mentions (where + how + how sure)
   photo / video / document time ────────┘         merge)          events   E001 call made 20:33 …
                                                                    participants (caller, vehicle …)
 Analyst ──► "Record observation" on CCTV ──► USER ENTERED event (never touched by re-processing)
 Analyst ──► Confirm / Reject  ──► review status + audit log
```

Screens: **Entities**, **entity profile**, **Events** (by day), and the evidence tab
**Extracted information** — the chain Evidence → Extracted information → Entity → Event (plan §12).

## 2. Entity resolution: how files get connected

```
 CALL-001 row 2:  "+1-202-555-0101"      ─┐ normalise → +12025550101 ─┐
 DOC-001 text:    "+1 202-555-0101"      ─┘                            ├─► PH001 (2 evidence items)
 VEH-001 line 2:  "ZZ99 ZZ 0001"         ─┐ normalise → ZZ99ZZ0001  ───┤
 DOC-001 text:    "ZZ99 ZZ 0001"          │                            ├─► V001 (4 evidence items)
 WIT-001 OCR:     "ZZ99ZZ0001"            │                            │
 CCTV-001 analyst:"ZZ99 ZZ 0001"         ─┘                            ┘
```
The database enforces "one entity per (case, type, normalised key)", so the merge is guaranteed
even when two workers process two files of the same case at the same moment (savepoint + retry).

## 3. Provenance on every fact

| Source | Label | Confidence | Example |
|---|---|---|---|
| A record row that states it | EXTRACTED | 0.95 (0.8 if the time has no zone) | call in CALL-001 line 2 |
| A pattern in text (phone, plate, email) | DETECTED | 0.9 / 0.7 × OCR confidence | plate in DOC-001 chars 324–336 |
| A language model (names, organisations, places) | DETECTED | ≤ 0.6 | "Ravi Kumar" in DOC-001 |
| An analyst | USER ENTERED | 1.0 | "person forces rear door" on CCTV-001 |

Each mention keeps the **context** ("…registration [ZZ99 ZZ 0001] leaving at 20:37…"), the
**extractor** name and the **exact place** in the file. Everything starts as *Requires Review*.

## 4. Four kinds of extractor

1. **Structured (CSV)** — call records, GPS, transactions, vehicle sightings. Column names vary
   between providers, so each type accepts aliases (`caller` = `from` = `a_number` …). If the
   needed columns are missing, FALCON says so instead of guessing.
2. **Text** — `.txt`, PDF text layer (pdfium), DOCX; pages without text → **OCR**.
3. **NLP** — `phonenumbers` (Google's rules), patterns for emails/plates, spaCy for names.
4. **Media** — photo/video/document times become *photo taken / video recorded / document dated* events.

## 5. Re-processing is safe

```
 clear automatic results of THIS evidence (events + mentions; never user-entered ones)
 → extract again (entities found again keep their number: P001 stays P001)
 → delete automatic entities nothing refers to any more
```

## 6. Why these choices

| Choice | Why | Instead of |
|---|---|---|
| RapidOCR | pip-only, offline, Apache-2.0, 97–99% on clean text | Tesseract (separate Windows installer) |
| pypdfium2 | permissive licence, renders pages for OCR | PyMuPDF (AGPL) |
| PyAV | FFmpeg inside the Python package | ffprobe (separate install) |
| Rules for phones/plates | exact and explainable | asking a model |
| spaCy small model + filters | fast on CPU; low confidence + review makes its mistakes harmless | large models (slow) or no names at all |
| No face recognition | ethics (plan §52); analysts record observations instead | automatic face matching |
| Sink as the only writer | one place for normalising, merging, provenance | every extractor writing to the DB |

## 7. Problems we hit (and the lesson)

| Problem | Lesson |
|---|---|
| OCR dropped spaces ("AnitaShah", "wasZZ99ZZ0001") | Real OCR output is messy: repair what is safe (`aB` joins, punctuation), make patterns tolerant |
| spaCy called "grey van" a PERSON | Small models make mistakes: filter (names are capitalised) and keep confidence low |
| A name ran onto the next line ("Anita Shah\nDate…") | Trim model spans at line ends instead of discarding them |
| Re-processing renumbered entities (P001 → P003) | Delete orphans *after* re-extraction so found-again entities keep their ID |
| Python patch scripts broke on `\d`, `\b`, `\x00` | Never generate code through escaped strings; edit files directly |
| Importing a pytest fixture from another test file | Shared fixtures belong in `conftest.py`, helpers in `tests/helpers.py` |

## 8. Improvements for later

- English-only OCR recognition model for better word spacing on long lines. *(P11)*
- Transformer NER (`en_core_web_trf`) as an option on stronger machines. *(P10)*
- Stable event numbers across re-processing. *(P8 — correlations will refer to events)*
- More record formats: messages (SMS/WhatsApp exports), mobile extraction reports (XML). *(P11)*
- Entity merge/split by analysts ("P002 and P007 are the same person"). *(P8)*

## 9. Try it yourself

1. Sign in as `a.kumar@…`, open CASE-2026-001 → **Entities**: V001 appears in 4 evidence items.
2. Open V001 → see each mention's context and the three events.
3. **Events** → filter by entity PH001 → the calls.
4. Evidence → WIT-001 → **Preview**: OCR text with its confidence.
5. Evidence → CCTV-001 → **Extracted information** → *Record observation*.
6. Confirm or reject an event; check the case **Activity** / audit.
