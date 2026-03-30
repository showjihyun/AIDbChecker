# Spec: AG-001
"""NeuralDB FastAPI application entry point."""

from contextlib import asynccontextmanager

import socketio
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

import app.utils.bcrypt_patch  # noqa: F401 — patch bcrypt BEFORE passlib loads
from app.api.deps import get_current_user
from app.api.v1 import (
    alerts,
    ash,
    audit,
    auth,
    baselines,
    copilot,
    dba,
    graph,
    incidents,
    instances,
    kpi,
    llm_observability,
    llm_settings,
    metrics,
    mtl,
    nl2sql,
    playbooks,
    rag,
    reports,
    schema_changes,
    system,
    tasks,
    tuning,
    users,
)
from app.config import settings
from app.middleware.audit import AuditLogMiddleware
from app.websocket.events import sio


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Startup and shutdown events."""
    # Startup
    yield
    # Shutdown: dispose system engine and all target DB pools
    from app.db.session import _target_pools, system_engine

    await system_engine.dispose()

    for pool_engine in list(_target_pools.values()):
        await pool_engine.dispose()
    _target_pools.clear()

    # Close tuning agent connection pools
    import contextlib

    from app.api.v1.tuning import _tuning_pool_cache

    for pool, _dsn in list(_tuning_pool_cache.values()):
        with contextlib.suppress(Exception):
            await pool.close()
    _tuning_pool_cache.clear()


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="AI-Powered Intelligent DB Monitoring System",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Spec: FS-ADMIN-003 -- Audit log middleware (after CORS, before route handling)
app.add_middleware(AuditLogMiddleware)

# Spec: API-ERR-001 -- Standardized error responses
from app.middleware.error_handler import register_error_handlers  # noqa: E402
from app.middleware.rate_limit import RateLimitMiddleware  # noqa: E402

register_error_handlers(app)

# SEC-10: Rate limiting on critical endpoints
app.add_middleware(RateLimitMiddleware)

# Prometheus metrics
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# Auth router — no JWT required (login/refresh are public)
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])

# Protected routers — require valid JWT on every endpoint
_auth_dep = [Depends(get_current_user)]
app.include_router(instances.router, prefix="/api/v1", tags=["instances"], dependencies=_auth_dep)
app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"], dependencies=_auth_dep)
app.include_router(ash.router, prefix="/api/v1", tags=["ash"], dependencies=_auth_dep)
app.include_router(alerts.router, prefix="/api/v1", tags=["alerts"], dependencies=_auth_dep)
app.include_router(incidents.router, prefix="/api/v1", tags=["incidents"], dependencies=_auth_dep)
app.include_router(users.router, prefix="/api/v1", tags=["users"], dependencies=_auth_dep)
app.include_router(audit.router, prefix="/api/v1", tags=["audit"], dependencies=_auth_dep)
app.include_router(baselines.router, prefix="/api/v1", tags=["baselines"], dependencies=_auth_dep)
app.include_router(nl2sql.router, prefix="/api/v1", tags=["nl2sql"], dependencies=_auth_dep)
app.include_router(rag.router, prefix="/api/v1", tags=["rag"], dependencies=_auth_dep)
app.include_router(mtl.router, prefix="/api/v1", tags=["mtl"], dependencies=_auth_dep)
app.include_router(
    schema_changes.router, prefix="/api/v1", tags=["schema-changes"], dependencies=_auth_dep
)
app.include_router(kpi.router, prefix="/api/v1", tags=["kpi"], dependencies=_auth_dep)
app.include_router(
    llm_settings.router, prefix="/api/v1", tags=["llm-settings"], dependencies=_auth_dep
)
app.include_router(tuning.router, prefix="/api/v1", tags=["tuning"], dependencies=_auth_dep)
app.include_router(dba.router, prefix="/api/v1", tags=["dba-agent"], dependencies=_auth_dep)
app.include_router(copilot.router, prefix="/api/v1", tags=["copilot"], dependencies=_auth_dep)
app.include_router(
    llm_observability.router, prefix="/api/v1", tags=["llm-observability"], dependencies=_auth_dep
)
app.include_router(graph.router, prefix="/api/v1", tags=["graph"], dependencies=_auth_dep)
app.include_router(reports.router, prefix="/api/v1", tags=["reports"], dependencies=_auth_dep)
app.include_router(playbooks.router, prefix="/api/v1", tags=["playbooks"], dependencies=_auth_dep)
app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"], dependencies=_auth_dep)

# System router — intentionally public (health check, metrics)
app.include_router(system.router, prefix="/api/v1", tags=["system"])

# Mount Socket.io ASGI app for WebSocket support
app.mount("/socket.io", socketio.ASGIApp(sio))
