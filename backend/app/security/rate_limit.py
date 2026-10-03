"""Rate limiting: slow down guessing and stop one user from exhausting the server.

    sign-in        10 tries / minute per IP address   (plus the per-account lockout)
    MFA code       10 tries / minute per IP address
    AI assistant    6 questions / minute per user     (each one keeps the CPU busy for minutes)
    AI search      20 searches / minute per user
    uploads        30 files / minute per user

A "sliding window": remember the time of each recent request; if there are already N within
the window, refuse with 429 Too Many Requests and say when to try again.

The memory lives inside the API process. FALCON runs one API process, so that is exact;
with several processes the limits would need a shared store (Redis) instead.
"""

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.security.tokens import hash_token
from app.services.request_context import request_context


class SlidingWindow:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_s: float, now: float | None = None) -> float:
        """Record a request. Returns 0 when allowed, else the seconds until it would be."""
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - window_s:
                hits.popleft()
            if len(hits) >= limit:
                return hits[0] + window_s - now
            hits.append(now)
            if len(self._hits) > 50_000:  # never let the memory grow without bound
                self._forget_idle(now, window_s)
            return 0.0

    def _forget_idle(self, now: float, window_s: float) -> None:
        for key in [k for k, v in self._hits.items() if not v or v[-1] <= now - window_s]:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


WINDOW = SlidingWindow()


def limit(bucket: str, per_minute: int, by: str = "ip") -> Callable[[Request], None]:
    """A FastAPI dependency: `Depends(limit("login", 10))`."""

    def dependency(request: Request) -> None:
        if by == "user":  # the session (hashed): one bucket per signed-in browser
            cookie = request.cookies.get(get_settings().session_cookie_name, "")
            who = hash_token(cookie)[:16] if cookie else "anonymous"
        else:
            who = request_context(request).ip_address or "unknown"
        wait = WINDOW.hit(f"{bucket}:{who}", per_minute, 60.0)
        if wait > 0:
            seconds = max(1, int(wait) + 1)
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Too many attempts. Wait {seconds} seconds and try again.",
                headers={"Retry-After": str(seconds)},
            )

    return dependency
