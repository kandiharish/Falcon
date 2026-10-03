# Phase 12: Production-ready

```
 P12a  Security hardening    headers · rate limits · fail-closed production checks · scanners
 P12b  Tests + CI            unit tests · browser tests · accessibility · GitHub Actions
 P12c  Performance           a 6,000-event case · measure · profile · fix
 P12d  Deployment            production containers · HTTPS · backups · $0 hosting guide
```

## 1. Security hardening

| Defence | What it stops |
|---|---|
| Security headers on every API reply (`nosniff`, frame denial, `default-src 'none'`, `no-referrer`, `no-store`, HSTS) | MIME confusion, clickjacking, leaking case IDs in referrers, cached evidence data |
| Rate limits (sliding window): sign-in and MFA 10/min per address; AI and uploads per session | Password and code guessing; one user exhausting the CPU |
| **Fail closed**: production refuses to start with insecure cookies, a short key, a weak DB password or demo accounts | The classic "forgot a dev setting in production" |
| Bandit, pip-audit, npm audit | Risky code patterns and known-vulnerable packages |

**What the scanners found:**
- `urlopen` also reads `file://` URLs, so a mistyped `OLLAMA_URL` could have read local
  files. Fix: only `http(s)` is allowed.
- `assert` statements disappear in optimised Python. Fix: explicit checks.
- Six npm advisories, all inside a **developer-only** tool. Fix: move build tools to devDependencies,
  and record the accepted risk.

## 2. Tests and CI: three layers

```
 unit (Vitest)            pure helpers               9 tests, 2 s      every save
 API (pytest)             services + endpoints + DB  135 tests, ~2 min every push
 end-to-end (Playwright)  a real browser, real data  9 tests, ~1 min  every push (CI)
 + accessibility (axe)    WCAG 2.1 AA, light + dark
```

**GitHub Actions** rebuilds everything on a clean machine for every push, and it found real
problems on its first day:
1. **The database image could no longer be built.** Its Debian release was retired and the
   package server dropped it. It only worked on our PC because of a weeks-old cache. Fix:
   start from the pgvector image and add PostGIS. Upgrading an existing database also needed
   `REINDEX` plus `REFRESH COLLATION VERSION`, because the system's text-sorting rules changed
   (glibc 2.31 → 2.36).
2. **`backend/app/storage` had never been committed.** The `.gitignore` line `storage/` was
   meant for the evidence folder, but it also matched this code folder. Every clone since
   Phase 5 was broken. Fix: `/storage/`, anchored to the repository root.
3. **Ruff guessed differently on Linux** which imports are "ours". Fix: say it explicitly.

**What axe found:** 18 text elements below the 4.5:1 contrast ratio. Status colours were tuned
for white, but badges sit on a tinted background. Fix: re-tune the tokens.

**Our rate limiter blocked our own tests** (the 6th sign-in in a minute). That's correct behaviour.
The tests now sign in once and reuse the session, which is also faster.

## 3. Performance: measure, then fix

The method: build a **big fictional case** (60 evidence items, 1,200 entities, 6,000 events),
**time** every endpoint, **profile** the slow ones, fix what the profile shows, then measure again.

| What | Before | After | How |
|---|---|---|---|
| Correlation run | 38.3 s | 1.9 s | COR numbers reserved in **one** statement (was 1,770 round trips: 11 s); sweep line on precomputed numbers (the `timed[i+1:]` slice copied the list for every event); integers instead of UUIDs as keys |
| Reviewing an entity | seconds (re-correlation inside the request) | ~140 ms | Requests only *ask* for a refresh; the worker runs it in the background and merges bursts |
| Relationship graph | 3.0 s / 2.2 MB | 1.35 s / 0.58 MB | Choose the best-connected nodes from cheap counts *before* building links; cap links at 1,200 by importance; select plain columns |
| Every list endpoint | — | < 500 ms | Already fine: the indexes work |

The lessons:
- **Measure before optimising.** The first guess ("the engine maths") was only half the story;
  the profiler showed 11 s of plain database round trips.
- **Round trips beat clever code.** One statement instead of 1,770 was the biggest single win.
- **Do slow work outside the request.** People should never wait for a recalculation they
  didn't ask for.

## 4. Deployment

```
 Internet ─HTTPS─► web (Caddy: certificates, headers, the app) ─/api─► api ─┐
                                                                    worker ─┼─► db (internal only)
                                                                   migrate ─┘   ollama (optional)
```

- **One backend image** runs the API, the worker and the migrations. It runs as a non-root user,
  and its dependencies are pinned by `uv.lock`.
- **`migrate` runs once** before the API and worker start, so a new version upgrades the
  database automatically.
- **Caddy** obtains and renews HTTPS certificates by itself. It sets the web app's
  Content-Security-Policy (only our own scripts, plus the OpenStreetMap tiles) and leaves the
  API's stricter rules alone.
- **The database has no published port.** Only the other containers can reach it.
- **Backups** (`deploy/backup.sh`) take the database **and** the evidence files together, with
  checksums.
- **The first administrator** is created with `create_admin` (production has no demo accounts).

Verified on this PC: HTTPS, security headers, the HTTP→HTTPS redirect, hidden API docs, a
Secure+HttpOnly session cookie, every page working under the strict policy, and a refusal to
start with unsafe settings.

The $0 hosting guide (Oracle Cloud Always Free, plus DuckDNS) is in [../DEPLOY.md](../DEPLOY.md).

## 5. Improvements for later

- Cache the graph per case until its data changes. Use Redis for rate limits across several API processes.
- Push the images to a registry and deploy from CI (continuous deployment).
- Evidence storage on S3-compatible object storage with encryption at rest.
- Monitoring: health checks with alerts, error tracking, log shipping.
