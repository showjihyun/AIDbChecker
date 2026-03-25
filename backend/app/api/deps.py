# Spec: MVP-ADMIN-001, MVP-ADMIN-002
"""FastAPI dependency injection — DB sessions + JWT authentication."""

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_session  # re-export for convenience
from app.models.user import User

# OAuth2 scheme — extracts Bearer token from Authorization header.
# tokenUrl points to the login endpoint for OpenAPI docs integration.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Optional variant that doesn't raise 401 when token is missing.
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login", auto_error=False
)

# Re-export get_session so deps.py is the canonical import for API dependencies
__all__ = ["get_session", "get_current_user", "require_role", "oauth2_scheme"]


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """Validate JWT token and return the authenticated User.

    Raises HTTPException 401 if the token is invalid, expired, or the
    user is not found / inactive.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        # Check expiration
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
