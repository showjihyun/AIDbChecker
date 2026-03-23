# Error Codes Spec: 통합 에러 코드 카탈로그

> **Spec ID**: API-ERR-001
> **PRD 참조**: §5 기능 요구사항 전체
> **상태**: Approved
> **Phase**: MVP

---

## 1. 에러 응답 표준 포맷

```python
# Spec: API-ERR-001
# backend/app/schemas/error.py

class ErrorResponse(BaseModel):
    error_code: str       # 머신 판독 코드 (INSTANCE_NOT_FOUND)
    message: str          # 사람 판독 메시지
    detail: str | None    # 상세 설명 (선택)
    field_errors: list[FieldError] | None  # 422 Validation 시
    request_id: str       # 추적용 UUID

class FieldError(BaseModel):
    field: str            # "host", "port", "password"
    message: str          # "이 필드는 필수입니다"
    code: str             # "required", "invalid_format"
```

### HTTP 응답 예시

```json
{
  "error_code": "INSTANCE_NOT_FOUND",
  "message": "DB instance not found",
  "detail": "Instance with ID '550e8400-...' does not exist",
  "field_errors": null,
  "request_id": "req-abc123"
}
```

```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "detail": null,
  "field_errors": [
    {"field": "host", "message": "이 필드는 필수입니다", "code": "required"},
    {"field": "port", "message": "1~65535 범위여야 합니다", "code": "invalid_range"}
  ],
  "request_id": "req-def456"
}
```

---

## 2. 에러 코드 카탈로그

### 2.1 인증/인가 (AUTH)

| error_code | HTTP | 설명 | 발생 조건 |
|-----------|------|------|----------|
| `AUTH_INVALID_CREDENTIALS` | 401 | 이메일/비밀번호 불일치 | POST /auth/login |
| `AUTH_TOKEN_EXPIRED` | 401 | JWT 만료 | 모든 인증 엔드포인트 |
| `AUTH_TOKEN_INVALID` | 401 | JWT 서명 불일치/형식 오류 | 모든 인증 엔드포인트 |
| `AUTH_REFRESH_EXPIRED` | 401 | Refresh Token 만료 | POST /auth/refresh |
| `AUTH_PERMISSION_DENIED` | 403 | RBAC 역할 부족 | 권한 필요 엔드포인트 |
| `AUTH_ACCOUNT_DISABLED` | 403 | 비활성 계정 | 로그인 시도 |

### 2.2 인스턴스 (INSTANCE)

| error_code | HTTP | 설명 | 발생 조건 |
|-----------|------|------|----------|
| `INSTANCE_NOT_FOUND` | 404 | 인스턴스 미존재 | GET/PUT/DELETE /instances/{id} |
| `INSTANCE_DUPLICATE` | 409 | 동일 host:port 이미 등록 | POST /instances |
| `INSTANCE_CONNECTION_FAILED` | 400 | DB 연결 실패 | POST /instances/{id}/test-connection |
| `INSTANCE_CONNECTION_TIMEOUT` | 408 | DB 연결 시간 초과 | POST /instances/{id}/test-connection |
| `INSTANCE_AUTH_FAILED` | 400 | DB 인증 실패 | POST /instances/{id}/test-connection |
| `INSTANCE_LIMIT_EXCEEDED` | 429 | 최대 인스턴스 수 초과 | POST /instances |
| `INSTANCE_PG_STAT_MISSING` | 400 | pg_stat_statements 미설치 | POST /instances/{id}/test-connection |

### 2.3 메트릭/ASH (METRIC)

| error_code | HTTP | 설명 | 발생 조건 |
|-----------|------|------|----------|
| `METRIC_RANGE_TOO_WIDE` | 400 | 조회 범위 초과 (최대 7일) | GET /instances/{id}/metrics |
| `METRIC_NO_DATA` | 404 | 해당 기간 메트릭 없음 | GET /instances/{id}/metrics |
| `ASH_DISABLED` | 400 | ASH 수집 비활성화 상태 | GET /instances/{id}/ash |

### 2.4 AI/ML (AI)

| error_code | HTTP | 설명 | 발생 조건 |
|-----------|------|------|----------|
| `AI_LLM_UNAVAILABLE` | 503 | LLM API 접속 불가 (온/오프라인 모두) | POST /mtl/predict, POST /nl2sql/query |
| `AI_LLM_TIMEOUT` | 504 | LLM 응답 타임아웃 | POST /mtl/predict |
| `AI_LLM_INVALID_RESPONSE` | 502 | LLM 응답 JSON 파싱 실패 | POST /mtl/predict |
| `AI_BUDGET_EXCEEDED` | 429 | 일일 LLM 토큰 예산 초과 | POST /mtl/predict, POST /nl2sql/query |
| `AI_BASELINE_NOT_READY` | 400 | 베이스라인 미학습 (2주 미만) | GET /instances/{id}/baselines |
| `AI_RAG_SEARCH_FAILED` | 500 | pgvector 검색 실패 | POST /rag/search |

### 2.5 NL2SQL (NL2SQL)

| error_code | HTTP | 설명 | 발생 조건 |
|-----------|------|------|----------|
| `NL2SQL_PARSE_FAILED` | 400 | 자연어 → SQL 변환 실패 | POST /nl2sql/query |
| `NL2SQL_WRITE_BLOCKED` | 403 | 쓰기 쿼리(INSERT/UPDATE/DELETE) 차단 | POST /nl2sql/query |
| `NL2SQL_EXECUTION_ERROR` | 500 | SQL 실행 오류 | POST /nl2sql/query |

### 2.6 알림 (ALERT)

| error_code | HTTP | 설명 | 발생 조건 |
|-----------|------|------|----------|
| `ALERT_CHANNEL_INVALID` | 400 | Slack Webhook URL 형식 오류 | POST /alerts/channels |
| `ALERT_CHANNEL_UNREACHABLE` | 400 | Slack Webhook 테스트 실패 | POST /alerts/test |

### 2.7 시스템 (SYSTEM)

| error_code | HTTP | 설명 | 발생 조건 |
|-----------|------|------|----------|
| `VALIDATION_ERROR` | 422 | 요청 데이터 검증 실패 | 모든 POST/PUT |
| `RATE_LIMITED` | 429 | 요청 빈도 초과 | 모든 엔드포인트 |
| `INTERNAL_ERROR` | 500 | 서버 내부 오류 | 예기치 않은 에러 |

---

## 3. FastAPI Exception Handler

```python
# backend/app/middleware/error_handler.py
# Spec: API-ERR-001

from fastapi import Request
from fastapi.responses import JSONResponse

class NeuralDBError(Exception):
    def __init__(self, error_code: str, message: str, status_code: int = 400, detail: str = None):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.detail = detail

async def neuraldb_error_handler(request: Request, exc: NeuralDBError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "detail": exc.detail,
            "field_errors": None,
            "request_id": request.state.request_id,
        },
    )
```

---

## 4. 인수 기준

- [ ] AC-1: 모든 에러 응답이 `ErrorResponse` 포맷을 따름
- [ ] AC-2: 422 응답에 `field_errors` 배열이 포함됨
- [ ] AC-3: 모든 에러에 `request_id`가 포함됨 (추적용)
- [ ] AC-4: error_code가 카탈로그에 정의된 값만 사용됨
