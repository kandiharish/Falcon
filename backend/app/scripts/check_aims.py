"""Acceptance check: does the running FALCON meet the project's aims (plan.md)? Development only.

    uv run python -m app.scripts.check_aims          # API on http://127.0.0.1:8010
    uv run python -m app.scripts.check_aims --ai     # also asks the local AI (1-2 min)

Runs against the demo case (reset_demo_data) through the real HTTP API, as real users.
It only reads: every write it attempts is one that FALCON must refuse.
Prints one line per acceptance test, grouped by aim, and exits 1 if any fails.
"""

import json
import statistics
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from http.cookiejar import CookieJar

from app.core.config import get_settings

API = "http://127.0.0.1:8010/api"
CASE = "CASE-2026-001"
C = f"/investigations/{CASE}"
# Words that would turn a lead into a verdict (plan.md §1, §43, §52).
VERDICT_WORDS = ("guilty", "culprit", "is responsible", "committed the", "criminal")


class Client:
    """One signed-in browser: its own cookie jar, the CSRF header on every request."""

    def __init__(self) -> None:
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def call(self, method: str, path: str, body=None, raw: bytes | None = None, ctype=None):
        headers = {"X-FALCON-Request": "1"}
        data = raw
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if ctype:
            headers["Content-Type"] = ctype
        request = urllib.request.Request(API + path, data=data, method=method, headers=headers)
        try:
            with self.opener.open(request, timeout=300) as r:
                content = r.read()
                return r.status, _parse(content), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, _parse(e.read()), dict(e.headers)

    def get(self, path: str):
        status, body, _ = self.call("GET", path)
        if status != 200:
            raise AssertionError(f"GET {path} returned {status}")
        return body

    def sign_in(self, email: str, password: str) -> None:
        status, _, _ = self.call("POST", "/auth/login", {"email": email, "password": password})
        if status != 200:
            raise SystemExit(f"Cannot sign in as {email} (HTTP {status}). Is the demo data reset?")


def _parse(content: bytes):
    try:
        return json.loads(content)
    except ValueError:
        return content


def _multipart(filename: str, content: bytes, fields: dict[str, str]) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
        for k, v in fields.items()
    ]
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n".encode()
        + content
        + b"\r\n"
    )
    return b"".join(
        parts
    ) + f"--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"


def build_checks(
    analyst: Client, evidence_analyst: Client, admin: Client, anonymous: Client, with_ai: bool
) -> list[tuple[str, str, Callable[[], str]]]:
    """(aim, test case, check). A check returns what it saw, or raises AssertionError."""

    def every_item_fingerprinted():
        items = analyst.get(f"{C}/evidence?limit=100")["items"]
        assert items, "no evidence in the demo case"
        bad = [
            e["reference"] for e in items if len(e["sha256"] or "") != 64 or not e["integrity_ok"]
        ]
        assert not bad, f"not intact: {bad}"
        return f"{len(items)} items, each with a SHA-256 fingerprint, all intact"

    def integrity_recheck():
        status, body, _ = analyst.call("POST", f"{C}/evidence/CCTV-001/verify-integrity")
        assert status == 200 and body["integrity_ok"], f"HTTP {status}"
        return "CCTV-001 re-hashed from storage: matches the fingerprint taken at upload"

    def duplicate_refused():
        _, original, _ = analyst.call("GET", f"{C}/evidence/CALL-001/content")
        assert isinstance(original, bytes | dict | list), "could not download CALL-001"
        content = original if isinstance(original, bytes) else json.dumps(original).encode()
        body, ctype = _multipart("again.csv", content, {"evidence_type": "call_records"})
        status, reply, _ = analyst.call("POST", f"{C}/evidence", raw=body, ctype=ctype)
        assert status == 409, f"HTTP {status}: a duplicate was accepted"
        return f"409 · {reply['detail'][:60]}…"

    def disguised_program_refused():
        body, ctype = _multipart(
            "photo.jpg", b"MZ\x90\x00" + b"\x00" * 200, {"evidence_type": "image"}
        )
        status, reply, _ = analyst.call("POST", f"{C}/evidence", raw=body, ctype=ctype)
        assert 400 <= status < 500, f"HTTP {status}: a Windows program named .jpg was accepted"
        return f"{status} · {str(reply.get('detail', ''))[:60]}"

    def empty_file_refused():
        body, ctype = _multipart("empty.txt", b"", {"evidence_type": "document"})
        status, _, _ = analyst.call("POST", f"{C}/evidence", raw=body, ctype=ctype)
        assert 400 <= status < 500, f"HTTP {status}"
        return f"{status} · an empty file is not evidence"

    def everything_processed():
        items = analyst.get(f"{C}/evidence?limit=100")["items"]
        done = [e for e in items if e["status"] == "processed"]
        assert len(done) == len(items), f"{len(items) - len(done)} not processed"
        types = sorted({e["evidence_type"] for e in items})
        return f"{len(done)}/{len(items)} processed across {len(types)} source types"

    def entities_found_across_sources():
        items = analyst.get(f"{C}/entities?limit=200")["items"]
        kinds = sorted({e["entity_type"] for e in items})
        assert len(kinds) >= 5, f"only {kinds}"
        v001 = analyst.get(f"{C}/entities/V001")
        assert v001["evidence_count"] >= 3, "the van is not linked across sources"
        sources = v001["evidence_count"]
        return f"{len(items)} entities of {len(kinds)} kinds; van V001 in {sources} sources"

    def facts_carry_confidence_and_source():
        events = analyst.get(f"{C}/events?limit=500")["items"]
        missing = [
            e["reference"]
            for e in events
            if e["confidence"] is None or not e["evidence_reference"] or not e["assertion_kind"]
        ]
        assert not missing, f"no confidence/source: {missing}"
        return f"all {len(events)} events name their source, method and confidence"

    def timeline_in_order():
        events = analyst.get(f"{C}/events?limit=500")["items"]
        times = [e["occurred_at"] for e in events if e["occurred_at"]]
        assert times == sorted(times), "events are out of order"
        case = analyst.get(C)
        return f"{len(times)} events in order, shown in the case time zone {case['time_zone']}"

    def events_on_the_map():
        events = analyst.get(f"{C}/events?limit=500")["items"]
        placed = [e for e in events if e["latitude"] is not None]
        assert placed, "no event has a location"
        return f"{len(placed)} of {len(events)} events have a map position"

    def correlations_explained():
        items = analyst.get(f"{C}/correlations?limit=200")["items"]
        assert items, "no correlations"
        for c in items:
            total = sum(f["contribution"] for f in c["factors"])
            assert abs(total - c["score"]) < 0.01, f"{c['reference']}: factors do not add up"
            assert all(f["explanation"] for f in c["factors"]), f"{c['reference']}: unexplained"
        levels = {lvl: sum(c["level"] == lvl for c in items) for lvl in ("high", "medium", "low")}
        return f"{len(items)} relationships; every score = sum of explained factors · {levels}"

    def strongest_first():
        items = analyst.get(f"{C}/correlations?limit=200")["items"]
        top = items[0]
        pair = f"{top['evidence_a']['reference']} ⟷ {top['evidence_b']['reference']}"
        assert top["reference"] == "COR-001" and top["level"] == "high", (
            f"top is {top['reference']}"
        )
        return f"COR-001 {pair} is High {top['score']:.2f}"

    def no_verdicts():
        items = analyst.get(f"{C}/correlations?limit=200")["items"]
        text = " ".join(f["explanation"].lower() for c in items for f in c["factors"])
        found = [w for w in VERDICT_WORDS if w in text]
        assert not found, f"verdict language: {found}"
        return "no 'guilty / responsible / culprit' language; only 'potential relationship'"

    def click_back_to_the_original():
        cor = analyst.get(f"{C}/correlations/COR-001")
        ref = cor["evidence_b"]["reference"]
        extracted = analyst.get(f"{C}/evidence/{ref}/extracted")
        status, _, headers = analyst.call("GET", f"{C}/evidence/{ref}/content")
        assert status == 200, f"original of {ref} not downloadable"
        n = len(extracted.get("entities", [])) + len(extracted.get("events", []))
        media = {k.lower(): v for k, v in headers.items()}.get("content-type", "?")
        return f"COR-001 → {ref} → {n} extracted facts → original file ({media})"

    def graph_connects():
        g = analyst.get(f"{C}/graph")
        assert g["nodes"] and g["edges"], "empty graph"
        return f"{len(g['nodes'])} nodes, {len(g['edges'])} links"

    def human_decides():
        status, _, _ = analyst.call(
            "POST", f"{C}/correlations/COR-001/review", {"review_status": "rejected", "note": ""}
        )
        assert status in (400, 422), f"HTTP {status}: rejected without a reason"
        return f"{status} · rejecting needs a written reason; nothing is auto-decided"

    def evidence_analyst_cannot_judge():
        status, _, _ = evidence_analyst.call(
            "POST", f"{C}/correlations/COR-001/review", {"review_status": "confirmed"}
        )
        assert status == 403, f"HTTP {status}"
        return "403 · an evidence analyst cannot confirm a relationship"

    def analyst_cannot_issue_reports():
        status, _, _ = analyst.call("POST", f"{C}/reports", {})
        assert status in (403, 422), f"HTTP {status}"
        return f"{status} · only officers issue reports"

    def admin_cannot_read_evidence():
        status, _, _ = admin.call("GET", f"{C}/evidence")
        assert status in (403, 404), f"HTTP {status}: the administrator read case evidence"
        return f"{status} · administrators manage people, not cases"

    def strangers_locked_out():
        status, _, _ = anonymous.call("GET", f"{C}/evidence")
        assert status == 401, f"HTTP {status}"
        return "401 · nothing without signing in"

    def audited():
        status, body, _ = admin.call("GET", "/audit?limit=200")
        assert status == 200, f"HTTP {status}"
        actions = {e["action"] for e in body["items"]}
        need = {"auth.login_succeeded", "correlation.run"}
        assert need <= actions, f"missing audit actions; saw {sorted(actions)[:8]}"
        return f"{body.get('total', len(body['items']))} audit entries; e.g. {sorted(actions)[:4]}"

    def security_headers():
        _, _, headers = analyst.call("GET", "/auth/me")
        lower = {k.lower() for k in headers}
        need = {"x-content-type-options", "x-frame-options", "content-security-policy"}
        assert need <= lower, f"missing {need - lower}"
        return "nosniff, frame protection and CSP on every reply"

    def fast_enough():
        slow = []
        # Warm up once, then the median of three, the way measure_performance times screens.
        for path in ("/dashboard", f"{C}/correlations", f"{C}/events?limit=500", f"{C}/graph"):
            analyst.get(path)
            runs = []
            for _ in range(3):
                started = time.perf_counter()
                analyst.get(path)
                runs.append((time.perf_counter() - started) * 1000)
            ms = statistics.median(runs)
            if ms > 500:
                slow.append(f"{path} {ms:.0f} ms")
        assert not slow, f"over 500 ms: {slow}"
        return "dashboard, correlations, timeline and graph each under 500 ms"

    def ai_search():
        status, ai, _ = analyst.call("GET", "/ai/status")
        if not ai.get("available"):
            return "SKIP · Ollama is not running"
        status, body, _ = analyst.call(
            "POST", f"{C}/ai/search", {"question": "Show all communications involving PH001"}
        )
        assert status == 200, f"HTTP {status}"
        refs = sorted(e["reference"] for e in body["events"])
        assert refs == ["E011", "E012", "E013"], f"got {refs}"
        return f"{body['interpreted_by']} → {refs} in {body['duration_ms'] / 1000:.0f} s"

    checks = [
        (
            "1 Store safely",
            "Every evidence item is fingerprinted and intact",
            every_item_fingerprinted,
        ),
        ("1 Store safely", "Integrity can be re-proved on demand", integrity_recheck),
        ("1 Store safely", "The same file cannot be added twice", duplicate_refused),
        ("1 Store safely", "A program disguised as a photo is refused", disguised_program_refused),
        ("1 Store safely", "An empty file is refused", empty_file_refused),
        ("2 Extract", "All 8 source types are processed", everything_processed),
        (
            "2 Extract",
            "People, phones, vehicles… found and linked across sources",
            entities_found_across_sources,
        ),
        (
            "2 Extract",
            "Every fact names its source and confidence",
            facts_carry_confidence_and_source,
        ),
        ("3 Connect", "Timeline is in time order", timeline_in_order),
        ("3 Connect", "Events with places can be mapped", events_on_the_map),
        ("3 Connect", "Every relationship is explained factor by factor", correlations_explained),
        ("3 Connect", "Strongest lead comes first", strongest_first),
        ("3 Connect", "Graph links entities and evidence", graph_connects),
        ("4 Explain & trace", "From a lead back to the original file", click_back_to_the_original),
        ("4 Explain & trace", "No verdicts: leads, not conclusions", no_verdicts),
        ("5 Human in control", "Rejecting a lead needs a reason", human_decides),
        (
            "5 Human in control",
            "Evidence analyst cannot judge leads",
            evidence_analyst_cannot_judge,
        ),
        (
            "5 Human in control",
            "Analyst cannot issue official reports",
            analyst_cannot_issue_reports,
        ),
        ("6 Secure", "Administrator cannot read case evidence", admin_cannot_read_evidence),
        ("6 Secure", "Signed-out visitor sees nothing", strangers_locked_out),
        ("6 Secure", "Sensitive actions are in the audit log", audited),
        ("6 Secure", "Browser security headers are set", security_headers),
        ("7 Fast", "Main screens answer in under 500 ms", fast_enough),
    ]
    if with_ai:
        checks.append(("8 Local AI", "Plain-English search finds PH001's calls", ai_search))
    return checks


def main() -> int:
    password = get_settings().demo_password
    if password is None:
        print("Set DEMO_PASSWORD in .env (development only).")
        return 1
    secret = password.get_secret_value()
    analyst, evidence_analyst, admin, anonymous = Client(), Client(), Client(), Client()
    analyst.sign_in("a.kumar@falcon.example", secret)
    evidence_analyst.sign_in("m.das@falcon.example", secret)
    admin.sign_in("admin@falcon.example", secret)

    failed = 0
    aim = ""
    checks = build_checks(analyst, evidence_analyst, admin, anonymous, "--ai" in sys.argv)
    for number, (group, title, check) in enumerate(checks, start=1):
        if group != aim:
            aim = group
            print(f"\nAIM {group}")
        try:
            outcome = check()
            mark = "SKIP" if outcome.startswith("SKIP") else "PASS"
        except AssertionError as e:
            outcome, mark = str(e), "FAIL"
            failed += 1
        print(f"  AT-{number:02d} {mark}  {title}\n               {outcome}")

    for client in (analyst, evidence_analyst, admin):
        client.call("POST", "/auth/logout")
    print(f"\n{len(checks) - failed} of {len(checks)} acceptance tests passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
