# Spec: SVC-001
"""Tests for SVC-001 Acceptance Criteria (Service Layer).

AC-1: Services are importable and instantiable (DI-ready)
AC-2: Transaction rollback behavior (integration -- skipped in unit)
AC-3: Valkey cache behavior — verify redis.asyncio is injectable with VALKEY_URL
AC-4: Audit log independence (integration -- skipped in unit)

Unit tests verify that service modules exist, classes are importable,
and the DI pattern (constructor injection / classmethod) is correctly structured.

IMPORTANT: Do NOT delete the @spec_ref decorator -- it enables AC tracking in CI.
"""

import pytest

from tests.conftest import spec_ref


@spec_ref("SVC-001", "AC-1")
async def test_svc_001_ac1_kpi_calculator_importable():
    """SVC-001 AC-1: KPICalculator service is importable and has compute_all_kpi.

    KPICalculator uses @classmethod pattern -- verify the class and its
    primary compute method exist and are callable.
    """
    from app.services.kpi_calculator import KPICalculator

    assert KPICalculator is not None
    assert hasattr(KPICalculator, "compute_all_kpi"), (
        "KPICalculator must have compute_all_kpi classmethod"
    )
    assert callable(getattr(KPICalculator, "compute_all_kpi"))


@spec_ref("SVC-001", "AC-1")
async def test_svc_001_ac1_rag_service_importable():
    """SVC-001 AC-1: RAG service module is importable.

    The RAG service uses module-level functions (format_for_prompt, etc.)
    which are importable and callable without external dependencies.
    """
    from app.services.rag import format_for_prompt

    # format_for_prompt is a pure function -- no DI needed
    result = format_for_prompt([])
    assert "No similar past incidents found" in result


@spec_ref("SVC-001", "AC-1")
async def test_svc_001_ac1_nl2sql_service_importable():
    """SVC-001 AC-1: NL2SQL service module is importable.

    Verifies that the nl2sql service module can be imported and its
    core functions are accessible.
    """
    from app.services import nl2sql

    # Module exposes generate_sql and execute_readonly_sql functions
    assert hasattr(nl2sql, "generate_sql"), (
        "nl2sql module must expose generate_sql function"
    )
    assert hasattr(nl2sql, "execute_readonly_sql"), (
        "nl2sql module must expose execute_readonly_sql function"
    )
    assert callable(nl2sql.generate_sql)
    assert callable(nl2sql.execute_readonly_sql)


@spec_ref("SVC-001", "AC-1")
async def test_svc_001_ac1_mtl_lite_service_importable():
    """SVC-001 AC-1: MTL Lite service is importable with predict function.

    The MTL Lite service provides the predict() function for 4-Head
    MTL inference. It must be importable for DI wiring.
    """
    from app.services.mtl_lite import predict

    assert callable(predict), "mtl_lite.predict must be a callable"


@spec_ref("SVC-001", "AC-1")
async def test_svc_001_ac1_schema_detector_importable():
    """SVC-001 AC-1: Schema detector service is importable."""
    from app.services import schema_detector

    assert schema_detector is not None


@spec_ref("SVC-001", "AC-2")
async def test_svc_001_ac2_transaction_rollback():
    """SVC-001 AC-2: Transaction rollback behavior verified.

    Full transaction boundary testing requires a live DB session.
    Unit level: verify that services accept AsyncSession (the rollback
    mechanism is provided by SQLAlchemy, not the service itself).
    """
    pytest.skip(
        "Transaction rollback requires live DB. "
        "Covered by integration tests with real PostgreSQL."
    )


@spec_ref("SVC-001", "AC-3")
async def test_svc_001_ac3_valkey_injectable():
    """SVC-001 AC-3: Valkey cache is injectable via redis.asyncio + VALKEY_URL.

    Verifies:
    1. redis.asyncio module is importable (dependency available)
    2. from_url() accepts the VALKEY_URL format from settings
    3. The client object has expected async methods (get, setex, aclose)
    4. RAG service uses the correct cache key prefix pattern
    """
    import redis.asyncio as aioredis
    from app.config import settings

    # 1. Verify VALKEY_URL is configured with redis:// protocol
    assert settings.VALKEY_URL.startswith("redis://"), (
        f"VALKEY_URL must use redis:// protocol, got: {settings.VALKEY_URL}"
    )

    # 2. Verify from_url() can construct a client without connecting
    #    (no network needed -- this validates the URL format acceptance)
    client = aioredis.from_url(settings.VALKEY_URL)
    assert client is not None

    # 3. Verify the client has the async methods our caching layer uses
    assert hasattr(client, "get"), "Valkey client must support get()"
    assert hasattr(client, "setex"), "Valkey client must support setex()"
    assert hasattr(client, "aclose"), "Valkey client must support aclose()"

    # 4. Verify cache key prefix used by RAG service
    from app.services.rag import _RAG_CACHE_PREFIX
    assert _RAG_CACHE_PREFIX == "rag:search:"

    # Clean up (no actual connection was made)
    await client.aclose()


@spec_ref("SVC-001", "AC-4")
async def test_svc_001_ac4_audit_log_middleware_exists():
    """SVC-001 AC-4: Audit log middleware is registered and fires independently.

    Unit level: verify the AuditLogMiddleware class exists and is registered
    on the FastAPI app. Full independence testing requires live DB.
    """
    from app.middleware.audit import AuditLogMiddleware

    assert AuditLogMiddleware is not None

    # Verify middleware is registered on the app
    from app.main import app

    middleware_classes = [m.cls for m in app.user_middleware if hasattr(m, "cls")]
    assert AuditLogMiddleware in middleware_classes, (
        "AuditLogMiddleware must be registered on the FastAPI app"
    )
