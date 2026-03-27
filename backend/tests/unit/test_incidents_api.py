# Spec: FS-DASH-004
"""Tests for Incident API endpoints (backend/app/api/v1/incidents.py).

Tests cover:
- list_incidents: empty list, with data, filter by severity (AC-1)
- get_incident: detail, not found (AC-1)
- update_incident_status: acknowledge, resolve, invalid transition (AC-3)
- RBAC: unauthenticated returns 401
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import _create_access_token, pwd_context
from app.models.db_instance import DBInstance
from app.models.incident import Incident
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
    role: str = "db_admin",
) -> User:
    """Insert a User directly into the test DB and return it."""
    user = User(
        id=uuid4(),
        email=f"inc-test-{uuid4().hex[:8]}@neuraldb.io",
        name="Incident Test User",
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
    """Insert a DBInstance for FK dependencies."""
    instance = DBInstance(
        id=uuid4(),
        name=f"pg-test-{uuid4().hex[:6]}",
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
    instance_id: "uuid4",
    severity: str = "warning",
    status: str = "open",
    title: str = "Test incident",
    source: str = "threshold",
) -> Incident:
    """Insert an Incident directly into the test DB."""
    incident = Incident(
        id=uuid4(),
        instance_id=instance_id,
        severity=severity,
        status=status,
        title=title,
        description="Test incident description",
        source=source,
        metric_type="cpu_usage",
        metric_value=95.0,
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
    """Create a db_admin user for authenticated requests."""
    return await _create_user_in_db(async_session, role="db_admin")


@pytest_asyncio.fixture
async def db_instance(async_session: AsyncSession) -> DBInstance:
    """Create a sample DB instance."""
    return await _create_db_instance(async_session)


# ---------------------------------------------------------------------------
# Tests: list_incidents
# ---------------------------------------------------------------------------

class TestListIncidents:
    """GET /api/v1/incidents"""

    @spec_ref("FS-DASH-004", "AC-1")
    async def test_list_incidents_empty(
        self, client: AsyncClient, auth_user: User
    ) -> None:
        """An empty incidents table returns an empty list with total 0."""
        resp = await client.get(
            "/api/v1/incidents",
            headers=_auth_header(str(auth_user.id)),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body
        assert body["total"] == 0
        assert body["items"] == []

    @spec_ref("FS-DASH-004", "AC-1")
    async def test_list_incidents_with_data(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
        auth_user: User,
        db_instance: DBInstance,
    ) -> None:
        """Creating an incident makes it appear in the listing."""
        incident = await _create_incident(
            async_session, instance_id=db_instance.id, severity="critical"
        )

        resp = await client.get(
            "/api/v1/incidents",
            headers=_auth_header(str(auth_user.id)),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        ids = [item["id"] for item in body["items"]]
        assert str(incident.id) in ids

    @spec_ref("FS-DASH-004", "AC-1")
    async def test_list_incidents_filter_by_severity(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
        auth_user: User,
        db_instance: DBInstance,
    ) -> None:
        """Filtering by severity only returns matching incidents."""
        await _create_incident(
            async_session, instance_id=db_instance.id, severity="critical"
        )
        await _create_incident(
            async_session, instance_id=db_instance.id, severity="warning"
        )

        resp = await client.get(
            "/api/v1/incidents",
            params={"severity": "critical"},
            headers=_auth_header(str(auth_user.id)),
        )
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert item["severity"] == "critical"


# ---------------------------------------------------------------------------
# Tests: get_incident
# ---------------------------------------------------------------------------

class TestGetIncident:
    """GET /api/v1/incidents/{incident_id}"""

    @spec_ref("FS-DASH-004", "AC-1")
    async def test_get_incident_detail(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
        auth_user: User,
        db_instance: DBInstance,
    ) -> None:
        """Fetching a single incident returns its full details."""
        incident = await _create_incident(
            async_session, instance_id=db_instance.id, title="CPU spike"
        )

        resp = await client.get(
            f"/api/v1/incidents/{incident.id}",
            headers=_auth_header(str(auth_user.id)),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(incident.id)
        assert body["title"] == "CPU spike"
        assert body["severity"] == incident.severity
        assert body["status"] == "open"

    @spec_ref("FS-DASH-004", "AC-1")
    async def test_get_incident_not_found(
        self, client: AsyncClient, auth_user: User
    ) -> None:
        """Fetching a non-existent incident returns 404."""
        fake_id = uuid4()
        resp = await client.get(
            f"/api/v1/incidents/{fake_id}",
            headers=_auth_header(str(auth_user.id)),
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["message"]


# ---------------------------------------------------------------------------
# Tests: update_incident_status
# ---------------------------------------------------------------------------

class TestUpdateIncidentStatus:
    """PUT /api/v1/incidents/{incident_id}/status"""

    @spec_ref("FS-DASH-004", "AC-3")
    async def test_update_incident_status_acknowledge(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
        auth_user: User,
        db_instance: DBInstance,
    ) -> None:
        """Acknowledging an open incident transitions status and sets acknowledged_at."""
        incident = await _create_incident(
            async_session, instance_id=db_instance.id, status="open"
        )

        resp = await client.put(
            f"/api/v1/incidents/{incident.id}/status",
            json={"status": "acknowledged"},
            headers=_auth_header(str(auth_user.id)),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "acknowledged"
        assert body["acknowledged_at"] is not None

    @spec_ref("FS-DASH-004", "AC-3")
    async def test_update_incident_status_resolve(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
        auth_user: User,
        db_instance: DBInstance,
    ) -> None:
        """Resolving an acknowledged incident transitions status and sets resolved_at."""
        incident = await _create_incident(
            async_session, instance_id=db_instance.id, status="acknowledged"
        )

        resp = await client.put(
            f"/api/v1/incidents/{incident.id}/status",
            json={"status": "resolved"},
            headers=_auth_header(str(auth_user.id)),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "resolved"
        assert body["resolved_at"] is not None

    @spec_ref("FS-DASH-004", "AC-3")
    async def test_update_incident_invalid_status(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
        auth_user: User,
        db_instance: DBInstance,
    ) -> None:
        """An invalid status transition returns 422."""
        incident = await _create_incident(
            async_session, instance_id=db_instance.id, status="resolved"
        )

        resp = await client.put(
            f"/api/v1/incidents/{incident.id}/status",
            json={"status": "acknowledged"},
            headers=_auth_header(str(auth_user.id)),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: RBAC / Auth
# ---------------------------------------------------------------------------

class TestIncidentsAuth:
    """Authentication requirements for incident endpoints."""

    @spec_ref("FS-DASH-004", "AC-1")
    async def test_incidents_require_auth(
        self, client: AsyncClient
    ) -> None:
        """Request without Authorization header returns 401."""
        resp = await client.get("/api/v1/incidents")
        assert resp.status_code == 401
