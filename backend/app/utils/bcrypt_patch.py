# Spec: BACKEND_TEST_SPEC
"""Patch bcrypt 5.x to truncate passwords >72 bytes instead of raising.

passlib's internal `detect_wrap_bug` sends a 256-byte test password during
backend initialization, but bcrypt 5.x raises ValueError for passwords
exceeding 72 bytes. This patch restores the historical bcrypt behavior
that passlib expects (silent truncation).

Import this module BEFORE any passlib import.
"""

import bcrypt

_orig_hashpw = bcrypt.hashpw
_orig_checkpw = bcrypt.checkpw


def _patched_hashpw(password: bytes, salt: bytes) -> bytes:
    if isinstance(password, bytes) and len(password) > 72:
        password = password[:72]
    return _orig_hashpw(password, salt)


def _patched_checkpw(password: bytes, hashed: bytes) -> bool:
    if isinstance(password, bytes) and len(password) > 72:
        password = password[:72]
    return _orig_checkpw(password, hashed)


bcrypt.hashpw = _patched_hashpw  # type: ignore[assignment]
bcrypt.checkpw = _patched_checkpw  # type: ignore[assignment]
