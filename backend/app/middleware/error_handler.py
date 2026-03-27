# Spec: API-ERR-001
"""Global error handler — standardized error responses for all exceptions.

Converts:
- NeuralDBError → structured ErrorResponse
- HTTPException → ErrorResponse with error_code mapping
- RequestValidationError → ErrorResponse with field_errors
- Unhandled exceptions → INTERNAL_ERROR
"""

from __future__ import annotations

from uuid import uuid4

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


class NeuralDBError(Exception):
    """Application-level error with structured error code.

    Spec: API-ERR-001 Section 3.

    Usage:
        raise NeuralDBError("INSTANCE_NOT_FOUND", "DB instance not found", 404,
                            detail=f"Instance {id} does not exist")
    """

    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int = 400,
        detail: str | None = None,
    ) -> None:
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


# ---------------------------------------------------------------------------
# HTTP status → error_code mapping for HTTPException fallback
# ---------------------------------------------------------------------------

_STATUS_TO_CODE = {
    400: "BAD_REQUEST",
    401: "AUTH_TOKEN_INVALID",
    403: "AUTH_PERMISSION_DENIED",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    501: "NOT_IMPLEMENTED",
    503: "SERVICE_UNAVAILABLE",
    504: "GATEWAY_TIMEOUT",
}


def _make_request_id(request: Request) -> str:
    """Get or generate request_id."""
    return getattr(request.state, "request_id", f"req-{uuid4().hex[:12]}")


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def _handle_neuraldb_error(request: Request, exc: NeuralDBError) -> JSONResponse:
    """Handle NeuralDBError → structured ErrorResponse."""
    request_id = _make_request_id(request)
    logger.warning(
        "error.neuraldb",
        error_code=exc.error_code,
        message=exc.message,
        status=exc.status_code,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "detail": exc.detail,
            "field_errors": None,
            "request_id": request_id,
        },
    )


async def _handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    """Convert FastAPI HTTPException → ErrorResponse."""
    request_id = _make_request_id(request)
    error_code = _STATUS_TO_CODE.get(exc.status_code, "UNKNOWN_ERROR")

    # Try to extract error_code from detail if it looks structured
    detail_str = str(exc.detail) if exc.detail else ""

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": error_code,
            "message": detail_str or f"HTTP {exc.status_code}",
            "detail": None,
            "field_errors": None,
            "request_id": request_id,
        },
    )


async def _handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Convert Pydantic ValidationError → ErrorResponse with field_errors."""
    request_id = _make_request_id(request)
    field_errors = []
    for err in exc.errors():
        loc = err.get("loc", ())
        field = ".".join(str(l) for l in loc if l != "body")
        field_errors.append(
            {
                "field": field or "unknown",
                "message": err.get("msg", "Validation error"),
                "code": err.get("type", "invalid"),
            }
        )

    return JSONResponse(
        status_code=422,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "detail": None,
            "field_errors": field_errors,
            "request_id": request_id,
        },
    )


async def _handle_unhandled(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions → INTERNAL_ERROR."""
    request_id = _make_request_id(request)
    logger.error(
        "error.unhandled",
        error=str(exc),
        type=type(exc).__name__,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "detail": None,
            "field_errors": None,
            "request_id": request_id,
        },
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_error_handlers(app: FastAPI) -> None:
    """Register all error handlers on the FastAPI app.

    Spec: API-ERR-001 — call this in main.py after app creation.
    """
    app.add_exception_handler(NeuralDBError, _handle_neuraldb_error)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, _handle_http_exception)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _handle_unhandled)  # type: ignore[arg-type]
