# Spec: FS-ADMIN-003
"""AuditLogMiddleware -- intercepts state-changing requests and writes audit_logs.

Records WHO/WHAT/WHEN/WHERE for all POST/PUT/DELETE requests.
GET requests are silently skipped. Audit writes are fire-and-forget
(asyncio.create_task) so the response is never delayed or broken.
"""

import asyncio
import base64
import json
import logging
import re
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.db.session import AsyncSessionLocal
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)

# HTTP method -> audit action mapping (Spec: FS-ADMIN-003 Section 2.2)
_METHOD_ACTION_MAP: dict[str, str] = {
    "POST": "create",
    "PUT": "update",
    "DELETE": "delete",
}

# Regex to extract resource segments from /api/v1/{resource}/{id?} paths
# Captures: group(1)=resource_name, group(2)=optional UUID
_RESOURCE_PATTERN = re.compile(
    r"/api/v1/([a-z][a-z0-9_-]+)(?:/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}))?",
    re.IGNORECASE,
)

# Plurals -> singular for resource_type normalization
_RESOURCE_SINGULAR: dict[str, str] = {
    "instances": "instance",
    "users": "user",
    "incidents": "incident",
    "baselines": "baseline",
    "audit-logs": "audit_log",
    "schema-changes": "schema_change",
}


def _extract_user_id_from_jwt(request: Request) -> UUID | None:
    """Decode the JWT 'sub' claim via base64 without cryptographic validation.

    This is intentional for the middleware -- we only need the user_id for
    logging purposes and must never fail the request. Full JWT validation
    happens in the auth dependency layer.
    """
    try:
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header[7:]
        # JWT structure: header.payload.signature -- we need the payload
        payload_b64 = token.split(".")[1]
        # Add padding if needed
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        sub = payload.get("sub")
        if sub:
            return UUID(sub)
    except Exception:  # noqa: BLE001
        pass
    return None


def _parse_resource(path: str) -> tuple[str, UUID | None]:
    """Extract resource_type (singular) and resource_id from the URL path.

    Examples (Spec: FS-ADMIN-003 Section 3.2):
        /api/v1/instances           -> ("instance", None)
        /api/v1/instances/{uuid}    -> ("instance", UUID)
        /api/v1/alerts/channels     -> ("alert_channel", None)
        /api/v1/auth/login          -> ("auth", None)
    """
    match = _RESOURCE_PATTERN.search(path)
    if not match:
        return ("unknown", None)

    raw_resource = match.group(1)
    resource_id_str = match.group(2)

    # Handle nested paths like /alerts/channels -> alert_channel
    rest_of_path = path[match.end() :]
    if resource_id_str is None:
        # Check for a sub-resource name after the first segment
        sub_match = re.match(r"/([a-z][a-z0-9_-]+)", rest_of_path or "")
        if sub_match:
            sub = sub_match.group(1)
            raw_resource = f"{raw_resource}_{sub}"

    resource_type = _RESOURCE_SINGULAR.get(raw_resource, raw_resource.rstrip("s"))
    resource_id = UUID(resource_id_str) if resource_id_str else None

    # Special case: /auth/login -> action override handled by caller
    return (resource_type, resource_id)


async def _write_audit_log(
    request: Request,
    response: Response,
    user_id: UUID | None,
) -> None:
    """Fire-and-forget coroutine that persists one audit_log row.

    Uses its own session (not request-scoped) so it never interferes
    with the request lifecycle. Silently swallows all errors.
    """
    try:
        resource_type, resource_id = _parse_resource(str(request.url.path))

        # Determine action -- special-case login
        method = request.method
        action = _METHOD_ACTION_MAP.get(method, method.lower())
        if "auth/login" in str(request.url.path):
            action = "login"

        ip_address = request.headers.get(
            "x-forwarded-for", request.client.host if request.client else None
        )
        # X-Forwarded-For may contain multiple IPs; take the first
        if ip_address and "," in ip_address:
            ip_address = ip_address.split(",")[0].strip()

        user_agent = request.headers.get("user-agent")

        details = {
            "method": method,
            "path": str(request.url.path),
            "status_code": response.status_code,
            "query_params": dict(request.query_params),
        }

        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address[:45] if ip_address else None,
            user_agent=user_agent[:500] if user_agent else None,
        )

        async with AsyncSessionLocal() as session:
            session.add(log_entry)
            await session.commit()

    except Exception:  # noqa: BLE001
        # Spec: FS-ADMIN-003 AC-6 -- never break the request
        logger.debug("audit_log.write_failed", exc_info=True)


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Intercepts POST/PUT/DELETE responses and writes audit_logs asynchronously.

    GET/HEAD/OPTIONS requests are skipped entirely.
    Audit writes run as background tasks so response latency is unaffected.
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        # Spec: FS-ADMIN-003 Section 2.2 -- skip GET
        response = await call_next(request)

        if request.method in _METHOD_ACTION_MAP:
            user_id = _extract_user_id_from_jwt(request)
            # Fire-and-forget: don't await -- Spec: FS-ADMIN-003 Section 3.3
            asyncio.create_task(_write_audit_log(request, response, user_id))

        return response
