# Spec: MVP-DASH-002
"""Socket.io event definitions for real-time metric and incident streaming.

Namespaces:
  /ws/metrics   — 1-second real-time metric updates
  /ws/incidents — incident creation / status change events
"""

import socketio
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

# Use Valkey (Redis-compatible) as the pub/sub backend so that Socket.io
# events emitted from Celery workers (separate processes) are delivered to
# connected WebSocket clients in the FastAPI process.
mgr = socketio.AsyncRedisManager(settings.VALKEY_URL)

sio = socketio.AsyncServer(
    async_mode="asgi",
    client_manager=mgr,
    cors_allowed_origins="*",
    namespaces=["/ws/metrics", "/ws/incidents"],
    logger=False,
    engineio_logger=False,
)


@sio.on("connect", namespace="/ws/metrics")
async def on_metrics_connect(sid: str, environ: dict) -> None:
    """Client connected to metrics namespace."""
    logger.info("ws.metrics_connected", sid=sid)


@sio.on("disconnect", namespace="/ws/metrics")
async def on_metrics_disconnect(sid: str) -> None:
    """Client disconnected from metrics namespace."""
    logger.info("ws.metrics_disconnected", sid=sid)


@sio.on("subscribe", namespace="/ws/metrics")
async def on_subscribe(sid: str, data: dict) -> None:
    """Client subscribes to a specific instance's metrics.

    data: {"instance_id": "uuid-string"}
    Joins the sid to a room named by instance_id for targeted broadcasts.
    """
    instance_id = data.get("instance_id")
    if instance_id:
        sio.enter_room(sid, room=instance_id, namespace="/ws/metrics")
        logger.info("ws.subscribed", sid=sid, instance_id=instance_id)


@sio.on("unsubscribe", namespace="/ws/metrics")
async def on_unsubscribe(sid: str, data: dict) -> None:
    """Client unsubscribes from a specific instance's metrics."""
    instance_id = data.get("instance_id")
    if instance_id:
        sio.leave_room(sid, room=instance_id, namespace="/ws/metrics")
        logger.info("ws.unsubscribed", sid=sid, instance_id=instance_id)


@sio.on("connect", namespace="/ws/incidents")
async def on_incidents_connect(sid: str, environ: dict) -> None:
    """Client connected to incidents namespace."""
    logger.info("ws.incidents_connected", sid=sid)


@sio.on("disconnect", namespace="/ws/incidents")
async def on_incidents_disconnect(sid: str) -> None:
    """Client disconnected from incidents namespace."""
    logger.info("ws.incidents_disconnected", sid=sid)


async def broadcast_metric(instance_id: str, data: dict) -> None:
    """Emit metric:update event to all clients subscribed to the instance.

    Args:
        instance_id: UUID string — used as the Socket.io room name.
        data: Metric payload with instance_id, sampled_at, category, metrics.
    """
    await sio.emit(
        "metric:update",
        data,
        room=instance_id,
        namespace="/ws/metrics",
    )


async def broadcast_incident(event: str, data: dict) -> None:
    """Emit incident event to all clients in the incidents namespace.

    Args:
        event: "incident:new" or "incident:update"
        data: Incident payload.
    """
    await sio.emit(
        event,
        data,
        namespace="/ws/incidents",
    )
