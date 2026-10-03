# FALCON security overview

What protects FALCON, where it lives in the code, and how to check it yourself.

## Layers

| Layer | What | Where |
|---|---|---|
| Identity | Argon2id passwords (12+ chars), lockout after 5 failures, MFA (TOTP, encrypted secrets, recovery codes) | `services/auth_service.py`, `services/mfa_service.py`, `security/totp.py`, `security/crypto.py` |
| Sessions | Random 256-bit token in an httpOnly, SameSite=Lax, Secure (production) cookie; only its hash is stored; expiry; "where you are signed in" | `security/tokens.py`, `api/auth.py` |
| CSRF | SameSite cookie + required `X-FALCON-Request` header on every change | `security/csrf.py` |
| Authorization | Role → permissions in code; case membership checked in every service; hidden cases return 404 | `security/permissions.py`, services |
| Abuse limits | Sign-in and MFA 10/min per address; AI assistant 6/min, AI search 20/min, uploads 30/min per session | `security/rate_limit.py` |
| Browser hardening | `nosniff`, `X-Frame-Options: DENY`, strict CSP on API replies, `no-referrer`, Permissions-Policy, `no-store`, HSTS behind HTTPS; the web app's CSP in `deploy/Caddyfile` | `security/headers.py` |
| Evidence integrity | SHA-256 on upload, read-only originals, re-verification, fingerprinted reports | `services/evidence_service.py`, `services/report_service.py` |
| Accountability | Append-only audit log (a database trigger refuses changes), access-denied attempts logged, exports audited | `services/audit_service.py`, migrations |
| AI safety | Local models only; read-only tools as the user; citations checked; evidence text treated as data | `ai/` |
| Configuration | Secrets only in the environment; production refuses to start with unsafe settings | `core/production.py` |

## Checks to run

```sh
cd backend
uv run pytest -q                                              # 130+ tests incl. security tests
uvx bandit -q -r app -x app/scripts                           # static analysis of our Python
uv run --with pip-audit pip-audit --skip-editable             # known vulnerabilities in packages
cd ../frontend
npm audit --omit=dev                                          # packages that ship to browsers
```

Last run (P12): Bandit 0 findings · pip-audit 0 known vulnerabilities · npm (shipped) 0.

**Accepted risk:** `npm audit` (including dev tools) reports `braces` via the `shadcn` command-line
tool. It runs only on a developer's machine when adding UI components, never in the browser or on
the server; the only offered "fix" downgrades the tool. Re-check when shadcn updates.

## Reporting a problem

This is a learning project with fictional data. If you find a security issue, open a GitHub issue
without exploit details, or contact the maintainer privately.
