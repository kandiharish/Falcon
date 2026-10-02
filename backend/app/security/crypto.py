"""Encryption of small secrets at rest (MFA secrets), with AES-256-GCM.

Why encrypt? A copy of the database (a backup, a leak) must not let anyone generate a
user's MFA codes. The key lives in the environment (FALCON_SECRET_KEY), never in the
database, so the two must be stolen together.

GCM is "authenticated" encryption: tampering with the stored text is detected on decrypt.
"""

import base64
import hashlib
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

PREFIX = "v1:"  # lets us change the scheme later without breaking stored values


class CryptoUnavailable(Exception):
    """No FALCON_SECRET_KEY configured."""


def _key() -> bytes:
    secret = get_settings().falcon_secret_key
    if secret is None or not secret.get_secret_value():
        raise CryptoUnavailable(
            "Multi-factor authentication needs FALCON_SECRET_KEY in the server settings."
        )
    # A fixed-length 256-bit key from whatever text was configured.
    return hashlib.sha256(secret.get_secret_value().encode()).digest()


def encrypt(plaintext: str) -> str:
    nonce = os.urandom(12)  # never reuse a nonce with the same key: random every time
    sealed = AESGCM(_key()).encrypt(nonce, plaintext.encode(), associated_data=None)
    return PREFIX + base64.urlsafe_b64encode(nonce + sealed).decode()


def decrypt(stored: str) -> str:
    if not stored.startswith(PREFIX):
        raise ValueError("Unknown encryption format.")
    raw = base64.urlsafe_b64decode(stored[len(PREFIX) :])
    try:
        return AESGCM(_key()).decrypt(raw[:12], raw[12:], associated_data=None).decode()
    except InvalidTag as error:
        raise ValueError("The stored secret was altered or the key changed.") from error
