# Spec: AG-001 — Shared DSN builder for target DB connections
"""Build asyncpg DSN from DBInstance fields + decrypted credentials."""

import urllib.parse

from app.models.db_instance import DBInstance
from app.utils.encryption import decrypt_value


def build_target_dsn(instance: DBInstance) -> str:
    """Build asyncpg-compatible DSN from instance fields.

    Decrypts username/password from connection_config (Fernet-encrypted).
    Uses urllib.parse.quote_plus for safe URL encoding.
    """
    config = instance.connection_config or {}
    username = decrypt_value(config["username"]) if "username" in config else "neuraldb"
    password = decrypt_value(config["password"]) if "password" in config else ""
    ssl_mode = config.get("sslmode", "prefer")
    return (
        f"postgresql://{urllib.parse.quote_plus(username)}:{urllib.parse.quote_plus(password)}"
        f"@{instance.host}:{instance.port}/{instance.database_name}"
        f"?sslmode={ssl_mode}"
    )
