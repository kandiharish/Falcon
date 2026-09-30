"""Session tokens.

The browser gets a long random token in an httpOnly cookie. The database stores only
its SHA-256 hash — so a leaked database copy cannot be used to log in as anyone.
"""

import hashlib
import secrets


def new_session_token() -> str:
    return secrets.token_urlsafe(32)  # 256 bits of randomness


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
