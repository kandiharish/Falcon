"""Time the API on the big load-test case, the way the browser calls it. Development only.

    uv run python -m app.scripts.seed_load_test          # once
    uv run python -m app.scripts.measure_performance     # API on http://127.0.0.1:8010

Signs in as the forensic analyst on the case team (demo password from .env), calls each
endpoint 5 times and prints the median and slowest time and the size of the reply.
Budget: every screen's data < 500 ms.
"""

import json
import statistics
import sys
import time
import urllib.request
from http.cookiejar import CookieJar

from app.core.config import get_settings

API = "http://127.0.0.1:8010/api"
CASE = "CASE-2026-900"
BUDGET_MS = 500
# The graph is an analysis view over the WHOLE case (6,000 events here): it gets more time.
SLOWER_BUDGET_MS = {"Graph (capped)": 1500, "Graph + events": 1500}
CHECKS = [
    ("Dashboard", "GET", "/dashboard"),
    ("Evidence list", "GET", f"/investigations/{CASE}/evidence?limit=25"),
    ("Entities list", "GET", f"/investigations/{CASE}/entities?limit=50"),
    ("Events (timeline)", "GET", f"/investigations/{CASE}/events?limit=500"),
    ("Correlations", "GET", f"/investigations/{CASE}/correlations?limit=200"),
    ("Graph (capped)", "GET", f"/investigations/{CASE}/graph"),
    ("Graph + events", "GET", f"/investigations/{CASE}/graph?include_events=true"),
    ("Global search", "GET", "/search?q=Synthetic%20vehicle%2012"),
    ("Notifications", "GET", "/notifications"),
    ("Review an entity", "POST", f"/investigations/{CASE}/entities/V001/review"),
]


def main() -> int:
    password = get_settings().demo_password
    if password is None:
        print("Set DEMO_PASSWORD in .env (development only).")
        return 1
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def call(method: str, path: str, body: dict | None = None) -> tuple[float, int]:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            API + path,
            data=data,
            method=method,
            headers={"X-FALCON-Request": "1", "Content-Type": "application/json"},
        )
        started = time.perf_counter()
        with opener.open(request, timeout=120) as response:
            size = len(response.read())
        return (time.perf_counter() - started) * 1000, size

    call(
        "POST",
        "/auth/login",
        {"email": "a.kumar@falcon.example", "password": password.get_secret_value()},
    )
    print(f"{'Endpoint':<20}{'median':>10}{'slowest':>10}{'size':>10}")
    over = 0
    for label, method, path in CHECKS:
        body = {"review_status": "confirmed"} if method == "POST" else None
        runs = [call(method, path, body) for _ in range(5)]
        times = [ms for ms, _ in runs]
        median = statistics.median(times)
        budget = SLOWER_BUDGET_MS.get(label, BUDGET_MS)
        flag = "" if median <= budget else f"  <-- over its {budget} ms budget"
        over += median > budget
        print(f"{label:<20}{median:>8.0f}ms{max(times):>8.0f}ms{runs[0][1] / 1024:>8.0f}kB{flag}")
    call("POST", "/auth/logout")
    print(f"\n{over} of {len(CHECKS)} over budget ({BUDGET_MS} ms; the graph 1500 ms).")
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
