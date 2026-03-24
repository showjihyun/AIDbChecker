# Spec: ADR-007
"""Fernet symmetric encryption for target DB credentials.

Used to encrypt sensitive fields in db_instances.connection_config
and alert_channels.config (webhook URLs, API keys).

The encryption key MUST be a valid Fernet key (32 url-safe base64-encoded bytes).
For development, a default key is derived from settings.CREDENTIAL_ENCRYPTION_KEY.
For production, generate a proper key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

# Derive a valid 32-byte Fernet key from the configured secret.
# If the configured key is already a valid Fernet key, use it directly.
# Otherwise, derive one via SHA-256 hash + base64 encoding.
_raw_key = settings.CREDENTIAL_ENCRYPTION_KEY


def _derive_fernet_key(raw: str) -> bytes:
    """Derive a valid Fernet key from an arbitrary string."""
    try:
        # Try using it as-is (if already a valid Fernet key)
        Fernet(raw.encode())
        return raw.encode()
    except (ValueError, Exception):
        # Derive via SHA-256 → base64url
        digest = hashlib.sha256(raw.encode()).digest()
        return base64.urlsafe_b64encode(digest)


_fernet = Fernet(_derive_fernet_key(_raw_key))


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string. Returns base64-encoded ciphertext."""
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a ciphertext string. Raises ValueError on invalid token."""
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError(
            "Failed to decrypt value. The encryption key may have changed, "
            "or the ciphertext is corrupted. Re-encrypt the credential."
        ) from exc
