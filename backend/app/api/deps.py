# Spec: MVP-ADMIN-001, MVP-ADMIN-002, FS-ADMIN-002
"""FastAPI dependency injection — DB sessions + JWT + API Key authentication."""

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_session  # re-export for convenience
from app.models.user import User

# OAuth2 scheme — extracts Bearer token from Authorization header.
# tokenUrl points to the login endpoint for OpenAPI docs integration.
# auto_error=False to allow API Key fallback (FS-ADMIN-002 AC-4)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

# Re-export get_session so deps.py is the canonical import for API dependencies
__all__ = ["get_session", "get_current_user", "require_role", "oauth2_scheme"]


async def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """Validate JWT token or API Key and return the authenticated User.

    Priority: Bearer JWT token → X-API-Key header fallback (FS-ADMIN-002 AC-4).
    Raises HTTPException 401 if neither is valid.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Spec: FS-ADMIN-002 AC-4 — API Key fallback
    if token is None:
        api_key = request.headers.get(settings.API_KEY_HEADER)
        if api_key:
            from app.services.sso import authenticate_api_key

            user = await authenticate_api_key(session, api_key)
            if user:
                return user
        raise credentials_exception

    # JWT path (existing)
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(
            tz=timezone.utc
        ):
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user_id = UUID(user_id_str)
    stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_exception

    return user


def require_role(*allowed_roles: str):
    """Return a dependency that checks the user has one of the allowed roles.

    Usage:
        @router.post("/", dependencies=[Depends(require_role("super_admin", "db_admin"))])
    """

    async def _check_role(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{current_user.role}' is not authorized for this action. "
                    f"Required: {', '.join(allowed_roles)}."
                ),
            )
        return current_user

    return _check_role
