# Spec: BACKEND_TEST_SPEC
"""Unit test conftest -- patches bcrypt 5.x compatibility issue with passlib.

passlib's internal `detect_wrap_bug` sends a 256-byte test password during
backend initialization, but bcrypt 5.x raises ValueError for passwords
exceeding 72 bytes. This conftest patches bcrypt.hashpw/checkpw to silently
truncate, matching the historical bcrypt behavior that passlib expects.
"""

import bcrypt


def _patch_bcrypt_72_byte_limit() -> None:
    """Patch bcrypt to truncate passwords >72 bytes instead of raising."""
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


# Apply patch before any passlib import triggers backend initialization
_patch_bcrypt_72_byte_limit()
