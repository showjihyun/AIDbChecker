# Spec: MVP-ADMIN-001, MVP-ADMIN-002
"""Unit tests for FastAPI dependency functions (backend/app/api/deps.py).

Tests cover:
- get_current_user: valid token, expired token, invalid token, inactive user
- require_role: allows matching role, blocks wrong role (403)
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import HTTPException
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from unittest.mock import MagicMock

from app.api.deps import get_current_user, require_role
from app.api.v1.auth import _create_access_token, _create_token, pwd_context
from app.config import settings
from app.models.user import User
from tests.conftest import spec_ref


def _mock_request(api_key: str | None = None):
    """Create a mock Request with optional X-API-Key header."""
    req = MagicMock()
    headers = {}
    if api_key:
        headers[settings.API_KEY_HEADER] = api_key
    req.headers = headers
    return req


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _insert_user(
    session: AsyncSession,
    *,
    role: str = "super_admin",
    is_active: bool = True,
) -> User:
    """Insert a User into the test DB."""
    user = User(
        id=uuid4(),
        email=f"dep-test-{uuid4().hex[:8]}@neuraldb.io",
        name="Dep Test User",
        hashed_password=pwd_context.hash("TestPass123!"),
        role=role,
        auth_provider="local",
        is_active=is_active,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Tests: get_current_user
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    """Tests for the get_current_user dependency."""

    @spec_ref("MVP-ADMIN-001", "AC-6")
    async def test_valid_token_returns_user(
        self, async_session: AsyncSession
    ) -> None:
        """A valid JWT token should resolve to the correct User object."""
        user = await _insert_user(async_session)
        token = _create_access_token(str(user.id))

        result = await get_current_user(request=_mock_request(), token=token, session=async_session)

        assert result.id == user.id
        assert result.email == user.email
        assert result.role == user.role

    @spec_ref("MVP-ADMIN-001", "AC-6")
    async def test_expired_token_returns_401(
        self, async_session: AsyncSession
    ) -> None:
        """An expired JWT token should raise HTTPException 401."""
        user = await _insert_user(async_session)
        token = _create_token(
            sub=str(user.id),
            expires_delta=timedelta(seconds=-10),
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(request=_mock_request(), token=token, session=async_session)

        assert exc_info.value.status_code == 401

    async def test_invalid_token_returns_401(
        self, async_session: AsyncSession
    ) -> None:
        """A completely invalid (garbage) token should raise HTTPException 401."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                request=_mock_request(), token="not.a.valid.jwt.token", session=async_session
            )

        assert exc_info.value.status_code == 401

    async def test_token_with_wrong_secret_returns_401(
        self, async_session: AsyncSession
    ) -> None:
        """A token signed with a different secret should raise 401."""
        user = await _insert_user(async_session)
        payload = {
            "sub": str(user.id),
            "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=15),
            "iat": datetime.now(tz=timezone.utc),
        }
        bad_token = jwt.encode(payload, "wrong-secret", algorithm=settings.JWT_ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(request=_mock_request(), token=bad_token, session=async_session)

        assert exc_info.value.status_code == 401

    @spec_ref("MVP-ADMIN-001", "AC-6")
    async def test_inactive_user_returns_401(
        self, async_session: AsyncSession
    ) -> None:
        """A valid token for an inactive user should raise HTTPException 401."""
        user = await _insert_user(async_session, is_active=False)
        token = _create_access_token(str(user.id))

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(request=_mock_request(), token=token, session=async_session)

        assert exc_info.value.status_code == 401

    async def test_deleted_user_returns_401(
        self, async_session: AsyncSession
    ) -> None:
        """A valid token for a soft-deleted user should raise HTTPException 401."""
        user = await _insert_user(async_session)
        # Soft-delete the user
        user.deleted_at = datetime.now(timezone.utc)
        await async_session.commit()

        token = _create_access_token(str(user.id))

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(request=_mock_request(), token=token, session=async_session)

        assert exc_info.value.status_code == 401

    async def test_nonexistent_user_returns_401(
        self, async_session: AsyncSession
    ) -> None:
        """A valid token for a user ID that does not exist should raise 401."""
        fake_id = str(uuid4())
        token = _create_access_token(fake_id)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(request=_mock_request(), token=token, session=async_session)

        assert exc_info.value.status_code == 401

    async def test_token_missing_sub_claim_returns_401(
        self, async_session: AsyncSession
    ) -> None:
        """A token without a 'sub' claim should raise 401."""
        payload = {
            "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=15),
            "iat": datetime.now(tz=timezone.utc),
        }
        token = jwt.encode(
            payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(request=_mock_request(), token=token, session=async_session)

        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Tests: require_role
# ---------------------------------------------------------------------------

class TestRequireRole:
    """Tests for the require_role dependency factory."""

    @spec_ref("MVP-ADMIN-002", "AC-6")
    async def test_matching_role_allows_access(
        self, async_session: AsyncSession
    ) -> None:
        """A user with a matching role should pass the check."""
        user = await _insert_user(async_session, role="super_admin")
        checker = require_role("super_admin")

        result = await checker(current_user=user)
        assert result.id == user.id

    async def test_multiple_allowed_roles(
        self, async_session: AsyncSession
    ) -> None:
        """A user with any of the allowed roles should pass."""
        user = await _insert_user(async_session, role="db_admin")
        checker = require_role("super_admin", "db_admin")

        result = await checker(current_user=user)
        assert result.id == user.id

    @spec_ref("MVP-ADMIN-002", "AC-6")
    async def test_wrong_role_raises_403(
        self, async_session: AsyncSession
    ) -> None:
        """A user with a non-matching role should get HTTPException 403."""
        user = await _insert_user(async_session, role="viewer")
        checker = require_role("super_admin")

        with pytest.raises(HTTPException) as exc_info:
            await checker(current_user=user)

        assert exc_info.value.status_code == 403
        assert "not authorized" in exc_info.value.detail

    async def test_operator_blocked_from_admin_endpoint(
        self, async_session: AsyncSession
    ) -> None:
        """An operator should be blocked from a super_admin-only endpoint."""
        user = await _insert_user(async_session, role="operator")
        checker = require_role("super_admin")

        with pytest.raises(HTTPException) as exc_info:
            await checker(current_user=user)

        assert exc_info.value.status_code == 403

    async def test_error_detail_includes_required_roles(
        self, async_session: AsyncSession
    ) -> None:
        """The 403 error detail should list the required roles."""
        user = await _insert_user(async_session, role="api_user")
        checker = require_role("super_admin", "db_admin")

        with pytest.raises(HTTPException) as exc_info:
            await checker(current_user=user)

        detail = exc_info.value.detail
        assert "super_admin" in detail
        assert "db_admin" in detail
