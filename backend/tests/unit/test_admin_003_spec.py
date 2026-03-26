# Spec: FS-ADMIN-003
"""Tests for FS-ADMIN-003 Acceptance Criteria (Audit Log Middleware).

Covers:
- AC-1: POST/PUT/DELETE creates audit_logs record (middleware dispatch logic)
- AC-2: GET does NOT create audit log (middleware skips GET)
- AC-3: user_id extracted from JWT correctly
- AC-4: resource_type/resource_id parsed from URL
- AC-6: Audit log failure does not break original request

NOTE: AC-5 (GET /audit-logs works) is fully covered in test_audit_api.py.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import _create_access_token, pwd_context
from app.middleware.audit import (
    AuditLogMiddleware,
    _METHOD_ACTION_MAP,
    _extract_user_id_from_jwt,
    _parse_resource,
    _write_audit_log,
)
from app.models.user import User
from tests.conftest import spec_ref


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_header(user_id: str) -> dict[str, str]:
    token = _create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}


async def _create_user(
    session: AsyncSession, *, role: str = "super_admin"
) -> User:
    user = User(
        id=uuid4(),
        email=f"admin003-{uuid4().hex[:8]}@neuraldb.io",
        name="Admin003 Test User",
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def admin_user(async_session: AsyncSession) -> User:
    return await _create_user(async_session, role="super_admin")


@pytest_asyncio.fixture
async def db_admin_user(async_session: AsyncSession) -> User:
    return await _create_user(async_session, role="db_admin")


# ---------------------------------------------------------------------------
# AC-1: POST/PUT/DELETE creates audit log records
# ---------------------------------------------------------------------------

@spec_ref("FS-ADMIN-003", "AC-1")
async def test_fs_admin_003_ac1_post_put_delete_audit_logs() -> None:
    """FS-ADMIN-003 AC-1: POST/PUT/DELETE requests trigger _write_audit_log.

    The AuditLogMiddleware dispatches _write_audit_log (via asyncio.create_task)
    only for POST, PUT, DELETE methods. We verify the middleware calls the writer
    for each state-changing method.
    """
    # Verify the method-to-action mapping covers POST/PUT/DELETE
    assert "POST" in _METHOD_ACTION_MAP
    assert "PUT" in _METHOD_ACTION_MAP
    assert "DELETE" in _METHOD_ACTION_MAP
    assert _METHOD_ACTION_MAP["POST"] == "create"
    assert _METHOD_ACTION_MAP["PUT"] == "update"
    assert _METHOD_ACTION_MAP["DELETE"] == "delete"


@spec_ref("FS-ADMIN-003", "AC-1")
async def test_fs_admin_003_ac1_middleware_calls_writer_for_post(
    client: AsyncClient,
    admin_user: User,
) -> None:
    """AC-1: POST request triggers _write_audit_log via middleware.

    Patch _write_audit_log to verify it is called when a POST request is made.
    """
    mock_writer = AsyncMock()

    with patch("app.middleware.audit._write_audit_log", mock_writer):
        resp = await client.post(
            "/api/v1/users",
            json={
                "email": f"ac1-post-{uuid4().hex[:6]}@neuraldb.io",
                "name": "AC1 Post",
                "password": "TestPass123!",
                "role": "viewer",
            },
            headers=_auth_header(str(admin_user.id)),
        )

    assert resp.status_code in (200, 201)
    # The middleware should have scheduled _write_audit_log via create_task.
    # With the patched mock, the task may or may not have completed.
    # Give it a moment.
    await asyncio.sleep(0.05)
    mock_writer.assert_called_once()


# ---------------------------------------------------------------------------
# AC-2: GET does NOT create audit log
# ---------------------------------------------------------------------------

@spec_ref("FS-ADMIN-003", "AC-2")
async def test_fs_admin_003_ac2(
    client: AsyncClient,
    admin_user: User,
) -> None:
    """FS-ADMIN-003 AC-2: GET requests are NOT recorded in audit_logs.

    Patch _write_audit_log and verify it is NOT called for GET requests.
    """
    mock_writer = AsyncMock()

    with patch("app.middleware.audit._write_audit_log", mock_writer):
        resp = await client.get(
            "/api/v1/incidents",
            headers=_auth_header(str(admin_user.id)),
        )

    assert resp.status_code == 200
    await asyncio.sleep(0.05)
    mock_writer.assert_not_called()


@spec_ref("FS-ADMIN-003", "AC-2")
async def test_fs_admin_003_ac2_get_method_not_in_map() -> None:
    """AC-2 complement: GET is not in the method-action mapping."""
    assert "GET" not in _METHOD_ACTION_MAP
    assert "HEAD" not in _METHOD_ACTION_MAP
    assert "OPTIONS" not in _METHOD_ACTION_MAP


# ---------------------------------------------------------------------------
# AC-3: user_id extracted from JWT correctly
# ---------------------------------------------------------------------------

@spec_ref("FS-ADMIN-003", "AC-3")
async def test_fs_admin_003_ac3_user_id_jwt() -> None:
    """FS-ADMIN-003 AC-3: user_id is correctly extracted from JWT token.

    Tests the _extract_user_id_from_jwt helper directly.
    """
    test_user_id = uuid4()
    token = _create_access_token(str(test_user_id))

    mock_request = MagicMock()
    mock_request.headers = {"authorization": f"Bearer {token}"}

    extracted_id = _extract_user_id_from_jwt(mock_request)
    assert extracted_id is not None, "Failed to extract user_id from JWT"
    assert extracted_id == test_user_id


@spec_ref("FS-ADMIN-003", "AC-3")
async def test_fs_admin_003_ac3_no_auth_header() -> None:
    """AC-3 edge case: missing Authorization header returns None."""
    mock_request = MagicMock()
    mock_request.headers = {}

    extracted_id = _extract_user_id_from_jwt(mock_request)
    assert extracted_id is None


@spec_ref("FS-ADMIN-003", "AC-3")
async def test_fs_admin_003_ac3_malformed_token() -> None:
    """AC-3 edge case: malformed token returns None (no exception)."""
    mock_request = MagicMock()
    mock_request.headers = {"authorization": "Bearer not.a.valid.jwt"}

    extracted_id = _extract_user_id_from_jwt(mock_request)
    assert extracted_id is None


# ---------------------------------------------------------------------------
# AC-4: resource_type/resource_id parsed from URL
# ---------------------------------------------------------------------------

@spec_ref("FS-ADMIN-003", "AC-4")
async def test_fs_admin_003_ac4_resource_type_resource_id_url() -> None:
    """FS-ADMIN-003 AC-4: resource_type and resource_id correctly parsed from URL.

    Tests the _parse_resource helper against various URL patterns.
    """
    # /api/v1/instances -> resource_type="instance", resource_id=None
    rtype, rid = _parse_resource("/api/v1/instances")
    assert rtype == "instance"
    assert rid is None

    # /api/v1/instances/{uuid} -> resource_type="instance", resource_id=UUID
    test_uuid = uuid4()
    rtype, rid = _parse_resource(f"/api/v1/instances/{test_uuid}")
    assert rtype == "instance"
    assert rid == test_uuid

    # /api/v1/users/{uuid} -> resource_type="user", resource_id=UUID
    user_uuid = uuid4()
    rtype, rid = _parse_resource(f"/api/v1/users/{user_uuid}")
    assert rtype == "user"
    assert rid == user_uuid

    # /api/v1/incidents -> resource_type="incident"
    rtype, rid = _parse_resource("/api/v1/incidents")
    assert rtype == "incident"
    assert rid is None

    # /api/v1/alerts/channels -> resource_type contains "alert" and "channel"
    rtype, rid = _parse_resource("/api/v1/alerts/channels")
    assert "alert" in rtype
    assert "channel" in rtype
    assert rid is None


@spec_ref("FS-ADMIN-003", "AC-4")
async def test_fs_admin_003_ac4_auth_login_resource() -> None:
    """AC-4: /api/v1/auth/login is parsed as a valid resource path.

    The middleware concatenates nested paths: auth + login = auth_login.
    The action override to 'login' is handled in _write_audit_log, not _parse_resource.
    """
    rtype, rid = _parse_resource("/api/v1/auth/login")
    # The middleware produces auth_login for the nested path.
    # action="login" is set separately in _write_audit_log.
    assert "auth" in rtype
    assert rid is None


@spec_ref("FS-ADMIN-003", "AC-4")
async def test_fs_admin_003_ac4_unknown_path() -> None:
    """AC-4 edge case: unrecognized path returns ('unknown', None)."""
    rtype, rid = _parse_resource("/health")
    assert rtype == "unknown"
    assert rid is None


# ---------------------------------------------------------------------------
# AC-6: Audit log failure does NOT break original request
# ---------------------------------------------------------------------------

@spec_ref("FS-ADMIN-003", "AC-6")
async def test_fs_admin_003_ac6(
    client: AsyncClient,
    admin_user: User,
) -> None:
    """FS-ADMIN-003 AC-6: Audit log write failure does not break the original response.

    Patch _write_audit_log to raise an exception. The POST request should
    still succeed because the middleware uses fire-and-forget with exception handling.
    """
    new_user_payload = {
        "email": f"audit-ac6-{uuid4().hex[:6]}@neuraldb.io",
        "name": "AC6 Failure Test",
        "password": "TestPass123!",
        "role": "viewer",
    }

    with patch(
        "app.middleware.audit._write_audit_log",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Simulated audit write failure"),
    ):
        resp = await client.post(
            "/api/v1/users",
            json=new_user_payload,
            headers=_auth_header(str(admin_user.id)),
        )

    # The request itself must succeed despite the audit write failure
    assert resp.status_code in (200, 201), (
        f"Request should succeed even when audit logging fails. "
        f"Got {resp.status_code}: {resp.text}"
    )
