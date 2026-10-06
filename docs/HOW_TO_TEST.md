# How to test FALCON, step by step (beginner's guide)

Every "Expected" below was checked on the real application on 6 Oct 2026, against freshly
reset demo data. All names, phones, plates and places are **fictional**.

## 0. What is FALCON, in one minute

Detectives get evidence in pieces: a CCTV video, phone records, GPS history, card payments,
a photo, a scanned witness statement. Each piece lives in its own file, and connecting them by
hand is slow and error-prone.

FALCON is a **detective's corkboard that explains every string**:

```
 1 STORE     upload evidence → SHA-256 fingerprint → original kept read-only
 2 EXTRACT   read each file → people, phones, vehicles, places (entities) + things that happened (events)
 3 CONNECT   compare everything → "these two items may be related, because…" (correlations, graph)
 4 EXPLAIN   timeline, map, reports, plain-language questions to a local AI — with evidence IDs
```

It **never decides guilt**. It shows possible links, with reasons, and humans confirm or reject.

How the pieces fit:

```
 Browser (React)  ──/api──►  FastAPI (Python)  ──►  PostgreSQL (data, map, AI vectors)
                                  │                       ▲
                                  ├── worker (reads files, finds entities, correlates)
                                  └── Ollama (local AI on YOUR PC; nothing leaves it)
```

## 1. Start it

In PowerShell:
```powershell
cd C:\falcon
.\dev.ps1
```
**Expected:** "FALCON is starting: http://localhost:5190", and three new windows (backend,
worker, frontend).

Check the API is healthy by opening http://localhost:8010/api/health.
**Expected:** `{"status":"ok","database":{"connected":true,…"postgis":"3.6.4","vector":"0.8.x"…}}`

Want a clean start, exactly like this guide? (This deletes only demo data.)
```powershell
cd C:\falcon\backend
uv run python -m app.scripts.reset_demo_data --yes
```

## 2. The demo accounts

Every demo account uses the same password, which is stored in your own `.env` file (it's never
in the code or on GitHub). To see it:
```powershell
Select-String -Path C:\falcon\.env -Pattern DEMO_PASSWORD
```

| Email | Role | What it may do (why it exists) |
|---|---|---|
| `r.varma@falcon.example` | Investigation Officer | Leads CASE-2026-001: uploads, tasks, **generates reports** |
| `a.kumar@falcon.example` | Forensic Analyst | Analyses: **reviews** entities, events and correlations |
| `m.das@falcon.example` | Evidence Analyst | Uploads and reads evidence only (no reviewing) |
| `k.iyer@falcon.example` | Supervisor | Sees **all** cases, reads the audit log |
| `a.menon@falcon.example` | Incident Investigator | Like an officer |
| `admin@falcon.example` | System Administrator | Manages users; **cannot read evidence** (least privilege) |

The login page also has a "Development demo accounts" list you can click to fill in the email.

## 3. The walkthrough

### Step 1: Sign in and see the command center
Open http://localhost:5190, sign in as **a.kumar**, and choose **CASE-2026-001 Riverside Warehouse
Break-in** in the top bar.

**Expected (Overview):**

| Tile | Value | Meaning |
|---|---|---|
| Active investigations | 2 | Cases A. Kumar works on that are active |
| Evidence items | 8 | Files in those cases |
| Being processed | 0 | The worker has finished |
| Entities identified | 12 | People, phones, vehicles… |
| Events identified | 19 | Things that happened |
| Potential relationships | 12 | Correlations |
| Requires review | 43 | Items no human has checked yet |
| Open tasks | 4 | Team work not finished |

"Needs attention" lists **overdue tasks** (the demo's due dates are fixed at 1–6 Oct 2026, so
how many are overdue depends on today's date).

**How it works:** every number is a live `COUNT` in the database, over only the cases you are
on a team for. Another officer would see different numbers.

### Step 2: Evidence and integrity
Go to **Evidence**.
**Expected:** 8 items, all "Processed": CALL-001, CCTV-001, DOC-001, GPS-001, IMG-001,
TXN-001, VEH-001, WIT-001.

Open **CCTV-001** and then the **Integrity** tab.
**Expected:** a 64-character SHA-256 fingerprint, and "verified".

**Why:** a fingerprint changes completely if even one byte of the file changes. Keeping the
original untouched and fingerprinted is how evidence stays trustworthy (chain of custody).

### Step 3: Upload your own evidence (and see FALCON connect it)
Make a text file `neighbour_note.txt` containing:
```
Neighbour statement, 28 Sept 2026.
Around 20:40 I saw a grey van, plate ZZ99 ZZ 0001, near the warehouse rear door.
The driver was on the phone; later I learned the number was +1 202-555-0101.
```
Sign in as **r.varma** (a.kumar can upload too). On **Evidence → Upload**, choose the file, set
the type to *Witness statement*, and add the description "Neighbour's note about the van".

**Expected:**
- It becomes **WIT-002**: Uploaded → Processing → Processed (a few seconds).
- **Extracted information** tab: **PH001** `+1 202-555-0101` (Detected, 0.90) and **V001**
  `ZZ99 ZZ 0001` (Detected, 0.70).
- **Correlations** tab (after a few seconds): 5 new **Low** relationships, e.g. with CALL-001
  and DOC-001 (both contain PH001) and with CCTV-001 and VEH-001 (both contain the van).

Now upload the **same file again**.
**Expected:** it's refused: *"This exact file is already in the investigation as WIT-002
(identical SHA-256 fingerprint)."*

**How it works:**
```
 upload → fingerprint → stored read-only → job queued → worker reads the text
 → finds valid phone numbers and plates → links to existing entities (same number = same PH001)
 → asks for a correlation refresh → worker compares pairs → new correlations appear
```
Why "Detected" and not "Extracted"? It was found in free text, which is less certain than a
structured CSV column, so confidence is lower and it needs review.

### Step 4: Entities
**Entities** lists **12**: A001 card account, D001 device, ORG001–003 shops/company, P001 Ravi
Kumar, P002 Anita Shah, PH001–PH004 phones, V001 the van.

Open **V001**.
**Expected:** it appears in CCTV-001, DOC-001, VEH-001 and WIT-001, and in 3 events (seen by
the rear-door camera, GATE-02 and DOCKROAD-01).

### Step 5: Timeline and map
Open **Timeline**. **Expected:** 19 events from **28 Sep 20:18 to 29 Sep 11:00**, in India time
(the case's time zone). The story:

| Time | What | From |
|---|---|---|
| 20:18–20:58 | Device D001 moves (GPS) | GPS-001 |
| 20:30 | Person forces the rear door | CCTV-001 |
| 20:33 | PH001 calls PH002 | CALL-001 |
| 20:36:50 | Grey van passes the rear-door camera | CCTV-001 |
| 20:37:00 | Van ZZ99 ZZ 0001 at GATE-02 | VEH-001 |
| 20:45 | Card A-4421-0098 pays a fuel station | TXN-001 |
| 20:52 | Van at DOCKROAD-01 | VEH-001 |
| 21:05 | PH001 calls PH003 | CALL-001 |
| 22:10 / next day 11:00 | Incident report / witness statement | DOC-001 / WIT-001 |

Switch to **Map** and pick entity **D001**: the device's path appears as a dashed line, and the
▶ button replays it.

Why the case's time zone? So "20:30" means the same moment for everyone, wherever they sit.

### Step 6: Correlations, the explained links
Open **Correlations**. **Expected:** 12, strongest first: **1 High, 4 Medium, 7 Low**.

Open **COR-001: CCTV-001 ⟷ VEH-001, High 0.95**. Under "Why this relationship exists":

| Factor | Score × weight = | Reason |
|---|---|---|
| Shared entity | 0.95 × 0.45 = 0.43 | Both contain V001 (ZZ99 ZZ 0001) |
| Close in time | 0.99 × 0.30 = 0.30 | 20:36:50 vs 20:37:00: 10 seconds apart |
| Close in place | 0.91 × 0.25 = 0.23 | 44 metres apart |
| **Score** | **0.95** | High ≥ 0.75 · Medium ≥ 0.50 · Low below |

Write a note and click **Confirm relationship**.
**Expected:** "Analyst Confirmed by A. Kumar", with the time. Rejecting needs a written reason.

Why fixed rules instead of machine learning? The same input always gives the same score, and
every number can be explained, for example in court.

### Step 7: Relationship graph
Open **Relationship Graph**, type `V001` and press Enter. The van is highlighted with its links.
Click a link to see **"Why this relationship exists"**. The **List** tab shows the same links as
a table, for screen readers and phones.

### Step 8: Ask in plain words (local AI)
Open **Analysis**. The page should say "Local AI ready · qwen3:8b" (Ollama must be running).
- **Search in plain words:** `Show all communications involving PH001`
  **Expected:** "Showing events involving PH001 of type call made…", then **E011, E012, E013**.
  The first search after starting can take about a minute; later ones about 10 s.
- **Investigation Assistant:** `Who did phone PH001 call that evening?`
  **Expected (1–3 minutes):** live steps (e.g. "Searched events → 3 events"), then an answer
  such as "PH001 called +1 202-555-0102 at 20:33 [E011] … and +1 202-555-0177 at 21:05
  [E013]", with clickable IDs and "All cited IDs were returned by FALCON lookups".

How it works: the AI only fills in a *search form*; FALCON's own code runs the search. The
assistant can only use read-only tools, as you, and every ID it cites is checked.

### Step 9: Tasks and notifications
**Tasks**, *This investigation*. **Expected:** To Do: T-003, T-004 · In Progress: T-001 · Review:
T-002 (review COR-001) · Completed: T-005. Move a card with its drop-down. The bell (top right)
shows a.kumar's notifications, such as tasks assigned to them.

### Step 10: A report you can trust
Sign in as **r.varma**, then **Reports → Generate report → Generate**.
**Expected:** RPT-001 opens with "**Fingerprint matches: unaltered since generation**" and
three parts: **A Observed evidence**, **B Analytical interpretation**, **C Record**
(including limitations FALCON wrote itself). Click **Print / save as PDF** to get a clean
black-on-white page.

### Step 11: Security, try to break the rules
| Try this | Expected |
|---|---|
| Sign in as **m.das**, open COR-001 | No Confirm/Reject: "Only reviewers on this investigation's team can confirm or reject correlations." |
| Sign in as **admin** | "System overview": no Evidence menu (administrators manage people, not cases). Audit Logs shows every action, e.g. your confirmation of COR-001 |
| Sign out, then open http://localhost:5190/evidence | Sent back to the sign-in page |
| Wrong password 5 times for **a.menon** | Account locked for 15 minutes (admin can unlock: Administration → ⋯ → Unlock) |
| More than 10 sign-in attempts in a minute | "Too many attempts. Wait N seconds" |
| Your name → **Account security → Set up** | A QR code for any authenticator app; after that, sign-in needs a 6-digit code |

## 4. The automated checks
```powershell
cd C:\falcon\backend;  uv run pytest -q     # Expected: 134 passed (2–7 minutes)
cd C:\falcon\frontend; npm test             # Expected: 9 passed
cd C:\falcon\frontend; npm run e2e          # Expected: 8 passed, 1 skipped (9 after you make a report)
```
The same checks, plus security scans and the production build, run on GitHub on every push
(green badge in the README).

## 5. Beginner's questions

**Why a web app, not Excel or a shared drive?** Excel can't fingerprint files, enforce who may
see which case, keep an audit log nobody can edit, or explain links between 8 kinds of files.

**Why does it say "potential relationship, not proof"?** Two things close in time and place may
be a coincidence. FALCON shows the reasons; a human decides.

**Why a local AI (Ollama) instead of ChatGPT?** Evidence must not leave the building. It's
also free. The cost: it's slower on a laptop without a graphics card.

**Why PostgreSQL for everything?** One database handles tables, maps (PostGIS), AI vectors
(pgvector) and fuzzy text search (pg_trgm). Fewer systems means fewer things to break or keep
in sync.

**Why React + FastAPI?** React is the most widely used UI library, with ready parts for tables,
maps and graphs. FastAPI is quick to write, checks every input, and Python is where the
OCR/NLP/AI tools are.

**Why can't anyone edit the audit log?** A database trigger rejects changes, so even a bug, or
an administrator, can't rewrite history.

**Why session cookies instead of tokens in the browser?** The cookie is httpOnly, so page
scripts can't read it. That's safer against stolen sessions.

**Why a worker process?** Reading a PDF with OCR takes seconds; you shouldn't wait for it. The
upload returns at once, and the worker does the slow part in the background.
