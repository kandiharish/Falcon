"""Security headers on every API response (plan §26).

Each header tells the browser to switch off a feature attackers like:

    X-Content-Type-Options: nosniff   don't guess file types (an "image" can't run as a script)
    X-Frame-Options / frame-ancestors  FALCON may not be shown inside another site (clickjacking)
    Content-Security-Policy            API replies are data: they may load and run NOTHING
    Referrer-Policy                    don't leak FALCON URLs (case IDs) to other sites
    Permissions-Policy                 no camera, microphone, geolocation… for this origin
    Cache-Control: no-store            evidence data must not linger in shared/browser caches
    Strict-Transport-Security          (HTTPS only) always use HTTPS for this site from now on

The web app's own CSP (scripts, styles, map tiles) is set by the web server in production
(deploy/Caddyfile), because the API never serves HTML.
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings

BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}
API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
# The interactive API docs page needs its own scripts and styles (development only).
DOCS_CSP = (
    "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; img-src 'self' data: "
    "https://fastapi.tiangolo.com; frame-ancestors 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        for name, value in BASE_HEADERS.items():
            response.headers.setdefault(name, value)
        docs = request.url.path in ("/api/docs", "/api/docs/oauth2-redirect")
        response.headers.setdefault("Content-Security-Policy", DOCS_CSP if docs else API_CSP)
        # Personal and evidence data: never stored by browsers or proxies. Evidence files
        # that are safe to cache set their own Cache-Control before reaching here.
        response.headers.setdefault("Cache-Control", "no-store")
        if get_settings().session_cookie_secure:  # we are behind HTTPS
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response
