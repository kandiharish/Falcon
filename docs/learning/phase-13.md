# Phase 13: From viewer to investigator's assistant

## 1. What we built

```
 P13a  UI polish        metric strip · leads first · timeline opens on the busy period
                        readable graph · RESTRICTED banner · one date format
 P13b  Telangana case   CASE-2026-005 KPHB Colony chain snatching (8 generated evidence items)
                        gazetteer: JNTU is a place, BNS is a law
 P13c  Unique features  insights engine ──▶ clock drift · route gaps · who-is-this · other cases
                        documents ──▶ Section 63 certificate · BNSS 94 letters · court bundle
                        QR evidence labels · incident replay with clock correction
```

## 2. The insights engine (the "what next?" brain)

```
 case records ──▶ fixed rules ──▶ suggestion + reasons + records + the request that answers it
```

| Rule | What it notices | Why it matters |
|---|---|---|
| Clock drift | The same bike, same spot: ANPR says 19:42:15, shop CCTV says 19:44:12 | CCTV clocks are often wrong; a wrong clock can break an alibi or a timeline |
| Route gap | The bike unseen for 61 min over 2.4 km | CCTV is overwritten in 15–30 days: ask now |
| Who is this? | Numbers in call records, UPI IDs, IMEIs with no known owner | Each needs a formal request to an operator or bank |
| Other cases | The same plate in a theft case | Serial offenders show up across cases |
| Waiting leads | High relationships nobody reviewed | Keeps humans in charge |

Why rules, not AI? The same reasons as correlation: explainable in court, same answer every time.

**Hit / no-hit privacy.** A user sees the other case's name only if they are on its team.
Otherwise FALCON says "1 other investigation you cannot open: ask a supervisor". This is how
police databases share leads without leaking other teams' work.

## 3. Court-ready documents

```
 evidence record (hash, source, custody) ──▶ template ──▶ DRAFT ──▶ officer checks & signs
```

- **Section 63, Bharatiya Sakshya Adhiniyam 2023** (it replaced Section 65B of the Evidence Act
  in July 2024). Courts need a certificate with every electronic record, stating its HASH.
  FALCON already has the SHA-256, so it pre-fills Parts A and B and leaves the rest blank.
- **Section 94, Bharatiya Nagarik Suraksha Sanhita 2023** (formerly Section 91 CrPC): the
  legal basis for asking operators and banks for records. The letter's period comes from the
  case's own records (3 days before the first sighting, 1 day after the last).
- **Court bundle**: originals + `SHA256SUMS.txt`. Anyone can run `sha256sum -c` and verify the
  files **without trusting FALCON**. That independence is the point.

FALCON never signs. Every draft says DRAFT, and every draft and export is in the audit log.

## 4. Replay with clock correction

```
 played time = recorded time − known clock error (CCTV-001: −117 s)
```

The replay only adjusts what it *shows*. The stored times never change, because changing
evidence would destroy its value.

## 5. Problems we hit (and the lesson)

| Problem | Lesson |
|---|---|
| spaCy read "JNTU" as a person, "BNS" as a company | General models lack local knowledge: add a gazetteer before the model |
| The worker kept running old parser code | Long-running processes need a restart after code changes |
| The labels page asked for 200 items; the API allows 100 | Read the API's limits; one wrong number broke two screens |
| Serif digits made a hash's `0` look like `o` | Hashes need lining numerals or a monospace font |
| Chromium lists `Asia/Calcutta`, not `Asia/Kolkata` | Always include the stored value in a picker's options |
| The dashboard made 39 database trips | Combine counts into one query; measure before guessing |

## 6. Try it yourself

1. Sign in as `r.varma@…` and open **CASE-2026-005**. Read *FALCON suggests*.
2. Click **Draft CCTV request**, then print it.
3. Download the **Court bundle**, unzip it, run `sha256sum -c SHA256SUMS.txt`.
4. **Replay the incident**: untick and tick the clock correction and watch CCTV-001 move by 2 minutes.
5. Run `uv run python -m app.scripts.check_aims` and read AIM 8.
