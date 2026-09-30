# Phase 3 — Login, Roles and the Audit Foundation

## 1. What we built

```
 ┌────────────┐   POST /api/auth/login    ┌─────────────────────────┐    ┌──────────────┐
 │ Login page │ ────────────────────────► │ check lockout           │    │ users        │
 │            │   email + password        │ verify Argon2 hash      │◄──►│ user_sessions│
 │            │ ◄──────────────────────── │ create session          │    │ audit_log    │
 └────────────┘   Set-Cookie: falcon_     │ write audit record      │    └──────────────┘
                  session (httpOnly)      └─────────────────────────┘
      │
      ▼ every later request carries the cookie automatically
 ┌──────────────────────────────────────────────────────────────────┐
 │ cookie → session valid? → role has permission? → run the route   │
 │            no: 401              no: 403 + audit "access.denied"  │
 └──────────────────────────────────────────────────────────────────┘
```

- A real **login page** (validation, show/hide password, remember device, forgot-password help).
- **Sessions** in an httpOnly cookie; **sign out** revokes them.
- **6 roles → 12 permissions**, checked by the server on every request.
- Screens and menus adapt to your role.
- **Administration → Users** page.
- **Audit log** records sign-ins, failures, lockouts, sign-outs and denied access — and the
  database itself refuses to edit or delete audit rows.
- **18 automated backend tests** on a separate test database.

## 2. Authentication vs authorization

```
 AUTHENTICATION  = "Who are you?"        → login, password, session cookie   → fails with 401
 AUTHORIZATION   = "What may you do?"    → role → permissions                → fails with 403
```

## 3. How a password is stored (and why)

```
 "my password"  ──Argon2id (slow, salted)──►  $argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>
                                               ↑ this is all the database ever sees
```

- **Hash, not encrypt:** a hash can't be turned back into the password.
- **Salt:** a random value per user, so two identical passwords have different hashes.
- **Slow on purpose:** ~50 ms per guess for us is nothing; for an attacker trying billions of
  guesses from a stolen database, it's years.

## 4. How a session works

```
 Browser cookie:   falcon_session = kJ3x…(random, 256 bits)
 Database row:     token_hash = sha256(kJ3x…) = 9f2c…
```

A stolen database copy contains only hashes — useless as cookies (there's a test for this).

**Cookie flags**

| Flag | Protects against |
|---|---|
| `HttpOnly` | JavaScript (and so XSS attacks) cannot read the cookie |
| `SameSite=Lax` | other websites cannot make your browser send it on POSTs (CSRF) |
| `Secure` (production) | cookie only travels over HTTPS |

**Why sessions and not JWT?** A JWT stays valid until it expires — you can't log someone out
instantly. A session row can be revoked at once (sign out, admin action, stolen laptop).

## 5. Attacks we defend against

| Attack | Defence in FALCON |
|---|---|
| Password guessing | lock for 15 min after 5 failures; every failure audited |
| Account discovery ("does this email exist?") | one message for every failure + equal timing (dummy hash) |
| Stolen database | Argon2 password hashes; only token hashes stored |
| XSS stealing the session | httpOnly cookie |
| CSRF (another site acts as you) | SameSite cookie + required `X-FALCON-Request` header |
| Open redirect after login (`?next=https://evil…`) | only same-site paths accepted |
| Tampering with history | database trigger blocks UPDATE/DELETE/TRUNCATE on audit_log |
| Invented roles | database CHECK constraint on `users.role` |
| Too much power in one account | least privilege: the admin can't read evidence |

## 6. Roles and permissions

| Permission | Officer | Analyst | Evidence An. | Supervisor | Admin |
|---|:-:|:-:|:-:|:-:|:-:|
| investigation:read | ✓ | ✓ | ✓ | ✓ | |
| investigation:write | ✓ | | | ✓ | |
| evidence:read / upload | ✓ | ✓ | ✓ | read | |
| evidence:verify | | ✓ | | ✓ | |
| correlation:review | ✓ | ✓ | | ✓ | |
| report:generate | ✓ | | | ✓ | |
| audit:read | | | | ✓ | ✓ |
| users:read | | | | ✓ | ✓ |
| users:manage / settings | | | | | ✓ |

(Incident Investigator = Officer.) Source of truth: `backend/app/security/permissions.py`.

**The frontend hides; the backend enforces.** Hiding a menu is convenience. Security is the
403 from the server — anyone can call the API directly, so every route checks.

## 7. New files

```
backend/
  alembic.ini, migrations/           database version control
  app/models/                        User, UserSession, AuditLog (tables as Python classes)
  app/security/permissions.py        roles → permissions
  app/security/passwords.py          Argon2id hashing
  app/security/tokens.py             random session tokens + SHA-256
  app/security/dependencies.py       current_session, require_permission (401/403)
  app/security/csrf.py               X-FALCON-Request header check
  app/services/auth_service.py       sign in / sign out / session lookup
  app/services/audit_service.py      the only writer of audit_log
  app/api/auth.py, admin.py          /api/auth/*, /api/admin/users, /api/audit
  app/scripts/seed_demo_users.py     fictional demo accounts (dev only)
  tests/conftest.py, test_auth.py    test database + 18 tests
frontend/src/
  app/auth.tsx                       RequireAuth, RequirePermission
  features/auth/LoginPage.tsx        sign-in screen
  features/admin/UsersPage.tsx       Administration → Users
  services/authService.ts, adminService.ts
```

## 8. Migrations (Alembic) in one picture

```
 change a model (Python)  ──►  alembic revision --autogenerate  ──►  migration file (reviewed!)
                                                                           │
                              alembic upgrade head  ◄──────────────────────┘
                              (applies it to the database, records the version)
```

Autogenerate writes tables and indexes; we added the CHECK constraint and the trigger by hand.
The same migrations build the test database, so tests use the exact real schema.

## 9. Problems we hit (and the lesson)

| Problem | Lesson |
|---|---|
| 14 tests failed: `invalid input for type inet: "testclient"` | Validate data from the outside world before storing it. A real proxy could send odd values too |
| A Windows Python script couldn't open `/c/falcon/...` | Git Bash paths (`/c/`) are not Windows paths; use relative paths |
| Blank login screenshot | It was mid-load; check the accessibility tree before assuming a bug |
| Browser-test tool printed the demo password in its log | Tool logs can leak secrets — use throwaway dev passwords and rotate them |

## 10. Improvements for later

- MFA enrolment and TOTP verification (the data model is ready). *(P11)*
- Session list with "sign out other devices"; idle timeout. *(P11)*
- User management: create, deactivate, change role — each change audited with before/after. *(P11)*
- Audit Logs page with filters; hash-chained audit rows for tamper evidence. *(P11)*
- Rate limiting by IP address, not only per account. *(P11)*
- Per-investigation membership (data isolation: see only your team's cases). *(P4)*

## 11. Try it yourself

1. Open http://localhost:5190 → you are sent to the login page.
2. Open **Development demo accounts**, pick `a.kumar@…`, enter the `DEMO_PASSWORD` from `.env`.
3. Visit http://localhost:5190/admin → *Access restricted*.
4. Sign out, sign in as `admin@…` → only Overview, Audit Logs, Administration; open Users.
5. Try a wrong password 5 times for `m.das@…` → locked for 15 minutes (re-run the seed script to unlock).
6. http://localhost:8010/api/docs → see the new `/api/auth` endpoints.
