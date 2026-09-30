"""Password hashing with Argon2id — the current recommendation (OWASP).

We never store passwords, only a slow, salted hash. "Slow" is the point:
it makes guessing billions of passwords from a stolen database impractical.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()  # Argon2id with the library's current safe defaults

# Used when an email does not exist, so a wrong email takes as long as a wrong password.
# Otherwise response timing would reveal which emails have accounts.
_DUMMY_HASH = _hasher.hash("falcon-timing-equaliser")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True when the hashing parameters were strengthened since this hash was made."""
    return _hasher.check_needs_rehash(password_hash)
