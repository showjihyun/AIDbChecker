# Spec: AG-001 — Shared DSN builder for target DB connections
"""Build asyncpg DSN from DBInstance fields + decrypted credentials."""

import re
import urllib.parse

from app.models.db_instance import DBInstance
from app.utils.encryption import decrypt_value

# Validation patterns — prevent DSN injection via malicious host/database values
_HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9._-]+$")
_DBNAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_dsn_components(host: str, port: int, database_name: str) -> None:
    """Validate DSN components to prevent injection attacks.

    Raises ValueError if any component contains suspicious characters.
    """
    if not _HOSTNAME_RE.match(host):
        raise ValueError(
            f"Invalid hostname: '{host}'. Only alphanumeric, dots, hyphens, underscores allowed."
        )
    if not (1 <= port <= 65535):
        raise ValueError(f"Invalid port: {port}. Must be 1-65535.")
    if not _DBNAME_RE.match(database_name):
        raise ValueError(
            f"Invalid database name: '{database_name}'. Only alphanumeric, hyphens, underscores allowed."
        )


def build_target_dsn(instance: DBInstance) -> str:
    """Build asyncpg-compatible DSN from instance fields.

    Validates host/port/database_name to prevent DSN injection.
    Decrypts username/password from connection_config (Fernet-encrypted).
    Uses urllib.parse.quote_plus for safe URL encoding of credentials.
    """
    _validate_dsn_components(instance.host, instance.port, instance.database_name)

    config = instance.connection_config or {}
    username = decrypt_value(config["username"]) if "username" in config else "neuraldb"
    password = decrypt_value(config["password"]) if "password" in config else ""
    ssl_mode = config.get("sslmode", "prefer")

    return (
        f"postgresql://{urllib.parse.quote_plus(username)}:{urllib.parse.quote_plus(password)}"
        f"@{instance.host}:{instance.port}/{instance.database_name}"
        f"?sslmode={urllib.parse.quote_plus(ssl_mode)}"
    )
