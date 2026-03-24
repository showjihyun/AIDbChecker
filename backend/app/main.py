# Spec: AG-001
"""NeuralDB FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.api.v1 import instances, metrics, ash, alerts, system


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Startup and shutdown events."""
    # Startup
    yield
    # Shutdown: dispose system engine
    from app.db.session import system_engine

    await system_engine.dispose()


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

# API Routers
app.include_router(instances.router, prefix="/api/v1", tags=["instances"])
app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"])
app.include_router(ash.router, prefix="/api/v1", tags=["ash"])
app.include_router(alerts.router, prefix="/api/v1", tags=["alerts"])
app.include_router(system.router, prefix="/api/v1", tags=["system"])
