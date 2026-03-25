# Spec: AG-001
"""NeuralDB FastAPI application entry point."""

from contextlib import asynccontextmanager

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from fastapi import Depends

from app.config import settings
from app.api.v1 import auth, instances, metrics, ash, alerts, system
from app.api.deps import get_current_user
from app.websocket.events import sio


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Startup and shutdown events."""
    # Startup
    yield
    # Shutdown: dispose system engine and all target DB pools
    from app.db.session import system_engine, _target_pools

    await system_engine.dispose()

    for pool_engine in list(_target_pools.values()):
        await pool_engine.dispose()
    _target_pools.clear()


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

# System router — intentionally public (health check, metrics)
app.include_router(system.router, prefix="/api/v1", tags=["system"])

# Mount Socket.io ASGI app for WebSocket support
app.mount("/socket.io", socketio.ASGIApp(sio))
