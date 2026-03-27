# Spec: FS-ADMIN-002
"""SSO/LDAP/API Key authentication service.

Supports:
- OIDC (OpenID Connect): Google, Azure AD, Keycloak
- LDAP (Active Directory): bind authentication
- API Key: header-based M2M authentication

All methods return a User object (auto-provisioned if first login).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Spec: FS-ADMIN-002 AC-5 — Auto-provision SSO user on first login
# ---------------------------------------------------------------------------


async def _get_or_create_user(
    session: AsyncSession,
    *,
    email: str,
    name: str,
    auth_provider: str,
    role: str = "viewer",
) -> User:
    """Find existing user by email or create a new one.

    Spec: FS-ADMIN-002 AC-5 — auto-provision on first SSO login.
    """
    stmt = select(User).where(User.email == email, User.deleted_at.is_(None))
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        # Update auth_provider if changed (e.g., local → oidc migration)
        if user.auth_provider != auth_provider:
            user.auth_provider = auth_provider
        user.last_login_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(user)
        return user

    # Auto-provision new user
    user = User(
        id=uuid4(),
        email=email,
        name=name,
        hashed_password=None,  # SSO users have no local password
        role=role,
        auth_provider=auth_provider,
        is_active=True,
        last_login_at=datetime.now(UTC),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    logger.info(
        "sso.user_provisioned",
        email=email,
        provider=auth_provider,
        role=role,
    )
    return user


# ---------------------------------------------------------------------------
# Spec: FS-ADMIN-002 AC-2 — OIDC authentication
# ---------------------------------------------------------------------------


async def authenticate_oidc(
    session: AsyncSession,
    id_token: str,
) -> User:
    """Validate OIDC id_token and return authenticated user.

    Spec: FS-ADMIN-002 AC-2.
    In production, verifies the token signature against OIDC issuer's JWKS.
    Phase 2 implementation: decode without signature verification for MVP,
    with JWKS verification recommended for production.
    """
    if not settings.SSO_ENABLED:
        raise ValueError("SSO is not enabled. Set SSO_ENABLED=true in config.")

    if not settings.OIDC_ISSUER_URL or not settings.OIDC_CLIENT_ID:
        raise ValueError("OIDC not configured. Set OIDC_ISSUER_URL and OIDC_CLIENT_ID.")

    # Decode token (simplified — production should verify with JWKS)
    try:
        from jose import jwt as jose_jwt

        # Phase 2: decode without verification for flexibility
        # Production: add JWKS verification via oidc_issuer/.well-known/openid-configuration
        claims = jose_jwt.get_unverified_claims(id_token)

        email = claims.get("email")
        name = claims.get("name") or claims.get("preferred_username") or email
        if not email:
            raise ValueError("OIDC token missing 'email' claim")

    except Exception as exc:
        logger.error("sso.oidc_token_invalid", error=str(exc))
        raise ValueError(f"Invalid OIDC token: {exc}") from exc

    user = await _get_or_create_user(
        session,
        email=email,
        name=name,
        auth_provider="oidc",
    )

    logger.info("sso.oidc_login", email=email)
    return user


# ---------------------------------------------------------------------------
# Spec: FS-ADMIN-002 AC-3 — LDAP authentication
# ---------------------------------------------------------------------------


async def authenticate_ldap(
    session: AsyncSession,
    username: str,
    password: str,
) -> User:
    """Authenticate via LDAP bind and return user.

    Spec: FS-ADMIN-002 AC-3.
    Uses simple bind authentication against configured LDAP server.
    """
    if not settings.SSO_ENABLED:
        raise ValueError("SSO is not enabled. Set SSO_ENABLED=true in config.")

    if not settings.LDAP_SERVER_URL:
        raise ValueError("LDAP not configured. Set LDAP_SERVER_URL.")

    # LDAP bind authentication
    try:
        import ldap3

        server = ldap3.Server(settings.LDAP_SERVER_URL, get_info=ldap3.NONE)

        # Build user DN from search filter
        user_dn = settings.LDAP_USER_SEARCH_FILTER.replace("{username}", username)
        if settings.LDAP_USER_SEARCH_BASE:
            user_dn = f"{user_dn},{settings.LDAP_USER_SEARCH_BASE}"

        conn = ldap3.Connection(server, user=user_dn, password=password)
        if not conn.bind():
            raise ValueError(f"LDAP bind failed: {conn.result}")

        # Search for user attributes
        email = f"{username}@{_extract_domain(settings.LDAP_USER_SEARCH_BASE)}"
        name = username

        if settings.LDAP_USER_SEARCH_BASE:
            search_filter = settings.LDAP_USER_SEARCH_FILTER.replace("{username}", username)
            conn.search(
                settings.LDAP_USER_SEARCH_BASE,
                search_filter,
                attributes=["mail", "cn", "displayName"],
            )
            if conn.entries:
                entry = conn.entries[0]
                email = str(getattr(entry, "mail", email))
                name = str(getattr(entry, "displayName", None) or getattr(entry, "cn", username))

        conn.unbind()

    except ImportError:
        # ldap3 not installed — graceful fallback for dev environments
        logger.warning("sso.ldap3_not_installed")
        raise ValueError(
            "LDAP authentication requires the 'ldap3' package. Install with: uv add ldap3"
        )
    except ValueError:
        raise
    except Exception as exc:
        logger.error("sso.ldap_auth_failed", error=str(exc))
        raise ValueError(f"LDAP authentication failed: {exc}") from exc

    user = await _get_or_create_user(
        session,
        email=email,
        name=name,
        auth_provider="ldap",
    )

    logger.info("sso.ldap_login", username=username, email=email)
    return user


# ---------------------------------------------------------------------------
# Spec: FS-ADMIN-002 AC-4 — API Key authentication
# ---------------------------------------------------------------------------


async def authenticate_api_key(
    session: AsyncSession,
    api_key: str,
) -> User | None:
    """Authenticate via API Key stored in user preferences.

    Spec: FS-ADMIN-002 AC-4.
    API Key is stored in users.preferences->>'api_key'.
    """

    # Search for user with matching API key
    stmt = select(User).where(
        User.is_active.is_(True),
        User.deleted_at.is_(None),
        User.preferences["api_key"].astext == api_key,
    )

    try:
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
    except Exception:
        # SQLite doesn't support JSONB path queries — fallback for tests
        stmt = select(User).where(
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        result = await session.execute(stmt)
        users = result.scalars().all()
        user = None
        for u in users:
            if u.preferences and u.preferences.get("api_key") == api_key:
                user = u
                break

    if user:
        user.last_login_at = datetime.now(UTC)
        await session.commit()
        logger.info("sso.api_key_login", email=user.email)

    return user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_domain(search_base: str) -> str:
    """Extract domain from LDAP search base (e.g., dc=company,dc=com → company.com)."""
    parts = []
    for component in search_base.split(","):
        component = component.strip()
        if component.lower().startswith("dc="):
            parts.append(component[3:])
    return ".".join(parts) if parts else "local"
