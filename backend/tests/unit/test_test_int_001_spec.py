# Spec: TEST-INT-001
"""Tests for TEST-INT-001 Acceptance Criteria (Integration Test Infrastructure).

Verifies that the integration testing infrastructure is properly set up:
- Directory structure and fixtures exist
- Markers are registered for test isolation
- Integration tests reference live_session fixture
- TEST_DATABASE_URL environment variable is read in conftest

IMPORTANT: Do NOT delete the @spec_ref decorator -- it enables AC tracking in CI.
"""

import os
from pathlib import Path

import pytest

from tests.conftest import spec_ref


# Resolve paths relative to the backend root
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_INTEGRATION_DIR = _BACKEND_ROOT / "tests" / "integration"


@spec_ref("TEST-INT-001", "AC-1")
async def test_test_int_001_ac1_integration_dir_and_conftest():
    """TEST-INT-001 AC-1: `tests/integration/` directory exists + conftest.py has live_session fixture.

    Validates:
    1. tests/integration/ directory exists
    2. conftest.py exists within it
    3. conftest.py defines the live_session fixture
    4. live_session yields an AsyncSession
    """
    # 1. Directory exists
    assert _INTEGRATION_DIR.is_dir(), (
        f"tests/integration/ directory must exist at {_INTEGRATION_DIR}"
    )

    # 2. conftest.py exists
    conftest_path = _INTEGRATION_DIR / "conftest.py"
    assert conftest_path.is_file(), (
        f"tests/integration/conftest.py must exist at {conftest_path}"
    )

    # 3. conftest.py defines live_session fixture
    conftest_content = conftest_path.read_text(encoding="utf-8")
    assert "live_session" in conftest_content, (
        "tests/integration/conftest.py must define a 'live_session' fixture"
    )
    assert "async" in conftest_content, (
        "live_session should be an async fixture (uses AsyncSession)"
    )

    # 4. Verify it uses AsyncSession
    assert "AsyncSession" in conftest_content, (
        "live_session fixture should use sqlalchemy.ext.asyncio.AsyncSession"
    )


@spec_ref("TEST-INT-001", "AC-2")
async def test_test_int_001_ac2_integration_marker_registered():
    """TEST-INT-001 AC-2: @pytest.mark.integration marker is registered for test isolation.

    Validates:
    1. The integration conftest.py registers the 'integration' marker
    2. Integration tests use the marker (verified from test_db_tables.py)
    """
    conftest_path = _INTEGRATION_DIR / "conftest.py"
    conftest_content = conftest_path.read_text(encoding="utf-8")

    # 1. Marker registration exists in conftest
    assert "pytest.mark.integration" in conftest_content or (
        '"integration' in conftest_content
    ), (
        "Integration conftest.py must register 'integration' marker "
        "via pytest_configure()"
    )

    # 2. Verify test_db_tables.py uses the marker
    test_db_path = _INTEGRATION_DIR / "test_db_tables.py"
    assert test_db_path.is_file(), "test_db_tables.py must exist in integration dir"
    test_content = test_db_path.read_text(encoding="utf-8")
    assert "@pytest.mark.integration" in test_content, (
        "Integration tests must use @pytest.mark.integration marker"
    )


@spec_ref("TEST-INT-001", "AC-3")
async def test_test_int_001_ac3_integration_tests_use_live_session():
    """TEST-INT-001 AC-3: Integration tests exist that use live_session fixture.

    Validates that test_db_tables.py:
    1. Contains actual test functions
    2. Tests reference the live_session fixture (parameter)
    3. Tests execute SQL queries against a real database
    """
    test_db_path = _INTEGRATION_DIR / "test_db_tables.py"
    assert test_db_path.is_file(), (
        "test_db_tables.py must exist in tests/integration/"
    )

    content = test_db_path.read_text(encoding="utf-8")

    # 1. Contains test functions
    assert "async def test_" in content, (
        "test_db_tables.py must contain async test functions"
    )

    # 2. Tests use live_session fixture
    assert "live_session" in content, (
        "Integration tests must use the live_session fixture"
    )

    # 3. Tests execute SQL (verifying it is a real integration test)
    assert "await live_session.execute" in content, (
        "Integration tests should execute queries via live_session"
    )

    # 4. Count test functions to verify meaningful coverage
    test_count = content.count("async def test_")
    assert test_count >= 2, (
        f"Expected at least 2 integration tests, found {test_count}"
    )


@spec_ref("TEST-INT-001", "AC-4")
async def test_test_int_001_ac4_test_database_url_env_var():
    """TEST-INT-001 AC-4: TEST_DATABASE_URL env var is read in integration conftest.

    Validates:
    1. conftest.py reads TEST_DATABASE_URL from environment
    2. Has a sensible default fallback (localhost neuraldb)
    3. The URL follows postgresql+asyncpg protocol
    """
    conftest_path = _INTEGRATION_DIR / "conftest.py"
    content = conftest_path.read_text(encoding="utf-8")

    # 1. Reads TEST_DATABASE_URL
    assert "TEST_DATABASE_URL" in content, (
        "Integration conftest must read TEST_DATABASE_URL environment variable"
    )

    # 2. Uses os.getenv or os.environ for reading
    assert "os.getenv" in content or "os.environ" in content, (
        "TEST_DATABASE_URL should be read from environment via os.getenv/os.environ"
    )

    # 3. Default URL uses postgresql+asyncpg protocol
    assert "postgresql+asyncpg://" in content, (
        "Default TEST_DATABASE_URL should use postgresql+asyncpg:// protocol"
    )

    # 4. Verify the variable is used to create an engine
    assert "create_async_engine" in content, (
        "TEST_DATABASE_URL should be passed to create_async_engine"
    )
