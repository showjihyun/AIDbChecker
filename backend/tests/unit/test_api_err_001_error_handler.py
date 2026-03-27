# Spec: API-ERR-001
"""Spec-Driven tests for standardized error responses.

Feature Spec: docs/specs/api/ERROR_CODES_SPEC.md
AC Coverage:
  AC-1: 모든 에러 응답이 ErrorResponse 포맷
  AC-2: 422 응답에 field_errors 배열
  AC-3: 모든 에러에 request_id 포함
  AC-4: error_code가 카탈로그 값만 사용
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.conftest import spec_ref


# ---------------------------------------------------------------------------
# AC-1: ErrorResponse 포맷
# ---------------------------------------------------------------------------


@spec_ref("API-ERR-001", "AC-1")
def test_api_err_001_ac1_error_response_schema():
    """AC-1: ErrorResponse 스키마에 필수 필드 존재."""
    from app.schemas.error import ErrorResponse

    err = ErrorResponse(
        error_code="TEST_ERROR",
        message="Test error message",
        request_id="req-123",
    )
    assert err.error_code == "TEST_ERROR"
    assert err.message == "Test error message"
    assert err.detail is None
    assert err.field_errors is None
    assert err.request_id == "req-123"


@spec_ref("API-ERR-001", "AC-1")
def test_api_err_001_ac1_neuraldb_error_class():
    """AC-1: NeuralDBError 커스텀 에러 클래스."""
    from app.middleware.error_handler import NeuralDBError

    err = NeuralDBError("INSTANCE_NOT_FOUND", "DB instance not found", 404)
    assert err.error_code == "INSTANCE_NOT_FOUND"
    assert err.status_code == 404
    assert err.message == "DB instance not found"


@spec_ref("API-ERR-001", "AC-1")
@pytest.mark.asyncio
async def test_api_err_001_ac1_404_returns_structured(client):
    """AC-1: 404 에러가 ErrorResponse 포맷으로 반환."""
    import uuid

    resp = await client.get(f"/api/v1/instances/{uuid.uuid4()}")
    # Should be 401 (no auth) or 404 — both should have error_code
    assert resp.status_code in (401, 404)
    data = resp.json()
    assert "error_code" in data
    assert "message" in data


# ---------------------------------------------------------------------------
# AC-2: 422 Validation with field_errors
# ---------------------------------------------------------------------------


@spec_ref("API-ERR-001", "AC-2")
@pytest.mark.asyncio
async def test_api_err_001_ac2_validation_error_has_field_errors(client):
    """AC-2: 잘못된 요청 → 422 + field_errors 배열."""
    # POST /auth/login with empty body should trigger validation
    resp = await client.post("/api/v1/auth/login", data={})
    assert resp.status_code == 422
    data = resp.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert isinstance(data["field_errors"], list)
    assert len(data["field_errors"]) >= 1
    assert "field" in data["field_errors"][0]
    assert "message" in data["field_errors"][0]


# ---------------------------------------------------------------------------
# AC-3: request_id 포함
# ---------------------------------------------------------------------------


@spec_ref("API-ERR-001", "AC-3")
@pytest.mark.asyncio
async def test_api_err_001_ac3_request_id_in_error(client):
    """AC-3: 에러 응답에 request_id 포함."""
    resp = await client.post("/api/v1/auth/login", data={})
    data = resp.json()
    assert "request_id" in data
    assert data["request_id"] is not None
    assert data["request_id"].startswith("req-")


# ---------------------------------------------------------------------------
# AC-4: error_code 카탈로그
# ---------------------------------------------------------------------------


@spec_ref("API-ERR-001", "AC-4")
def test_api_err_001_ac4_status_code_mapping():
    """AC-4: HTTP 상태 → error_code 매핑 존재."""
    from app.middleware.error_handler import _STATUS_TO_CODE

    assert _STATUS_TO_CODE[400] == "BAD_REQUEST"
    assert _STATUS_TO_CODE[401] == "AUTH_TOKEN_INVALID"
    assert _STATUS_TO_CODE[403] == "AUTH_PERMISSION_DENIED"
    assert _STATUS_TO_CODE[404] == "NOT_FOUND"
    assert _STATUS_TO_CODE[409] == "CONFLICT"
    assert _STATUS_TO_CODE[422] == "VALIDATION_ERROR"
    assert _STATUS_TO_CODE[500] == "INTERNAL_ERROR"


@spec_ref("API-ERR-001", "AC-4")
def test_api_err_001_ac4_error_handler_registered():
    """AC-4: 에러 핸들러가 app에 등록됨."""
    from app.main import app as fastapi_app

    # exception_handlers dict should have our handlers
    assert Exception in fastapi_app.exception_handlers
