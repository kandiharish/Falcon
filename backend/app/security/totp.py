"""Time-based one-time passwords (TOTP, RFC 6238) — what authenticator apps compute.

    shared secret (20 random bytes, shown once as a QR code)
         │
    step = floor(unix time / 30)          ← changes every 30 seconds
         │
    HMAC-SHA1(secret, step) → pick 4 bytes → number mod 1,000,000 → "492 038"

The phone and the server compute the same 6 digits without talking to each other: only
someone holding the secret (the enrolled phone) can produce the current code.
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

STEP_SECONDS = 30
DIGITS = 6
DRIFT_STEPS = 1  # accept the previous/next code too: phone clocks are a little off


def new_secret() -> str:
    """160 random bits, written in base32 (the alphabet authenticator apps expect)."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _key(secret: str) -> bytes:
    padded = secret.upper() + "=" * (-len(secret) % 8)
    return base64.b32decode(padded)


def code_at(secret: str, step: int) -> str:
    digest = hmac.new(_key(secret), struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F  # "dynamic truncation": the last nibble picks where to read
    number = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10**DIGITS).zfill(DIGITS)


def current_step(now: float | None = None) -> int:
    return int((time.time() if now is None else now) // STEP_SECONDS)


def verify(
    secret: str, code: str, last_used_step: int | None, now: float | None = None
) -> int | None:
    """The time step the code belongs to, or None. A step already used is refused, so a
    code seen over someone's shoulder cannot be replayed within its 30 seconds."""
    code = "".join(ch for ch in code if ch.isdigit())
    if len(code) != DIGITS:
        return None
    step = current_step(now)
    for candidate in range(step - DRIFT_STEPS, step + DRIFT_STEPS + 1):
        if last_used_step is not None and candidate <= last_used_step:
            continue
        if hmac.compare_digest(code_at(secret, candidate), code):  # constant-time compare
            return candidate
    return None


def provisioning_uri(secret: str, account: str, issuer: str = "FALCON") -> str:
    """The text inside the QR code; every authenticator app understands it."""
    label = quote(f"{issuer}:{account}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}&digits={DIGITS}&period={STEP_SECONDS}"


def new_recovery_codes(count: int = 8) -> list[str]:
    """One-time backup codes for a lost phone, e.g. 'k7qd-3mxa'."""
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"  # no 0/o, 1/l/i: easy to read aloud
    return [
        "-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(2))
        for _ in range(count)
    ]


def hash_recovery_code(code: str) -> str:
    return hashlib.sha256(code.strip().lower().replace(" ", "").encode()).hexdigest()
