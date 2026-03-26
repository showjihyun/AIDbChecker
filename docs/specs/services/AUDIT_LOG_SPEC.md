# Feature Spec: 감사 로그 미들웨어

## 메타데이터
- **Spec ID**: FS-ADMIN-003
- **PRD 참조**: FR-ADMIN-003, MVP-ADMIN-003
- **우선순위**: P0 (MVP)
- **상태**: Approved
- **선행 Spec**: DM-001 (audit_logs 테이블), API-001 (인증)
- **구현 파일**:
  - Backend: `backend/app/middleware/audit.py`, `backend/app/api/v1/audit.py`
  - Test: `backend/tests/unit/test_admin_003_spec.py`

---

## 1. 개요

모든 상태 변경 API 호출에 대해 WHO/WHAT/WHEN/WHERE/WHY를 `audit_logs` 테이블에 자동 기록하는 FastAPI 미들웨어.

---

## 2. 인터페이스 계약

### 2.1 미들웨어 동작

```
Request → JWT에서 user_id 추출
       → Route 실행 (response 생성)
       → POST/PUT/DELETE 요청이면 감사 로그 기록
       → Response 반환
```

### 2.2 기록 대상

| HTTP Method | 기록 여부 | action 값 |
|-------------|----------|----------|
| GET | ❌ 기록 안함 | - |
| POST | ✅ | `create` |
| PUT | ✅ | `update` |
| DELETE | ✅ | `delete` |

### 2.3 감사 로그 스키마 (ERD.md §2.13 참조)

```python
class AuditLogCreate:
    user_id: UUID | None      # JWT에서 추출 (미인증 시 None)
    action: str               # create / update / delete
    resource_type: str        # URL 경로에서 추출 (instances, users, alerts 등)
    resource_id: UUID | None  # URL 경로에서 추출
    details: dict             # request method, path, status_code, ip
    ip_address: str | None    # X-Forwarded-For 또는 client.host
    user_agent: str | None    # User-Agent 헤더
```

### 2.4 API 엔드포인트

- **Method**: GET
- **Path**: `/api/v1/audit-logs`
- **Auth**: super_admin only
- **Query Params**: `user_id`, `resource_type`, `from_ts`, `to_ts`, `limit` (default 50)
- **Response**: `{ items: AuditLog[], total: int }`

---

## 3. 구현 규격

### 3.1 미들웨어 구현

```python
# backend/app/middleware/audit.py
# Spec: FS-ADMIN-003

class AuditLogMiddleware:
    """FastAPI middleware that logs state-changing API calls."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        if request.method in ("POST", "PUT", "DELETE"):
            # 비동기로 감사 로그 기록 (응답 지연 방지)
            asyncio.create_task(_write_audit_log(request, response))

        return response
```

### 3.2 리소스 추출 규칙

```
/api/v1/instances           → resource_type="instance", resource_id=None
/api/v1/instances/{id}      → resource_type="instance", resource_id={id}
/api/v1/users/{id}          → resource_type="user", resource_id={id}
/api/v1/alerts/channels     → resource_type="alert_channel", resource_id=None
/api/v1/auth/login          → resource_type="auth", action="login"
```

### 3.3 성능 요구사항

- 감사 로그 기록은 **응답 반환 후 비동기** 처리 (응답 지연 0ms)
- 감사 로그 기록 실패 시 **silent skip** (절대 요청을 실패시키지 않음)

---

## 4. 인수 기준

- [ ] AC-1: POST/PUT/DELETE 요청 시 audit_logs 테이블에 레코드 생성
- [ ] AC-2: GET 요청은 감사 로그에 기록되지 않음
- [ ] AC-3: user_id가 JWT에서 올바르게 추출됨
- [ ] AC-4: resource_type과 resource_id가 URL에서 올바르게 파싱됨
- [ ] AC-5: GET /api/v1/audit-logs에서 감사 이력 조회 가능 (super_admin)
- [ ] AC-6: 감사 로그 기록 실패 시 원래 응답에 영향 없음
