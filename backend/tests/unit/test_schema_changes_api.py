# Spec: FS-SCHEMA-001
"""Tests for Schema Changes API endpoints (backend/app/api/v1/schema_changes.py).

Tests cover:
- list_schema_changes: empty list, with data, filter by change_type (AC-4)
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import _create_access_token, pwd_context
from app.models.db_instance import DBInstance
from app.models.schema_change import SchemaChange
from app.models.user import User


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
        email=f"schema-test-{uuid4().hex[:8]}@neuraldb.io",
        name="Schema Test User",
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
        name=f"pg-schema-{uuid4().hex[:6]}",
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


async def _create_schema_change(
    session: AsyncSession,
    *,
    instance_id: "uuid4",
    change_type: str = "CREATE",
    object_type: str = "TABLE",
    object_name: str = "test_table",
    ddl_command: str | None = None,
) -> SchemaChange:
    """Insert a SchemaChange directly into the test DB."""
    change = SchemaChange(
        id=uuid4(),
        instance_id=instance_id,
        change_type=change_type,
        object_type=object_type,
        object_name=object_name,
        ddl_command=ddl_command or f"{change_type} {object_type} {object_name}",
        before_state=None,
        after_state={"columns": ["id", "name"]},
        executed_by="postgres",
        detected_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    session.add(change)
    await session.commit()
    await session.refresh(change)
    return change


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
# Tests: list_schema_changes
# ---------------------------------------------------------------------------

class TestListSchemaChanges:
    """GET /api/v1/instances/{instance_id}/schema-changes"""

    # Spec: FS-SCHEMA-001 AC-4
    async def test_list_schema_changes_empty(
        self,
        client: AsyncClient,
        auth_user: User,
        db_instance: DBInstance,
    ) -> None:
        """An instance with no schema changes returns an empty list."""
        resp = await client.get(
            f"/api/v1/instances/{db_instance.id}/schema-changes",
            headers=_auth_header(str(auth_user.id)),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body
        assert body["total"] == 0
        assert body["items"] == []

    # Spec: FS-SCHEMA-001 AC-4
    async def test_list_schema_changes_with_data(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
        auth_user: User,
        db_instance: DBInstance,
    ) -> None:
        """Creating a schema change makes it appear in the listing."""
        change = await _create_schema_change(
            async_session,
            instance_id=db_instance.id,
            change_type="CREATE",
            object_type="TABLE",
            object_name="new_users",
        )

        resp = await client.get(
            f"/api/v1/instances/{db_instance.id}/schema-changes",
            headers=_auth_header(str(auth_user.id)),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        ids = [item["id"] for item in body["items"]]
        assert str(change.id) in ids
        # Verify fields
        item = next(i for i in body["items"] if i["id"] == str(change.id))
        assert item["change_type"] == "CREATE"
        assert item["object_type"] == "TABLE"
        assert item["object_name"] == "new_users"

    # Spec: FS-SCHEMA-001 AC-4
    async def test_list_schema_changes_filter_by_type(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
        auth_user: User,
        db_instance: DBInstance,
    ) -> None:
        """Filtering by change_type only returns matching schema changes."""
        await _create_schema_change(
            async_session,
            instance_id=db_instance.id,
            change_type="CREATE",
            object_name="table_a",
        )
        await _create_schema_change(
            async_session,
            instance_id=db_instance.id,
            change_type="ALTER",
            object_type="COLUMN",
            object_name="table_b.email",
        )
        await _create_schema_change(
            async_session,
            instance_id=db_instance.id,
            change_type="DROP",
            object_type="INDEX",
            object_name="idx_old",
        )

        resp = await client.get(
            f"/api/v1/instances/{db_instance.id}/schema-changes",
            params={"change_type": "ALTER"},
            headers=_auth_header(str(auth_user.id)),
        )
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert item["change_type"] == "ALTER"

    # Spec: FS-SCHEMA-001 AC-4
    async def test_list_schema_changes_nonexistent_instance_returns_404(
        self,
        client: AsyncClient,
        auth_user: User,
    ) -> None:
        """Querying schema changes for a non-existent instance returns 404."""
        fake_id = uuid4()
        resp = await client.get(
            f"/api/v1/instances/{fake_id}/schema-changes",
            headers=_auth_header(str(auth_user.id)),
        )
        assert resp.status_code == 404
