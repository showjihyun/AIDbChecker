# Feature Spec: Task Queue 관리

## 메타데이터
- **Spec ID**: FS-AUTO-004
- **PRD 참조**: FR-AUTO-004
- **우선순위**: P0 (Phase 2)
- **상태**: Implemented
- **선행 Spec**: FS-AUTO-002 (Adaptive Autonomy), FS-AUTO-003 (Playbook Lite), AG-001 (Remediation Agent)
- **구현 파일**:
  - Backend: `backend/app/services/task_queue.py` (Phase 2 신규)
  - API: `backend/app/api/v1/tasks.py` (Phase 2 신규)
  - Existing: `backend/app/tasks/` (Celery 태스크 — 수집/분석/알림은 이미 존재)

---

## 1. 개요

Playbook 실행, AI 에이전트 작업, 유지보수 명령 등 **쓰기 작업**을 관리하는 Task Queue. 3가지 실행 모드(Auto/Manual/Schedule)를 지원하고, Autonomy Level에 따른 승인 워크플로우를 통합합니다.

> **범위 제한**: Phase 2에서는 Playbook Lite(Built-in 7개) 실행과 수동 트리거에 대한 큐 관리만 구현. 스케줄 모드와 유지보수 윈도우는 Phase 3.

---

## 2. 실행 모드

### Phase 2 (Lite)

| 모드 | 트리거 | 승인 | 설명 |
|------|--------|------|------|
| **Manual** | 관리자가 UI에서 실행 | Autonomy Gate | Playbook 선택 → 인스턴스 선택 → 실행 |
| **Auto** | 인시던트 발생 → DB Copilot 매칭 | Autonomy Gate | Playbook 자동 매칭 → L1: 추천, L2: 승인 후 실행 |

### Phase 3 (추가)

| 모드 | 트리거 | 설명 |
|------|--------|------|
| **Schedule** | cron 표현식 | 유지보수 윈도우 내 배치 실행 (VACUUM, REINDEX 등) |

---

## 3. Task 상태 머신

```
QUEUED → PENDING_APPROVAL → APPROVED → RUNNING → [COMPLETED | FAILED | ROLLED_BACK]
  │            │                                         │
  │            └── REJECTED (관리자 거부)                   │
  └── CANCELLED (관리자 취소)                               └── ESCALATED
```

### 상태 정의

| 상태 | 설명 |
|------|------|
| `queued` | 큐에 등록됨, Autonomy 체크 전 |
| `pending_approval` | Autonomy L1/L2에서 관리자 승인 대기 |
| `approved` | 승인됨, 실행 대기 |
| `rejected` | 관리자가 거부 |
| `cancelled` | 관리자가 취소 |
| `running` | 실행 중 |
| `completed` | 성공 완료 |
| `failed` | 실행 실패 |
| `rolled_back` | 실패 후 롤백 완료 |
| `escalated` | 롤백도 실패, 사람 에스컬레이션 |

---

## 4. API Endpoints

| Method | Path | Description | Phase |
|--------|------|-------------|-------|
| GET | `/api/v1/tasks` | Task 목록 조회 (status/instance 필터) | Phase 2 |
| GET | `/api/v1/tasks/{id}` | Task 상세 (실행 로그 포함) | Phase 2 |
| POST | `/api/v1/tasks` | Task 수동 생성 (Playbook + instance) | Phase 2 |
| POST | `/api/v1/tasks/{id}/approve` | Task 승인 | Phase 2 |
| POST | `/api/v1/tasks/{id}/reject` | Task 거부 | Phase 2 |
| POST | `/api/v1/tasks/{id}/cancel` | Task 취소 (queued/pending만) | Phase 2 |
| GET | `/api/v1/tasks/{id}/logs` | 실행 단계별 로그 | Phase 2 |

### Request/Response

```python
# Spec: FR-AUTO-004
class TaskCreate(BaseModel):
    playbook_name: str              # Built-in Playbook 이름
    instance_id: UUID               # 대상 인스턴스
    trigger: str = "manual"         # manual | auto | schedule (Phase 2: manual/auto만)
    params: dict | None = None      # Playbook 파라미터 오버라이드

class TaskResponse(BaseModel):
    id: UUID
    playbook_name: str
    instance_id: UUID
    trigger: str
    status: str                     # queued ~ escalated
    autonomy_level: int
    confidence_score: float | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    created_by: UUID                # 요청한 사용자
    execution_log: list[dict] | None  # 단계별 실행 결과
```

---

## 5. 승인 워크플로우

```
Task 생성
    → Autonomy Gate (FS-AUTO-002)
    → L0: 즉시 rejected ("알림 전용 인스턴스")
    → L1: pending_approval → UI 알림 + WebSocket → 관리자 approve/reject
    → L2: pending_approval → 관리자 approve → running
```

### WebSocket 이벤트

| Event | Direction | Payload |
|-------|-----------|---------|
| `task:pending_approval` | Server → Client | `{task_id, playbook_name, instance_name}` |
| `task:status_changed` | Server → Client | `{task_id, old_status, new_status}` |

---

## 6. 동시 실행 제어

| 규칙 | 값 | 설명 |
|------|-----|------|
| 인스턴스당 동시 Task | 1 | 같은 DB에 2개 Playbook 동시 실행 방지 |
| 전체 동시 Task | 3 | 시스템 리소스 보호 |
| 승인 대기 만료 | 30분 | 만료 시 자동 cancelled |

---

## 7. 인수 기준 (Acceptance Criteria) — Phase 2

- [ ] **AC-1**: POST `/api/v1/tasks`로 Playbook Task 생성 시 `status: "queued"` 반환
- [ ] **AC-2**: Autonomy L1 인스턴스에서 Task 생성 시 `pending_approval` 상태로 전환 + WebSocket 알림
- [ ] **AC-3**: 관리자 승인 후 Task 실행 → `completed` 또는 `failed` 상태
- [ ] **AC-4**: 같은 인스턴스에 동시 Task 생성 시도 시 거부 (409 Conflict)
- [ ] **AC-5**: 승인 대기 30분 초과 시 자동 `cancelled`
- [ ] **AC-6**: GET `/api/v1/tasks`에서 status 필터링 동작

---

## 8. 의존성

- **선행 Spec**: FS-AUTO-002 (Autonomy Gate), FS-AUTO-003 (Playbook Lite)
- **연동 Spec**: WEBSOCKET_EVENTS_SPEC (승인 알림), AUDIT_LOG_SPEC (Task 감사 기록)
- **저장**: `remediation_logs` 테이블 재활용 (ERD DM-001)
