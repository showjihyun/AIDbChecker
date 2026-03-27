# Spec: MVP-ADMIN-001, MVP-ADMIN-002, MVP-ADMIN-003
"""Integration tests for User CRUD API endpoints (backend/app/api/v1/users.py).

Tests cover:
- list_users: empty list, populated list
- create_user: happy path (201), duplicate email (409), invalid role (422)
- update_user: update name (200), update password, user not found (404)
- delete_user: soft delete (204), not found (404)
- RBAC: non-super_admin gets 403 on all user management endpoints
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import _create_access_token, pwd_context
from app.models.user import User
from tests.conftest import spec_ref


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_header(user_id: str) -> dict[str, str]:
    """Create an Authorization header with a valid JWT for the given user ID."""
    token = _create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}


async def _create_user_in_db(
    session: AsyncSession,
    *,
    email: str = "admin@neuraldb.io",
    name: str = "Admin",
    role: str = "super_admin",
    password: str = "TestPass123!",
    is_active: bool = True,
) -> User:
    """Insert a User directly into the test DB and return it."""
    user = User(
        id=uuid4(),
        email=email,
        name=name,
        hashed_password=pwd_context.hash(password),
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
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def admin_user(async_session: AsyncSession) -> User:
    """Create a super_admin user for authenticated requests."""
    return await _create_user_in_db(
        async_session,
        email=f"admin-{uuid4().hex[:8]}@neuraldb.io",
        name="Test Admin",
        role="super_admin",
    )


@pytest_asyncio.fixture
async def viewer_user(async_session: AsyncSession) -> User:
    """Create a viewer user for RBAC-denied requests."""
    return await _create_user_in_db(
        async_session,
        email=f"viewer-{uuid4().hex[:8]}@neuraldb.io",
        name="Test Viewer",
        role="viewer",
    )


# ---------------------------------------------------------------------------
# Tests: list_users
# ---------------------------------------------------------------------------

class TestListUsers:
    """GET /api/v1/users"""

    @spec_ref("MVP-ADMIN-002", "AC-6")
    async def test_list_users_returns_items_and_total(
        self, client: AsyncClient, admin_user: User
    ) -> None:
        """Listing users should return at least the admin user itself."""
        resp = await client.get(
            "/api/v1/users", headers=_auth_header(str(admin_user.id))
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body
        assert body["total"] >= 1
        emails = [u["email"] for u in body["items"]]
        assert admin_user.email in emails

    async def test_list_users_excludes_soft_deleted(
        self, client: AsyncClient, async_session: AsyncSession, admin_user: User
    ) -> None:
        """Soft-deleted users should not appear in the listing."""
        deleted = await _create_user_in_db(
            async_session,
            email=f"deleted-{uuid4().hex[:8]}@neuraldb.io",
            name="Deleted User",
        )
        # Soft-delete
        deleted.deleted_at = datetime.now(timezone.utc)
        deleted.is_active = False
        await async_session.commit()

        resp = await client.get(
            "/api/v1/users", headers=_auth_header(str(admin_user.id))
        )
        assert resp.status_code == 200
        emails = [u["email"] for u in resp.json()["items"]]
        assert deleted.email not in emails


# ---------------------------------------------------------------------------
# Tests: create_user
# ---------------------------------------------------------------------------

class TestCreateUser:
    """POST /api/v1/users"""

    @spec_ref("MVP-ADMIN-002", "AC-6")
    async def test_create_user_success(
        self, client: AsyncClient, admin_user: User
    ) -> None:
        """Creating a user with valid data returns 201 and the user object."""
        payload = {
            "email": f"new-{uuid4().hex[:8]}@neuraldb.io",
            "name": "New User",
            "password": "SecurePass1!",
            "role": "db_admin",
        }
        resp = await client.post(
            "/api/v1/users",
            json=payload,
            headers=_auth_header(str(admin_user.id)),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == payload["email"]
        assert body["name"] == payload["name"]
        assert body["role"] == "db_admin"
        assert body["is_active"] is True
        assert "id" in body
        # Password must not be in the response
        assert "password" not in body
        assert "hashed_password" not in body

    async def test_create_user_duplicate_email_returns_409(
        self, client: AsyncClient, admin_user: User
    ) -> None:
        """Creating a user with an existing email returns 409 Conflict."""
        payload = {
            "email": admin_user.email,
            "name": "Duplicate",
            "password": "SecurePass1!",
            "role": "viewer",
        }
        resp = await client.post(
            "/api/v1/users",
            json=payload,
            headers=_auth_header(str(admin_user.id)),
        )
        assert resp.status_code == 409
        assert "already exists" in resp.json()["message"]

    async def test_create_user_invalid_role_returns_422(
        self, client: AsyncClient, admin_user: User
    ) -> None:
        """Creating a user with an invalid role returns 422 validation error."""
        payload = {
            "email": f"bad-role-{uuid4().hex[:8]}@neuraldb.io",
            "name": "Bad Role",
            "password": "SecurePass1!",
            "role": "root",  # not in allowlist
        }
        resp = await client.post(
            "/api/v1/users",
            json=payload,
            headers=_auth_header(str(admin_user.id)),
        )
        assert resp.status_code == 422

    async def test_create_user_short_password_returns_422(
        self, client: AsyncClient, admin_user: User
    ) -> None:
        """Creating a user with a password shorter than 8 chars returns 422."""
        payload = {
            "email": f"short-{uuid4().hex[:8]}@neuraldb.io",
            "name": "Short PW",
            "password": "abc",
            "role": "viewer",
        }
        resp = await client.post(
            "/api/v1/users",
            json=payload,
            headers=_auth_header(str(admin_user.id)),
        )
        assert resp.status_code == 422

    async def test_create_user_invalid_email_returns_422(
        self, client: AsyncClient, admin_user: User
    ) -> None:
        """Creating a user with a malformed email returns 422."""
        payload = {
            "email": "not-an-email",
            "name": "Bad Email",
            "password": "SecurePass1!",
            "role": "viewer",
        }
        resp = await client.post(
            "/api/v1/users",
            json=payload,
            headers=_auth_header(str(admin_user.id)),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: update_user
# ---------------------------------------------------------------------------

class TestUpdateUser:
    """PUT /api/v1/users/{user_id}"""

    async def test_update_user_name(
        self, client: AsyncClient, async_session: AsyncSession, admin_user: User
    ) -> None:
        """Updating a user's name returns 200 and the updated name."""
        target = await _create_user_in_db(
            async_session,
            email=f"update-name-{uuid4().hex[:8]}@neuraldb.io",
            name="Old Name",
            role="viewer",
        )
        resp = await client.put(
            f"/api/v1/users/{target.id}",
            json={"name": "New Name"},
            headers=_auth_header(str(admin_user.id)),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    async def test_update_user_password(
        self, client: AsyncClient, async_session: AsyncSession, admin_user: User
    ) -> None:
        """Updating a user's password returns 200 (password is hashed internally)."""
        target = await _create_user_in_db(
            async_session,
            email=f"update-pw-{uuid4().hex[:8]}@neuraldb.io",
            name="PW User",
            role="operator",
            password="OldPassword1!",
        )
        resp = await client.put(
            f"/api/v1/users/{target.id}",
            json={"password": "NewPassword1!"},
            headers=_auth_header(str(admin_user.id)),
        )
        assert resp.status_code == 200

        # Verify the password was actually changed by refreshing from DB
        await async_session.refresh(target)
        assert pwd_context.verify("NewPassword1!", target.hashed_password) is True
        assert pwd_context.verify("OldPassword1!", target.hashed_password) is False

    async def test_update_user_role(
        self, client: AsyncClient, async_session: AsyncSession, admin_user: User
    ) -> None:
        """Updating a user's role returns 200 and the new role."""
        target = await _create_user_in_db(
            async_session,
            email=f"update-role-{uuid4().hex[:8]}@neuraldb.io",
            name="Role User",
            role="viewer",
        )
        resp = await client.put(
            f"/api/v1/users/{target.id}",
            json={"role": "operator"},
            headers=_auth_header(str(admin_user.id)),
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "operator"

    async def test_update_user_not_found_returns_404(
        self, client: AsyncClient, admin_user: User
    ) -> None:
        """Updating a non-existent user returns 404."""
        fake_id = uuid4()
        resp = await client.put(
            f"/api/v1/users/{fake_id}",
            json={"name": "Ghost"},
            headers=_auth_header(str(admin_user.id)),
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["message"]


# ---------------------------------------------------------------------------
# Tests: delete_user
# ---------------------------------------------------------------------------

class TestDeleteUser:
    """DELETE /api/v1/users/{user_id}"""

    async def test_soft_delete_user_returns_204(
        self, client: AsyncClient, async_session: AsyncSession, admin_user: User
    ) -> None:
        """Soft-deleting an existing user returns 204 No Content."""
        target = await _create_user_in_db(
            async_session,
            email=f"delete-{uuid4().hex[:8]}@neuraldb.io",
            name="To Delete",
            role="viewer",
        )
        resp = await client.delete(
            f"/api/v1/users/{target.id}",
            headers=_auth_header(str(admin_user.id)),
        )
        assert resp.status_code == 204

        # Verify soft delete: deleted_at is set, is_active is False
        await async_session.refresh(target)
        assert target.deleted_at is not None
        assert target.is_active is False

    async def test_delete_user_not_found_returns_404(
        self, client: AsyncClient, admin_user: User
    ) -> None:
        """Deleting a non-existent user returns 404."""
        fake_id = uuid4()
        resp = await client.delete(
            f"/api/v1/users/{fake_id}",
            headers=_auth_header(str(admin_user.id)),
        )
        assert resp.status_code == 404

    async def test_delete_already_deleted_user_returns_404(
        self, client: AsyncClient, async_session: AsyncSession, admin_user: User
    ) -> None:
        """Deleting an already soft-deleted user returns 404."""
        target = await _create_user_in_db(
            async_session,
            email=f"double-del-{uuid4().hex[:8]}@neuraldb.io",
            name="Double Delete",
            role="viewer",
        )
        # First delete
        resp = await client.delete(
            f"/api/v1/users/{target.id}",
            headers=_auth_header(str(admin_user.id)),
        )
        assert resp.status_code == 204

        # Second delete should 404
        resp = await client.delete(
            f"/api/v1/users/{target.id}",
            headers=_auth_header(str(admin_user.id)),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: RBAC — non-super_admin gets 403
# ---------------------------------------------------------------------------

class TestRBAC:
    """All user management endpoints require super_admin role."""

    @spec_ref("MVP-ADMIN-002", "AC-6")
    async def test_list_users_as_viewer_returns_403(
        self, client: AsyncClient, viewer_user: User
    ) -> None:
        resp = await client.get(
            "/api/v1/users", headers=_auth_header(str(viewer_user.id))
        )
        assert resp.status_code == 403
        assert "not authorized" in resp.json()["message"]

    async def test_create_user_as_viewer_returns_403(
        self, client: AsyncClient, viewer_user: User
    ) -> None:
        payload = {
            "email": "forbidden@neuraldb.io",
            "name": "Forbidden",
            "password": "SecurePass1!",
            "role": "viewer",
        }
        resp = await client.post(
            "/api/v1/users",
            json=payload,
            headers=_auth_header(str(viewer_user.id)),
        )
        assert resp.status_code == 403

    async def test_update_user_as_operator_returns_403(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        operator = await _create_user_in_db(
            async_session,
            email=f"op-{uuid4().hex[:8]}@neuraldb.io",
            name="Operator",
            role="operator",
        )
        resp = await client.put(
            f"/api/v1/users/{operator.id}",
            json={"name": "Hacked"},
            headers=_auth_header(str(operator.id)),
        )
        assert resp.status_code == 403

    async def test_delete_user_as_db_admin_returns_403(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        db_admin = await _create_user_in_db(
            async_session,
            email=f"dba-{uuid4().hex[:8]}@neuraldb.io",
            name="DBA",
            role="db_admin",
        )
        resp = await client.delete(
            f"/api/v1/users/{db_admin.id}",
            headers=_auth_header(str(db_admin.id)),
        )
        assert resp.status_code == 403

    @spec_ref("MVP-ADMIN-001", "AC-6")
    async def test_unauthenticated_request_returns_401(
        self, client: AsyncClient
    ) -> None:
        """Request without Authorization header returns 401."""
        resp = await client.get("/api/v1/users")
        assert resp.status_code == 401
