# Feature Spec: AI Decision Log

## 메타데이터
- **Spec ID**: FS-ADMIN-004
- **PRD 참조**: FR-ADMIN-004
- **우선순위**: P0 (MVP)
- **상태**: Implemented
- **선행 Spec**: DM-001 (ERD — `audit_logs` 테이블), FS-AI-011 (Confidence Score)
- **구현 파일**:
  - Backend: `backend/app/middleware/audit.py` (기존 감사 미들웨어 확장)
  - Models: `backend/app/models/audit_log.py` (기존 — `action: "ai_decision"` 이미 정의)
  - Services: `backend/app/services/mtl_lite.py`, `backend/app/services/nl2sql.py`, `backend/app/services/rag.py`

---

## 1. 개요

모든 LLM/AI 호출에 대해 **입력 프롬프트, 출력 결과, 토큰 사용량, 추론 근거(Reasoning Chain), 실행 시간**을 자동 기록하는 시스템. 기존 `audit_logs` 테이블의 `action: "ai_decision"` 타입으로 저장하며, Self-Healing 전 과정의 AI 판단을 투명하게 추적합니다.

> **기존 인프라 활용**: 별도 테이블 없이 `audit_logs.details` JSONB 필드에 AI 전용 필드를 확장합니다.

---

## 2. 로깅 대상

| AI 기능 | 로깅 시점 | 필수 필드 | Phase |
|---------|----------|----------|-------|
| MTL Lite RCA | 인시던트 진단 시 | prompt, response, tokens, confidence, reasoning_chain | MVP |
| NL2SQL | 사용자 질의 시 | natural_query, generated_sql, model, tokens | MVP |
| RAG 검색 | 유사 인시던트 검색 시 | query_text, top_k, results_count, search_time_ms | MVP |
| Auto-Baseline | 이상 탐지 판단 시 | metric_type, sample_value, baseline_range, is_anomaly | MVP |
| DB Copilot | ToT 진단 시 | branches_explored, selected_branch, scores, tokens | Phase 2 |
| Playbook 실행 | Autonomy Gate 통과 시 | playbook_name, autonomy_level, confidence, decision | Phase 2 |

---

## 3. 로그 스키마

### `audit_logs` 테이블 활용 (DM-001 참조)

기존 컬럼:
- `action`: `"ai_decision"` (고정)
- `resource_type`: `"mtl_rca"` | `"nl2sql"` | `"rag_search"` | `"anomaly_detection"` | `"copilot"` | `"playbook_execution"`
- `resource_id`: 관련 인시던트/인스턴스 ID
- `user_id`: 트리거한 사용자 (시스템 자동이면 NULL)

### `details` JSONB 확장 필드

```python
# Spec: FR-ADMIN-004
class AIDecisionDetails(BaseModel):
    """audit_logs.details JSONB에 저장되는 AI Decision 필드"""

    # 공통
    ai_model: str                        # "gpt-4o", "mistral:7b", "stl+isolation_forest"
    ai_mode: str                         # "online" | "offline"
    inference_time_ms: int               # 추론 소요 시간

    # LLM 호출 시 (MTL, NL2SQL, Copilot)
    prompt_summary: str | None = None    # 프롬프트 요약 (전문은 과대 → 요약만)
    prompt_tokens: int | None = None     # 입력 토큰 수
    completion_tokens: int | None = None # 출력 토큰 수
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None  # 추정 비용

    # AI 판단 결과
    decision: str                        # "anomaly_detected", "normal", "sql_generated", "rca_completed"
    confidence: float | None = None      # 0.0~1.0 (FS-AI-011)
    reasoning_summary: str | None = None # 추론 요약 (1~2문장)

    # 입출력 요약
    input_summary: dict | None = None    # 입력 데이터 요약 (메트릭 스냅샷 등)
    output_summary: dict | None = None   # 출력 결과 요약

    # 에러
    error: str | None = None             # 실패 시 에러 메시지
```

### 예시: MTL RCA Decision Log

```json
{
  "action": "ai_decision",
  "resource_type": "mtl_rca",
  "resource_id": "incident-uuid-123",
  "details": {
    "ai_model": "gpt-4o",
    "ai_mode": "online",
    "inference_time_ms": 2340,
    "prompt_tokens": 1200,
    "completion_tokens": 450,
    "total_tokens": 1650,
    "estimated_cost_usd": 0.025,
    "decision": "rca_completed",
    "confidence": 0.87,
    "reasoning_summary": "CPU 급증 + Seq Scan 감지 → Missing Index가 근본 원인",
    "input_summary": {
      "instance": "pg-prod-01",
      "metrics": {"cpu": 92, "connections": 45, "tps": 120},
      "rag_results_count": 3
    },
    "output_summary": {
      "anomaly_type": "query_performance_degradation",
      "root_cause": "missing_index",
      "severity": 0.8,
      "suggested_actions": ["CREATE INDEX CONCURRENTLY"]
    }
  }
}
```

---

## 4. 로깅 구현

### 4.1 데코레이터 패턴

```python
# Spec: FR-ADMIN-004
# backend/app/utils/ai_logger.py

from functools import wraps

def log_ai_decision(resource_type: str):
    """AI 호출 함수에 적용하는 Decision Log 데코레이터"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                result = await func(*args, **kwargs)
                elapsed_ms = int((time.monotonic() - start) * 1000)

                await create_audit_log(
                    action="ai_decision",
                    resource_type=resource_type,
                    details=build_ai_details(result, elapsed_ms),
                )
                return result
            except Exception as e:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                await create_audit_log(
                    action="ai_decision",
                    resource_type=resource_type,
                    details={"error": str(e), "inference_time_ms": elapsed_ms},
                )
                raise
        return wrapper
    return decorator

# 사용 예:
@log_ai_decision("mtl_rca")
async def mtl_lite_predict(context: dict) -> MTLPredictResponse: ...

@log_ai_decision("nl2sql")
async def generate_sql(question: str, instance_id: UUID) -> NL2SQLResponse: ...
```

### 4.2 프롬프트 저장 정책

| 항목 | 정책 | 이유 |
|------|------|------|
| 전체 프롬프트 | **저장하지 않음** | 토큰 수 과다 → DB 비대화 |
| 프롬프트 요약 | 저장 (200자 이내) | 감사/디버깅에 충분 |
| 전체 응답 | **저장하지 않음** | output_summary로 대체 |
| 응답 요약 | 저장 (JSON 구조) | 핵심 결과만 |
| 토큰 수/비용 | 저장 | LLM Observability 기초 데이터 |

---

## 5. 조회 API

기존 감사 로그 API 확장:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/audit-logs?action=ai_decision` | AI Decision Log 필터 조회 |
| GET | `/api/v1/audit-logs?action=ai_decision&resource_type=mtl_rca` | RCA 판단 이력만 |
| GET | `/api/v1/audit-logs?action=ai_decision&resource_id={incident_id}` | 특정 인시던트의 AI 판단 이력 |

---

## 6. 인수 기준 (Acceptance Criteria)

- [ ] **AC-1**: MTL Lite RCA 호출 시 `audit_logs`에 `action: "ai_decision"`, `resource_type: "mtl_rca"` 기록 자동 생성
- [ ] **AC-2**: NL2SQL 호출 시 `resource_type: "nl2sql"` 기록 자동 생성
- [ ] **AC-3**: `details` JSONB에 `ai_model`, `inference_time_ms`, `total_tokens`, `confidence` 포함
- [ ] **AC-4**: LLM 호출 실패 시 `details.error`에 에러 메시지 기록
- [ ] **AC-5**: GET `/api/v1/audit-logs?action=ai_decision`으로 AI 판단 이력 필터 조회 가능
- [ ] **AC-6**: 전체 프롬프트는 저장하지 않고 `prompt_summary` (200자 이내)만 기록

---

## 7. 의존성

- **선행 Spec**: DM-001 (`audit_logs` 테이블), AUDIT_LOG_SPEC (감사 로그 기본 구조)
- **연동 Spec**: FS-AI-011 (Confidence Score — `details.confidence`), FS-AI-013 (LLM Observability — 토큰/비용 데이터 공유)
- **비고**: Phase 2의 LLM Observability(FS-AI-013)가 이 로그 데이터를 집계하여 대시보드에 표시
