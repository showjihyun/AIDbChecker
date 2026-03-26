# Spec: TEST-INT-001
"""Integration test fixtures -- real PostgreSQL session.

Provides:
- live_session: AsyncSession connected to a real PostgreSQL instance
- Auto-skip: all integration tests are skipped if DB is unreachable

Requires:
- docker compose up -d postgres
- alembic upgrade head (tables must exist)
- Environment: TEST_DATABASE_URL (default: localhost neuraldb)
"""

import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://neuraldb:neuraldb@localhost:5432/neuraldb",
)


def pytest_configure(config):
    """Register the integration marker."""
    config.addinivalue_line("markers", "integration: requires live PostgreSQL")


def pytest_collection_modifyitems(config, items):
    """Auto-skip integration tests when the DB is unreachable."""
    import asyncio

    db_available = False
    try:
        loop = asyncio.new_event_loop()
        engine = create_async_engine(TEST_DB_URL, pool_size=1)

        async def _probe():
            async with engine.connect() as conn:
                from sqlalchemy import text
                await conn.execute(text("SELECT 1"))
            await engine.dispose()

        loop.run_until_complete(_probe())
        loop.close()
        db_available = True
    except Exception:
        pass

    if not db_available:
        skip = pytest.mark.skip(reason="Integration DB not available")
        for item in items:
            if "integration" in str(item.fspath):
                item.add_marker(skip)


@pytest_asyncio.fixture
async def live_session():
    """Real PostgreSQL session for integration tests.

    Each test gets its own session. No automatic rollback -- integration
    tests operate on actual data created by Alembic migrations.
    """
    engine = create_async_engine(TEST_DB_URL, pool_size=2)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()
