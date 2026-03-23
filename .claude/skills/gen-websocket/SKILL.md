---
name: gen-websocket
description: Generate python-socketio WebSocket event handlers for real-time metric streaming, incident notifications, agent status updates, and live dashboard data. Includes server-side event emitters and client-side React hooks.
argument-hint: "[namespace] [events: comma-separated]"
allowed-tools: Read, Write, Glob, Grep, Edit
---

# Generate WebSocket Handler

## Arguments
- Namespace: $0
- Events: $1 (comma-separated)

## Output Files
```
backend/app/websocket/namespaces/{namespace}.py   # Server handler
frontend/src/hooks/use{Namespace}Socket.ts         # Client hook
```

## Server Template (python-socketio)
```python
import socketio
from app.websocket.manager import sio

@sio.on('connect', namespace='/{namespace}')
async def connect(sid, environ, auth):
    instance_id = environ.get('HTTP_X_INSTANCE_ID')
    await sio.enter_room(sid, f'instance:{instance_id}', namespace='/{namespace}')

@sio.on('disconnect', namespace='/{namespace}')
async def disconnect(sid):
    pass

@sio.on('subscribe', namespace='/{namespace}')
async def subscribe(sid, data):
    room = data.get('room')
    await sio.enter_room(sid, room, namespace='/{namespace}')

# Emit from anywhere in the app:
# await sio.emit('{event}', data, room=f'instance:{id}', namespace='/{namespace}')
```

## WebSocket Manager
```python
# backend/app/websocket/manager.py
import socketio

sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=True,
)

socket_app = socketio.ASGIApp(sio)
```

## FastAPI Integration
```python
# backend/app/main.py
from app.websocket.manager import socket_app
app.mount('/ws', socket_app)
```

## Namespaces
| Namespace | Events | Purpose |
|-----------|--------|---------|
| /metrics | metric:update, metric:spike | Real-time 1s metric streaming |
| /incidents | incident:new, incident:update, incident:resolve | Live incident feed |
| /agents | agent:status, agent:action, agent:complete | Agent execution monitoring |
| /ash | ash:sample, ash:heatmap | Live ASH session data |
| /remediation | remediation:start, remediation:progress, remediation:complete | Self-healing progress |

## Rules
- Use rooms for per-instance data isolation
- Auth via JWT token in handshake
- Heartbeat interval: 25s, timeout: 60s
- Emit to specific rooms, not broadcast
- Binary data for large metric batches
- Client auto-reconnect with exponential backoff
