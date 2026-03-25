# Spec: BACKEND_TEST_SPEC
"""Shared pytest fixtures for NeuralDB backend tests.

Provides:
- async_session: SQLAlchemy async session bound to a test-scoped PostgreSQL or SQLite DB
- client: httpx.AsyncClient wired to the FastAPI app with overridden DB session
- sample_instance: a pre-created DBInstance for use in tests
"""

import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base
from app.db.session import get_session
from app.models.db_instance import DBInstance

# Import all models so Base.metadata is populated (Alembic-style).
# This import triggers pgvector Vector type registration.
# NOTE: Must come BEFORE the FastAPI app import to avoid namespace collision.
import app.models  # noqa: F401

# Import the FastAPI application instance. Use alias to avoid collision
# with the `app` package that was just imported on the line above.
from app.main import app as fastapi_app


# Use an in-memory SQLite for unit tests (fast, no external deps).
# For integration tests, override TEST_DATABASE_URL to point to a real PostgreSQL.
TEST_DATABASE_URL = "sqlite+aiosqlite:///file::memory:?cache=shared&uri=true"

_IS_SQLITE = "sqlite" in TEST_DATABASE_URL

# PostgreSQL-only column types that SQLite cannot handle at all.
# Tables containing these types must be skipped entirely during table creation.
_PG_ONLY_TYPE_NAMES = {"VECTOR", "ARRAY"}


def _apply_sqlite_jsonb_workaround() -> None:
    """Register a compile-time rule so JSONB columns emit as JSON on SQLite.

    SQLAlchemy's JSON type stores values as TEXT, which is sufficient for tests.
    ARRAY and VECTOR types have no viable SQLite mapping, so those tables are
    skipped instead (see _sqlite_compatible_tables).
    """
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy.ext.compiler import compiles

    @compiles(JSONB, "sqlite")
    def _compile_jsonb_sqlite(type_, compiler, **kw):  # type: ignore[no-untyped-def]
        return "JSON"


if _IS_SQLITE:
    _apply_sqlite_jsonb_workaround()


_test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    # SQLite needs these for async
    connect_args={"check_same_thread": False} if _IS_SQLITE else {},
)

_TestSessionLocal = async_sessionmaker(
    _test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def _sqlite_compatible_tables() -> list:
    """Filter out tables with PostgreSQL-only column types that SQLite cannot handle.

    Skips tables containing pgvector VECTOR or PostgreSQL ARRAY columns.
    JSONB columns are handled via compile-time type mapping (JSONB -> JSON),
    so tables with only JSONB (no VECTOR/ARRAY) are now included.
    """
    skip_tables = set()
    for table in Base.metadata.sorted_tables:
        for col in table.columns:
            col_type_str = str(col.type).upper()
            if any(pg_type in col_type_str for pg_type in _PG_ONLY_TYPE_NAMES):
                skip_tables.add(table.name)
                break
    return [t for t in Base.metadata.sorted_tables if t.name not in skip_tables]


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_tables():
    """Create all tables once per test session, drop at teardown.

    Skips tables with pgvector Vector or ARRAY columns when running on SQLite.
    Tables with JSONB columns are included (compile-time JSONB -> JSON mapping).
    """
    tables = (
        _sqlite_compatible_tables()
        if _IS_SQLITE
        else list(Base.metadata.sorted_tables)
    )
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all, tables=tables)
    await _test_engine.dispose()


@pytest_asyncio.fixture
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional async session that rolls back after each test."""
    async with _TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(async_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """httpx.AsyncClient bound to the FastAPI app with test DB session."""

    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield async_session

    fastapi_app.dependency_overrides[get_session] = _override_get_session

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_instance(async_session: AsyncSession) -> DBInstance:
    """Create and return a sample DBInstance for testing."""
    instance = DBInstance(
        id=uuid4(),
        name="test-pg-01",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="testdb",
        environment="development",
        connection_config={},
        is_active=True,
        autonomy_level=0,
    )
    async_session.add(instance)
    await async_session.commit()
    await async_session.refresh(instance)
    return instance
