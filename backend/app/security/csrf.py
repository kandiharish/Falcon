"""CSRF protection.

Attack: a malicious site makes your browser send a POST to FALCON; the browser attaches your
session cookie automatically. Two defences:
  1. The cookie is SameSite=Lax → browsers don't send it on cross-site POSTs.
  2. Every state-changing request must carry the header X-FALCON-Request. Other websites
     cannot add custom headers to requests aimed at us without our permission (CORS),
     and we grant none.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

CSRF_HEADER = "X-FALCON-Request"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
BLOCKED_MESSAGE = "This request was blocked for security reasons. Reload the page and try again."


class CSRFHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in UNSAFE_METHODS and request.url.path.startswith("/api/"):
            if request.headers.get(CSRF_HEADER) != "1":
                return JSONResponse(
                    status_code=403,
                    content={"detail": BLOCKED_MESSAGE},
                )
        return await call_next(request)
