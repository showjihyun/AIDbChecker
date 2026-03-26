# Spec: FS-DASH-004
"""Tests for FS-DASH-004 Acceptance Criteria (Incident List Page).

Covers:
- AC-2: severity color classes (frontend-only AC)
- AC-4: empty state returns empty items (backend API test)
- AC-5: WebSocket real-time incident (integration AC)
- AC-6: SideNav has incidents route (frontend-only AC)

NOTE: AC-1 (severity/status filter) and AC-3 (ACK/Resolve) are fully
covered in test_incidents_api.py with real assertions.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import _create_access_token, pwd_context
from app.models.db_instance import DBInstance
from app.models.incident import Incident
from app.models.user import User
from tests.conftest import spec_ref
from datetime import datetime, timezone

import pytest_asyncio


# ---------------------------------------------------------------------------
# Helpers (reused from test_incidents_api.py pattern)
# ---------------------------------------------------------------------------

def _auth_header(user_id: str) -> dict[str, str]:
    token = _create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}


async def _create_user(session: AsyncSession, *, role: str = "db_admin") -> User:
    user = User(
        id=uuid4(),
        email=f"dash004-{uuid4().hex[:8]}@neuraldb.io",
        name="Dash004 Test User",
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


async def _create_db_instance(session: AsyncSession) -> DBInstance:
    instance = DBInstance(
        id=uuid4(),
        name=f"pg-dash004-{uuid4().hex[:6]}",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="testdb",
        environment="development",
        connection_config={},
        is_active=True,
        autonomy_level=0,
    )
    session.add(instance)
    await session.commit()
    await session.refresh(instance)
    return instance


async def _create_incident(
    session: AsyncSession,
    *,
    instance_id,
    severity: str = "warning",
    status: str = "open",
) -> Incident:
    incident = Incident(
        id=uuid4(),
        instance_id=instance_id,
        severity=severity,
        status=status,
        title=f"Test {severity} incident",
        description="Test incident for dash-004 spec",
        source="threshold",
        metric_type="cpu_usage",
        metric_value=90.0,
        baseline_value=50.0,
        detected_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(incident)
    await session.commit()
    await session.refresh(incident)
    return incident


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def auth_user(async_session: AsyncSession) -> User:
    return await _create_user(async_session)


@pytest_asyncio.fixture
async def db_instance(async_session: AsyncSession) -> DBInstance:
    return await _create_db_instance(async_session)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@spec_ref("FS-DASH-004", "AC-2")
async def test_fs_dash_004_ac2_severity():
    """FS-DASH-004 AC-2: severity color classes are a frontend (React/TailwindCSS) concern.

    The backend provides severity as a string field (critical/warning/notice/info)
    in the API response. Color mapping happens in IncidentRow.tsx using design tokens.
    """
    pytest.skip("Frontend AC -- requires Vitest (severity color classes are CSS/React)")


@spec_ref("FS-DASH-004", "AC-4")
async def test_fs_dash_004_ac4_emptystate(
    client: AsyncClient,
    auth_user: User,
) -> None:
    """FS-DASH-004 AC-4: when no incidents exist, API returns empty items list.

    The frontend EmptyState component renders based on items being empty.
    This test validates the backend contract that enables that behavior.
    """
    resp = await client.get(
        "/api/v1/incidents",
        headers=_auth_header(str(auth_user.id)),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0


@spec_ref("FS-DASH-004", "AC-5")
async def test_fs_dash_004_ac5_websocket():
    """FS-DASH-004 AC-5: WebSocket pushes new incidents in real-time.

    Requires a live Socket.io server with /ws/incidents namespace
    and incident:new event handling. Cannot be tested with httpx alone.
    """
    pytest.skip(
        "Integration test -- requires live Socket.io server "
        "(/ws/incidents namespace with incident:new event)"
    )


@spec_ref("FS-DASH-004", "AC-6")
async def test_fs_dash_004_ac6_sidenav_incidents():
    """FS-DASH-004 AC-6: SideNav includes an Incidents menu item with /incidents route.

    This is a frontend-only AC. The backend confirms that the /api/v1/incidents
    route is registered and accessible. SideNav rendering is tested via Vitest.
    """
    pytest.skip("Frontend AC -- requires Vitest (SideNav component rendering)")
