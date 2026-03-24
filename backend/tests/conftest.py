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
from app.main import app
from app.models.db_instance import DBInstance


# Use an in-memory SQLite for unit tests (fast, no external deps).
# For integration tests, override TEST_DATABASE_URL to point to a real PostgreSQL.
TEST_DATABASE_URL = "sqlite+aiosqlite:///file::memory:?cache=shared&uri=true"

_test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    # SQLite needs these for async
    connect_args={"check_same_thread": False} if "sqlite" in TEST_DATABASE_URL else {},
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


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_tables():
    """Create all tables once per test session, drop at teardown."""
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
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

    app.dependency_overrides[get_session] = _override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


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
