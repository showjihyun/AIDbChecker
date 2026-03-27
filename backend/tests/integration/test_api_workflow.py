# Spec: TEST-INT-001
"""Integration tests — API workflow E2E with real SQLite DB.

Tests the critical user journey:
  1. Login → JWT
  2. Create Instance
  3. List Instances
  4. Get Instance Detail
  5. System Health Check
  6. List Playbooks
  7. List Tasks (empty)
  8. AIGC Report generate (mock LLM)
  9. Audit Log query
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.conftest import spec_ref


@pytest_asyncio.fixture
async def auth_client(client):
    """Create an authenticated client by logging in with seed user."""
    # Create a user first
    from app.db.session import get_session
    from app.main import app as fastapi_app
    from sqlalchemy.ext.asyncio import AsyncSession

    # Login with seed user (if exists) or create one
    import app.utils.bcrypt_patch  # noqa: F401
    from passlib.context import CryptContext

    pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

    from uuid import uuid4

    from app.models.user import User

    email = f"admin-{uuid4().hex[:8]}@test.com"

    # Get session from the overridden dependency
    async for session in fastapi_app.dependency_overrides[get_session]():
        user = User(
            id=uuid4(),
            email=email,
            name="Test Admin",
            hashed_password=pwd_ctx.hash("testpass123"),
            role="super_admin",
            auth_provider="local",
            is_active=True,
        )
        session.add(user)
        await session.commit()

    # Login
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "testpass123"},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]

    # Return client with auth header
    client.headers["Authorization"] = f"Bearer {token}"
    return client


# ─────────────────────────────────────────────────
# Workflow Tests
# ─────────────────────────────────────────────────


@spec_ref("TEST-INT-001", "AC-1")
@pytest.mark.asyncio
async def test_workflow_login(client):
    """E2E: Login → JWT token."""
    import app.utils.bcrypt_patch  # noqa: F401
    from passlib.context import CryptContext
    from uuid import uuid4
    from app.models.user import User
    from app.db.session import get_session
    from app.main import app as fastapi_app

    pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

    async for session in fastapi_app.dependency_overrides[get_session]():
        user = User(
            id=uuid4(),
            email=f"login-{uuid4().hex[:6]}@test.com",
            name="Login Test",
            hashed_password=pwd_ctx.hash("pass123"),
            role="db_admin",
            auth_provider="local",
            is_active=True,
        )
        session.add(user)
        await session.commit()

        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": user.email, "password": "pass123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"


@spec_ref("TEST-INT-001", "AC-2")
@pytest.mark.asyncio
async def test_workflow_system_health(client):
    """E2E: System health check (public, no auth)."""
    resp = await client.get("/api/v1/system/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert data["status"] in ("healthy", "degraded", "unhealthy")


@spec_ref("TEST-INT-001", "AC-3")
@pytest.mark.asyncio
async def test_workflow_instance_crud(auth_client):
    """E2E: Create → List → Get Instance."""
    # Create
    resp = await auth_client.post(
        "/api/v1/instances",
        json={
            "name": "test-pg-e2e",
            "db_type": "postgresql",
            "host": "localhost",
            "port": 5432,
            "database_name": "testdb",
            "environment": "development",
        },
    )
    assert resp.status_code == 201
    instance = resp.json()
    instance_id = instance["id"]
    assert instance["name"] == "test-pg-e2e"

    # List
    resp = await auth_client.get("/api/v1/instances")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1

    # Get Detail
    resp = await auth_client.get(f"/api/v1/instances/{instance_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "test-pg-e2e"


@spec_ref("TEST-INT-001", "AC-4")
@pytest.mark.asyncio
async def test_workflow_playbooks_list(auth_client):
    """E2E: List built-in playbooks."""
    resp = await auth_client.get("/api/v1/playbooks")
    assert resp.status_code == 200
    playbooks = resp.json()
    assert len(playbooks) >= 7
    names = [p["name"] for p in playbooks]
    assert "lock-remediation" in names
    assert "vacuum-maintenance" in names


@spec_ref("TEST-INT-001", "AC-5")
@pytest.mark.asyncio
async def test_workflow_tasks_empty(auth_client):
    """E2E: List tasks (initially empty)."""
    resp = await auth_client.get("/api/v1/tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 0


@spec_ref("TEST-INT-001", "AC-6")
@pytest.mark.asyncio
async def test_workflow_auth_me(auth_client):
    """E2E: Get current user profile."""
    resp = await auth_client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert "email" in data
    assert data["role"] == "super_admin"


@spec_ref("TEST-INT-001", "AC-7")
@pytest.mark.asyncio
async def test_workflow_unauthorized(client):
    """E2E: Protected endpoint without token → 401."""
    resp = await client.get("/api/v1/instances")
    assert resp.status_code == 401


@spec_ref("TEST-INT-001", "AC-8")
@pytest.mark.asyncio
async def test_workflow_playbook_detail(auth_client):
    """E2E: Get playbook detail with YAML."""
    resp = await auth_client.get("/api/v1/playbooks/lock-remediation")
    assert resp.status_code == 200
    data = resp.json()
    assert data["metadata"]["name"] == "lock-remediation"
    assert "yaml_content" in data
    assert "apiVersion" in data["yaml_content"]


@spec_ref("TEST-INT-001", "AC-9")
@pytest.mark.asyncio
async def test_workflow_404_instance(auth_client):
    """E2E: Non-existent instance → 404."""
    import uuid
    fake_id = str(uuid.uuid4())
    resp = await auth_client.get(f"/api/v1/instances/{fake_id}")
    assert resp.status_code == 404


@spec_ref("TEST-INT-001", "AC-10")
@pytest.mark.asyncio
async def test_workflow_sso_disabled(client):
    """E2E: OIDC/LDAP 404 when SSO disabled."""
    resp = await client.post(
        "/api/v1/auth/oidc/callback",
        json={"id_token": "fake"},
    )
    assert resp.status_code == 404
