# Playbook Spec: Playbook-as-Code (Lite)

> **Spec ID**: FS-AUTO-003
> **PRD 참조**: FR-AUTO-001~005
> **상태**: Approved (Revised — Lite Scope)
> **적용 Phase**: Phase 2 (Lite) → Phase 3 (Full)
> **선행 Spec**: AGENT_SPEC.md (Remediation Agent), ERD.md (playbooks, remediation_logs)
> **ADR**: ADR-008 (경량 Playbook + DB Copilot 하이브리드)

---

## 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| v1.0 | 2026-03-21 | 초기 작성 (Full Scope) |
| v2.0 | 2026-03-26 | ADR-008 반영 — Lite Scope로 축소. Phase 2: Built-in 7개 + 기본 실행기 + L0~L2. Phase 3: 커스텀 YAML + Git 연동 + L3/L4 + LLM 자동 생성 |

---

## Phase 구분

### Phase 2 (Lite) — 이 문서의 구현 범위

| 포함 | 설명 |
|------|------|
| Built-in Playbook 7개 | 시스템 내장, 읽기 전용 YAML |
| 기본 실행 엔진 | 순차 실행 + 실패 시 역순 롤백 |
| Autonomy Gate L0~L2 | L0(알림), L1(추천+승인대기), L2(승인후실행) |
| 실행 이력 | `remediation_logs` 테이블 저장 |
| Confidence Score 연동 | Confidence < 0.5 시 자동 차단 |
| 수동 트리거 | UI에서 Playbook 선택 → 실행 |

### Phase 3 (Full) — 별도 Spec 업데이트 예정

| 연기 항목 | 사유 |
|----------|------|
| 커스텀 Playbook YAML 작성/편집 | Built-in 검증 후 개방 |
| LLM Playbook 자동 생성 | DB Copilot(FS-AI-012)이 실시간 판단으로 대체 |
| Git PR 연동 워크플로우 | Built-in은 코드 배포로 관리 |
| SLO 자동 검증 (before/after) | Phase 2는 수동 확인 |
| 동적 Autonomy 격하 (FR-AUTO-005) | 운영 데이터 축적 후 도입 |
| Autonomy L3/L4 | 프로덕션 검증 후 개방 |
| `schedule` 트리거 | Phase 2는 `metric_threshold`, `anomaly_detection`, `manual`만 |

---

## 1. Playbook Lifecycle (Lite)

```
[Built-in YAML 배포] → Active
                        ↓
                 Execution Cycle:
                 Triggered (수동 / 인시던트 자동매칭)
                     → Confidence Check (≥ 0.5?)
                     → Autonomy Check (L0~L2)
                     → [알림 | 추천+승인대기 | 승인후실행]
                         Execute → Step 1 → Step 2 → ...
                             → [Success | Failure → Rollback]
```

**Lite에서 제거된 단계**: Draft → Review → Approved (Built-in이므로 불필요)

---

## 2. YAML Schema (Lite)

Phase 2 Lite는 전체 스키마의 부분 집합만 지원합니다.

### 지원하는 필드

```yaml
# Spec: FR-AUTO-003 (Lite)
apiVersion: neuraldb/v1
kind: Playbook

metadata:
  name: "lock-remediation"               # kebab-case, unique
  version: "1.0"
  description: "Lock contention 자동 해소"
  author: "builtin"                       # Lite: "builtin" 고정
  tags: [performance, lock, postgresql]
  min_autonomy_level: 2                   # 0~2 (Lite에서 L3/L4 미지원)
  target_db_types: [postgresql]
  risk_level: medium                      # low | medium | high | critical

trigger:
  type: metric_threshold                  # Lite: metric_threshold | anomaly_detection | manual
  metric: lock_wait_timeout
  condition: ">"
  threshold: 5000
  duration: 30s
  cooldown: 5m
  min_confidence: 0.5                     # Confidence Score 최소값

steps:
  - name: "detect_blocking_queries"
    type: sql                             # Lite: sql만 지원 (command, api_call, agent_invoke는 Phase 3)
    query: |
      SELECT pid, query, wait_event_type, wait_event
      FROM pg_stat_activity
      WHERE state = 'active' AND wait_event_type = 'Lock'
    timeout: 10s
    save_as: blocking_sessions

  - name: "kill_blocking_session"
    type: sql
    query: "SELECT pg_terminate_backend({{ blocking_sessions[0].pid }})"
    timeout: 5s
    requires_approval: true               # L0/L1: 항상 승인 대기, L2: autonomy_level 체크
    rollback:
      query: "-- no rollback needed"

on_success:
  - notify: slack
    message: "Lock remediation 완료"

on_failure:
  - rollback: all
  - notify: slack
    severity: critical
    message: "Lock remediation 실패: {{ error }}"
```

### Lite에서 미지원하는 필드

| 필드 | Phase 3에서 지원 |
|------|-----------------|
| `preconditions` | 사전 조건 검증 |
| `steps[].type: command` | 셸 명령 실행 |
| `steps[].type: api_call` | 외부 API 호출 |
| `steps[].type: agent_invoke` | 에이전트 호출 |
| `steps[].retry` | 자동 재시도 |
| `slo_check` | SLO 자동 검증 |
| `on_failure.downgrade_autonomy` | 동적 Autonomy 격하 |
| `on_failure.escalate` | 에스컬레이션 체인 |
| `trigger.type: schedule` | 스케줄 트리거 |

---

## 3. Template Variables (Lite)

| 변수 | 설명 |
|------|------|
| `{{ instance_id }}` | 대상 DB 인스턴스 ID |
| `{{ instance_name }}` | 인스턴스 표시명 |
| `{{ trigger.metric_value }}` | 트리거 시점 메트릭 값 |
| `{{ steps.<step_name>.result }}` | 이전 단계 실행 결과 |
| `{{ error }}` | 실패 시 에러 메시지 |
| `{{ now }}` | 현재 UTC timestamp |

`save_as`로 저장된 변수도 `{{ variable_name }}`으로 참조 가능.

---

## 4. Built-in Playbook Templates (7개)

| # | Playbook | Trigger | Risk | Autonomy | Description |
|---|----------|---------|------|----------|-------------|
| 1 | `lock-remediation` | lock_wait > 5s | medium | L2 | 블로킹 세션 감지 → kill |
| 2 | `index-optimization` | seq_scan_ratio > 80% | medium | L2 | Missing index 감지 → CREATE INDEX CONCURRENTLY |
| 3 | `replication-lag` | replication_lag > 5s | high | L2 | WAL sender 점검 → 파라미터 알림 |
| 4 | `connection-pool` | connections > 80% max | medium | L1 | idle 세션 감지 → kill idle |
| 5 | `vacuum-maintenance` | dead_tuples > threshold | low | L1 | bloat 분석 → VACUUM ANALYZE |
| 6 | `query-timeout` | query_duration > 30s | low | L1 | 느린 쿼리 식별 → pg_cancel_backend |
| 7 | `memory-pressure` | hit_ratio < 95% | high | L2 | 캐시 분석 → shared_buffers 조정 추천 |

**파일 위치**: `backend/playbooks/builtin/`

**참고**: `replication-lag`과 `memory-pressure`는 risk_level=high이므로 DB Copilot 판단 결과와 결합하여 트리거됨.

---

## 5. 실행 엔진 (Lite)

### 5.1 실행 흐름

```python
# Spec: FR-AUTO-003 (Lite)
# backend/app/services/playbook_executor.py

async def execute_playbook(
    playbook: Playbook,
    instance_id: UUID,
    trigger_context: dict,
    autonomy_level: int,
    confidence_score: float,
) -> RemediationLog:
    """Built-in Playbook 실행기 (Lite)"""

    # 1. Confidence Check
    if confidence_score < playbook.trigger.min_confidence:
        return RemediationLog(status="blocked", reason="low_confidence")

    # 2. Autonomy Check
    if autonomy_level < playbook.metadata.min_autonomy_level:
        return RemediationLog(status="pending_approval")

    # 3. 순차 실행
    executed_steps = []
    for step in playbook.steps:
        if step.requires_approval and autonomy_level < 2:
            await request_approval(step)  # WebSocket으로 UI에 승인 요청

        result = await execute_step(instance_id, step, trigger_context)
        executed_steps.append(result)

        if result.failed:
            # 4. 롤백 (역순)
            await rollback_steps(instance_id, executed_steps)
            return RemediationLog(status="failed", actions=executed_steps)

    return RemediationLog(status="success", actions=executed_steps)
```

### 5.2 Safety Rules

1. **모든 SQL에 `statement_timeout` 설정** — Playbook YAML의 `timeout` 필드 적용
2. **Autonomy Gate 필수** — L0/L1은 실행 불가, L2는 승인 후 실행
3. **Confidence Gate 필수** — Confidence < 0.5 시 자동 차단
4. **읽기 전용 커넥션 분리** — 조회 step은 읽기 커넥션, 쓰기 step은 쓰기 커넥션
5. **Built-in만 실행** — Phase 2에서 사용자 YAML 업로드/실행 불가

---

## 6. DB Copilot 연동 (ADR-008)

### 위험 수준별 역할 분담

| 위험 수준 | 주 담당 | 보조 | 예시 |
|----------|---------|------|------|
| **고위험** (DDL, 파라미터) | Built-in Playbook | DB Copilot이 Playbook 추천 | CREATE INDEX, ALTER SYSTEM |
| **중위험** (세션 kill, VACUUM) | DB Copilot 판단 | Playbook 절차 참조 | pg_terminate_backend, VACUUM |
| **저위험** (조회, 분석) | DB Copilot 자유 | - | EXPLAIN, pg_stat 조회 |

### 연동 흐름

```
인시던트 발생
    ↓
DB Copilot (ToT 분석)
    ↓
┌── 매칭되는 Built-in Playbook 있음?
│   ├── Yes → Playbook 추천 (L1) 또는 실행 (L2)
│   └── No  → DB Copilot이 추천 액션 제시 (사람 승인 필요)
│            → 반복 패턴 발견 시 Phase 3에서 Playbook 승격 후보로 기록
```

---

## 7. API Endpoints (Lite)

| Method | Path | Description | Phase |
|--------|------|-------------|-------|
| GET | `/api/v1/playbooks` | Built-in Playbook 목록 조회 | Phase 2 |
| GET | `/api/v1/playbooks/{name}` | Playbook 상세 (YAML 포함) | Phase 2 |
| POST | `/api/v1/playbooks/{name}/execute` | Playbook 수동 실행 | Phase 2 |
| GET | `/api/v1/playbooks/{name}/history` | 실행 이력 조회 | Phase 2 |
| POST | `/api/v1/playbooks/{name}/approve/{log_id}` | 승인 대기 Playbook 승인 | Phase 2 |
| POST | `/api/v1/playbooks` | 커스텀 Playbook 생성 | Phase 3 |
| PUT | `/api/v1/playbooks/{name}` | Playbook 수정 | Phase 3 |
| DELETE | `/api/v1/playbooks/{name}` | Playbook 삭제 | Phase 3 |

---

## 8. 인수 기준 (Acceptance Criteria) — Phase 2 Lite

- [ ] **AC-1**: 7개 Built-in Playbook이 시스템 시작 시 자동 로드됨
- [ ] **AC-2**: GET `/api/v1/playbooks`에서 Built-in 목록 반환
- [ ] **AC-3**: Autonomy L2 인스턴스에서 `lock-remediation` 수동 실행 시 블로킹 세션 kill 성공
- [ ] **AC-4**: Autonomy L0 인스턴스에서 Playbook 실행 시도 시 `status: "blocked"` 반환
- [ ] **AC-5**: Confidence < 0.5 인시던트에 대해 Playbook 자동 트리거 차단
- [ ] **AC-6**: 실행 실패 시 역순 롤백 후 `remediation_logs`에 전체 이력 저장
- [ ] **AC-7**: DB Copilot 진단 결과에서 매칭 Playbook 자동 추천 (UI 표시)
- [ ] **AC-8**: 승인 대기 상태의 Playbook을 UI에서 승인/거부 가능

---

## 9. 의존성

- **선행 Spec**: DM-001 (ERD — `playbooks`, `remediation_logs`), AG-001 (Remediation Agent), FS-AUTO-002 (Adaptive Autonomy — Gate 로직)
- **연동 Spec**: FS-AI-012 (DB Copilot — Playbook 추천/선택), FS-AI-011 (Confidence Score — 차단 게이트)
- **후행 Spec**: Phase 3 Full Playbook (커스텀 YAML + Git + L3/L4)
- **ADR**: ADR-008 (경량 Playbook + DB Copilot 하이브리드)
