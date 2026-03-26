# Spec: FS-ADMIN-003
"""Tests for Audit Log API endpoints (backend/app/api/v1/audit.py).

Tests cover:
- list_audit_logs: returns items+total (AC-5)
- RBAC: viewer gets 403 (AC-5)
- filter by resource_type (AC-5)
- filter by date range (AC-5)
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import _create_access_token, pwd_context
from app.models.audit_log import AuditLog
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
    email: str | None = None,
    name: str = "Test User",
    role: str = "super_admin",
) -> User:
    """Insert a User directly into the test DB and return it."""
    user = User(
        id=uuid4(),
        email=email or f"audit-test-{uuid4().hex[:8]}@neuraldb.io",
        name=name,
        hashed_password=pwd_context.hash("TestPass123!"),
        role=role,
        auth_provider="local",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _create_audit_log(
    session: AsyncSession,
    *,
    user_id: "uuid4 | None" = None,
    action: str = "create",
    resource_type: str = "instance",
    resource_id: "uuid4 | None" = None,
    details: dict | None = None,
    created_at: datetime | None = None,
) -> AuditLog:
    """Insert an AuditLog directly into the test DB."""
    log = AuditLog(
        id=uuid4(),
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id or uuid4(),
        details=details or {"method": "POST", "path": "/api/v1/instances"},
        ip_address="127.0.0.1",
        user_agent="test-agent",
        created_at=created_at or datetime.now(timezone.utc),
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def admin_user(async_session: AsyncSession) -> User:
    """Create a super_admin user for authenticated requests."""
    return await _create_user_in_db(async_session, role="super_admin")


@pytest_asyncio.fixture
async def viewer_user(async_session: AsyncSession) -> User:
    """Create a viewer user for RBAC-denied requests."""
    return await _create_user_in_db(async_session, role="viewer")


# ---------------------------------------------------------------------------
# Tests: list_audit_logs
# ---------------------------------------------------------------------------

class TestListAuditLogs:
    """GET /api/v1/audit-logs"""

    @spec_ref("FS-ADMIN-003", "AC-5")
    async def test_list_audit_logs_as_super_admin(
        self, client: AsyncClient, async_session: AsyncSession, admin_user: User
    ) -> None:
        """Super admin can list audit logs and sees items + total."""
        # Create some audit logs
        await _create_audit_log(async_session, user_id=admin_user.id)
        await _create_audit_log(
            async_session, user_id=admin_user.id, action="update", resource_type="user"
        )

        resp = await client.get(
            "/api/v1/audit-logs",
            headers=_auth_header(str(admin_user.id)),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body
        assert body["total"] >= 2
        assert len(body["items"]) >= 2

    @spec_ref("FS-ADMIN-003", "AC-5")
    async def test_list_audit_logs_as_viewer_returns_403(
        self, client: AsyncClient, viewer_user: User
    ) -> None:
        """Viewer role is denied access to audit logs."""
        resp = await client.get(
            "/api/v1/audit-logs",
            headers=_auth_header(str(viewer_user.id)),
        )
        assert resp.status_code == 403

    @spec_ref("FS-ADMIN-003", "AC-5")
    async def test_audit_log_filters_by_resource_type(
        self, client: AsyncClient, async_session: AsyncSession, admin_user: User
    ) -> None:
        """Filtering by resource_type only returns matching logs."""
        await _create_audit_log(
            async_session, user_id=admin_user.id, resource_type="instance"
        )
        await _create_audit_log(
            async_session, user_id=admin_user.id, resource_type="user"
        )

        resp = await client.get(
            "/api/v1/audit-logs",
            params={"resource_type": "instance"},
            headers=_auth_header(str(admin_user.id)),
        )
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert item["resource_type"] == "instance"

    @spec_ref("FS-ADMIN-003", "AC-5")
    async def test_audit_log_filters_by_date_range(
        self, client: AsyncClient, async_session: AsyncSession, admin_user: User
    ) -> None:
        """Filtering by from_ts/to_ts restricts results to that time window."""
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(days=10)
        recent_time = now - timedelta(hours=1)

        # Old log (outside range)
        await _create_audit_log(
            async_session,
            user_id=admin_user.id,
            resource_type="instance",
            created_at=old_time,
        )
        # Recent log (inside range)
        recent_log = await _create_audit_log(
            async_session,
            user_id=admin_user.id,
            resource_type="user",
            created_at=recent_time,
        )

        from_ts = (now - timedelta(days=1)).isoformat()
        to_ts = now.isoformat()

        resp = await client.get(
            "/api/v1/audit-logs",
            params={"from_ts": from_ts, "to_ts": to_ts},
            headers=_auth_header(str(admin_user.id)),
        )
        assert resp.status_code == 200
        body = resp.json()
        # All returned items should be within the date range
        ids = [item["id"] for item in body["items"]]
        assert str(recent_log.id) in ids
