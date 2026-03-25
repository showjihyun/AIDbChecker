# Spec: MVP-AI-001, MVP-AI-002
"""Unit tests for Baselines API — list, retrain, and auth enforcement.

Uses httpx AsyncClient with FastAPI test overrides. Requires authenticated
user (JWT) since baselines routes are protected.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import _create_access_token, pwd_context
from app.models.db_instance import DBInstance
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth_header(user_id: str) -> dict[str, str]:
    """Create an Authorization header with a valid JWT for the given user ID."""
    token = _create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}


async def _create_test_user(session: AsyncSession) -> User:
    """Insert a test User into the DB for authentication."""
    user = User(
        id=uuid4(),
        email=f"baseline-test-{uuid4().hex[:8]}@neuraldb.io",
        name="Baseline Tester",
        hashed_password=pwd_context.hash("TestPass123!"),
        role="super_admin",
        auth_provider="local",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _create_test_instance(session: AsyncSession) -> DBInstance:
    """Insert a uniquely-named DBInstance into the DB."""
    instance = DBInstance(
        id=uuid4(),
        name=f"test-baseline-{uuid4().hex[:8]}",
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


class TestBaselinesAPI:
    """Tests for baselines API endpoints."""

    @pytest.mark.asyncio
    async def test_list_baselines_empty(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """GET /instances/{id}/baselines returns empty list when no baselines exist."""
        user = await _create_test_user(async_session)
        instance = await _create_test_instance(async_session)
        headers = _auth_header(str(user.id))

        response = await client.get(
            f"/api/v1/instances/{instance.id}/baselines",
            headers=headers,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["total"] == 0

    @pytest.mark.asyncio
    async def test_retrain_returns_202(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """POST /instances/{id}/baselines/retrain returns 202 Accepted."""
        user = await _create_test_user(async_session)
        instance = await _create_test_instance(async_session)
        headers = _auth_header(str(user.id))

        # The retrain endpoint does a lazy import:
        #   from app.tasks.analyze import retrain_baselines
        # We patch that module-level name so the import resolves to our mock.
        mock_celery_task = MagicMock()
        mock_celery_task.delay.return_value = MagicMock(id="mock-task-id-123")

        with patch.dict(
            "sys.modules",
            {},
        ), patch(
            "app.tasks.analyze.retrain_baselines",
            mock_celery_task,
            create=True,
        ):
            response = await client.post(
                f"/api/v1/instances/{instance.id}/baselines/retrain",
                headers=headers,
            )

        assert response.status_code == 202
        body = response.json()
        assert "retrain" in body["message"].lower()
        assert body["instance_id"] == str(instance.id)
        assert body["task_id"] == "mock-task-id-123"

    @pytest.mark.asyncio
    async def test_baselines_require_auth(self) -> None:
        """Baselines endpoints return 401 when no auth token is provided."""
        from app.main import app as fastapi_app

        # Clear dependency overrides to test real auth enforcement
        saved_overrides = dict(fastapi_app.dependency_overrides)
        fastapi_app.dependency_overrides.clear()

        try:
            transport = ASGITransport(app=fastapi_app)
            async with AsyncClient(transport=transport, base_url="http://test") as raw:
                instance_id = uuid4()
                response = await raw.get(
                    f"/api/v1/instances/{instance_id}/baselines"
                )
                assert response.status_code in (401, 403)
        finally:
            fastapi_app.dependency_overrides.update(saved_overrides)
