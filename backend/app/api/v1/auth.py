# Spec: MVP-ADMIN-001 — JWT Authentication endpoints
"""Auth endpoints: login, token refresh, current user info."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.utils.bcrypt_patch  # noqa: F401 — must be imported before passlib
from app.api.deps import get_current_user, get_session
from app.config import settings
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class UserMeResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    auth_provider: str
    is_active: bool
    last_login_at: datetime | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_token(sub: str, expires_delta: timedelta) -> str:
    expire = datetime.now(tz=UTC) + expires_delta
    payload = {"sub": sub, "exp": expire, "iat": datetime.now(tz=UTC)}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _create_access_token(user_id: str) -> str:
    return _create_token(
        sub=user_id,
        expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def _create_refresh_token(user_id: str) -> str:
    return _create_token(
        sub=user_id,
        expires_delta=timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Authenticate with email + password, receive JWT access and refresh tokens."""
    stmt = select(User).where(
        User.email == form_data.username,
        User.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or user.hashed_password is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact an administrator.",
        )

    # Update last_login_at
    user.last_login_at = datetime.now(tz=UTC)
    await session.commit()

    user_id = str(user.id)
    return TokenResponse(
        access_token=_create_access_token(user_id),
        refresh_token=_create_refresh_token(user_id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: TokenRefreshRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Exchange a valid refresh token for a new access + refresh token pair."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            body.refresh_token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception

    stmt = select(User).where(
        User.id == user_id_str,
        User.deleted_at.is_(None),
        User.is_active.is_(True),
    )
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception

    user_id = str(user.id)
    return TokenResponse(
        access_token=_create_access_token(user_id),
        refresh_token=_create_refresh_token(user_id),
    )


# ---------------------------------------------------------------------------
# Spec: FS-ADMIN-002 — SSO/LDAP endpoints
# ---------------------------------------------------------------------------


class OIDCCallbackRequest(BaseModel):
    id_token: str


class LDAPLoginRequest(BaseModel):
    username: str
    password: str


@router.post("/oidc/callback", response_model=TokenResponse)
async def oidc_callback(
    body: OIDCCallbackRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Exchange OIDC id_token for JWT tokens.

    Spec: FS-ADMIN-002 AC-2, AC-5, AC-6.
    """
    if not settings.SSO_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO is not enabled.",
        )

    from app.services.sso import authenticate_oidc

    try:
        user = await authenticate_oidc(session, body.id_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )

    user_id = str(user.id)
    return TokenResponse(
        access_token=_create_access_token(user_id),
        refresh_token=_create_refresh_token(user_id),
    )


@router.post("/ldap", response_model=TokenResponse)
async def ldap_login(
    body: LDAPLoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Authenticate via LDAP and issue JWT tokens.

    Spec: FS-ADMIN-002 AC-3, AC-5, AC-6.
    """
    if not settings.SSO_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO is not enabled.",
        )

    from app.services.sso import authenticate_ldap

    try:
        user = await authenticate_ldap(session, body.username, body.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )

    user_id = str(user.id)
    return TokenResponse(
        access_token=_create_access_token(user_id),
        refresh_token=_create_refresh_token(user_id),
    )


@router.get("/me", response_model=UserMeResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserMeResponse:
    """Return the currently authenticated user's profile."""
    return UserMeResponse.model_validate(current_user)
