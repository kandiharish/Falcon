"""Who is calling, from where — captured once per request for sessions and audit records."""

import ipaddress
from dataclasses import dataclass

from fastapi import Request


@dataclass(frozen=True)
class RequestContext:
    ip_address: str | None
    user_agent: str | None


def _valid_ip(value: str | None) -> str | None:
    """Only real IP addresses are stored; anything else (e.g. "testclient") becomes None."""
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


def request_context(request: Request) -> RequestContext:
    user_agent = request.headers.get("user-agent")
    return RequestContext(
        ip_address=_valid_ip(request.client.host if request.client else None),
        user_agent=user_agent[:400] if user_agent else None,
    )
