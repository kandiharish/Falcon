# Phase 11: Team work, reports and account security

Built in five commits, each tested and pushed on its own:

```
 P11a  Tasks + notifications          P11d  Audit log screen + user management
 P11b  Reports with fingerprints      P11e  MFA (authenticator codes) + your sessions
 P11c  Command-center dashboard + global search
```

## 1. Tasks and notifications

```
 To Do ──► In Progress ──► Review ──► Completed        (board, one column per status)
 a task: T-001 · title · priority · due date · assignee (team only) · related evidence
```

- Every change is audited with only the fields that changed, before and after.
- **Notifications avoid overload, by design:**
  - you are never notified about your own action;
  - processing results go to the person who uploaded, new correlations to the case lead only;
  - a repeat of an unread notification updates it instead of piling up.
- The bell asks for new notifications every 30 seconds (polling). It is simple and robust, and
  notifications are not urgent to the second. Live pushing (WebSockets) is a later improvement.

Bugs the tests caught:
- Unassigning a task kept showing the old person. The column changed, but the already-loaded
  relationship object did not. The fix is to set the relationship itself.
- After that fix, the audit diff missed the change until the database was **flushed**. The
  lesson: know when your ORM actually writes.

## 2. Reports: frozen, fingerprinted snapshots

```
 case data ──► JSON snapshot ──► canonical bytes (sorted keys) ──► SHA-256
   Part A  OBSERVED EVIDENCE           evidence, sources, entities, timeline, integrity
   Part B  ANALYTICAL INTERPRETATION   correlations, relationships, analyst notes
   Part C  RECORD                      limitations (automatic + written), audit summary, fingerprint
```

- A report is **never recalculated**: what was shared stays exactly what it was.
- Every view re-computes the fingerprint. If anyone edits the stored report (even directly in
  the database), the page shows *"Fingerprint MISMATCH"*. There is a test that does exactly
  that.
- **Limitations are written automatically**: unreviewed items, unverified integrity,
  low-confidence readings, events without a time, open tasks. A report that hides its weak
  points is dangerous.
- Print uses CSS `@media print`: navigation hidden, black on white, "Save as PDF" from the
  browser. No PDF library is needed. JSON export gives the exact fingerprinted bytes.

## 3. Dashboard and global search

- Every number is a `COUNT` over the cases **you** can see (same visibility rule as everywhere),
  and every tile links to where the records are.
- Event activity is **hourly** when events span up to 3 days (a single night reads well), otherwise
  daily: let the data choose the scale.
- Charts are plain HTML bars. Each one also says its numbers in words for screen readers.
- Global search (Ctrl+K): one indexed query per kind of record, at most 5 results each, only
  in visible cases. Phone numbers match with any spacing ("202 555 0102").
- Typing is **debounced**: the request waits until you pause for 250 ms, so there is no request
  per keystroke.

## 4. Audit log screen and user management

- Filter by area, person, object and dates; open an entry to see before and after; export CSV.
  **The export itself is audited.**
- Administrators manage accounts, with safety rules:
  - a role change, deactivation or password reset **ends that user's sessions at once**;
  - you cannot deactivate or demote yourself;
  - passwords need at least 12 characters;
  - the temporary password is never written to the audit log.
- Least privilege still holds: administrators manage people but still cannot read evidence.

## 5. Multi-factor authentication: how authenticator apps work

```
 secret (20 random bytes) ──shared once by QR──► phone
 every 30 s:  step = time ÷ 30   →   HMAC-SHA1(secret, step)   →   6 digits
 phone and server compute the same code without talking to each other
```

We wrote TOTP ourselves (RFC 6238, about 20 lines) and test it against the **official test
vectors**. If it matches the RFC, it matches every authenticator app.

| Threat | Defence |
|---|---|
| Stolen password | Sign-in needs a code from the phone too |
| Code seen over a shoulder | Each 30-second code works once (last used step is stored) |
| Guessing codes | Wrong codes count towards the same 5-try lockout as passwords |
| Database leak | Secrets encrypted with AES-256-GCM; the key lives only in `.env` |
| Lost phone | 8 one-time recovery codes (only their hashes stored); admin "Reset MFA" as a last resort |
| Hijacked session turning MFA off | Turning it off needs the password **and** a current code |
| Account details leaking before code | After the password, the session is "pending": it can only submit the code, and the login reply reveals nothing about the account |

Also new: **Where you are signed in**. See every active session and sign out the ones you do not
recognise.

## 6. Problems we hit (and the lesson)

| Problem | Lesson |
|---|---|
| QR code image broken | `svg_inline` omits the SVG namespace an `<img>` needs; use a full `data:` URI |
| Notification click did not open the task when already on the page | Make the URL the source of truth, not a copy in state |
| Evidence list empty in the task form | The API caps pages at 100; a request for 200 was rejected. Show "could not load", never a misleading "empty" |
| A migration with a required JSON column failed on existing users | New required columns need a database default |
| Breadcrumb "Not found" on the account page | Pages outside the menu need their own label |

## 7. Improvements for later

- Push notifications (WebSockets) and email digests. *(later)*
- Report templates per case type; digital signature of the fingerprint. *(later)*
- WebAuthn / passkeys as a second factor (phishing-resistant). *(P12+)*
- Require MFA for certain roles (policy). *(P12)*

## 8. Try it yourself

1. As `r.varma@…` open **Tasks**, move T-003 to In Progress, then assign it to A. Kumar.
   A. Kumar's bell shows it.
2. **Reports → Generate**, then open the report, **Print / save as PDF**, and **Download JSON**.
3. **Overview**: click "Requires review", or the overdue alert.
4. Press **Ctrl+K** and type `202 555`.
5. As `admin@…` open **Audit logs** and filter *User management*; then **Administration** → ⋯ menu.
6. Your name → **Account security** → **Set up**. Scan the QR code with your phone, then sign
   out and back in.
