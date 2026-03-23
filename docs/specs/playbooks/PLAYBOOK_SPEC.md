# Playbook Spec: Playbook-as-Code YAML 스키마

> **Spec ID**: FS-AUTO-003
> **PRD 참조**: FR-AUTO-001~005
> **상태**: Approved
> **적용 Phase**: Phase 2
> **선행 Spec**: AGENT_SPEC.md (Remediation Agent), ERD.md (playbooks, remediation_logs)

---

## 1. Playbook Lifecycle

```
Draft → Review → Approved → Active → [Deprecated]
                     ↓
              Execution Cycle:
              Triggered → Autonomy Check → [Wait Approval | Execute]
                  Execute → Step 1 → Validate → Step 2 → ...
                      → [Success | Failure → Rollback → Escalate]
```

---

## 2. YAML Schema

```yaml
# playbook-name.yaml
apiVersion: neuraldb/v1
kind: Playbook

metadata:
  name: "lock-remediation"               # kebab-case, unique
  version: "1.0"
  description: "Lock contention 자동 해소"
  author: "human"                         # human | ai-agent
  tags: [performance, lock, postgresql]
  min_autonomy_level: 2                   # 최소 자율 등급 (0~4)
  target_db_types: [postgresql]           # [postgresql, mysql, mssql]
  risk_level: medium                      # low | medium | high | critical

trigger:
  type: metric_threshold                  # metric_threshold | anomaly_detection | schema_change | manual | schedule
  metric: lock_wait_timeout
  condition: ">"
  threshold: 5000                         # ms
  duration: 30s                           # 지속 시간 (일시적 스파이크 무시)
  cooldown: 5m                            # 재트리거 방지 간격

preconditions:
  - name: "check_replication_lag"
    query: "SELECT pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) FROM pg_stat_replication"
    expect: "< 1048576"                   # 1MB 이내
    fail_action: skip                     # skip | alert | escalate

steps:
  - name: "detect_blocking_queries"
    type: sql                             # sql | command | api_call | agent_invoke
    query: |
      SELECT pid, query, wait_event_type, wait_event
      FROM pg_stat_activity
      WHERE state = 'active' AND wait_event_type = 'Lock'
    timeout: 10s
    save_as: blocking_sessions            # 결과를 변수로 저장

  - name: "profile_query_plan"
    type: sql
    query: "EXPLAIN (FORMAT JSON) {{ blocking_sessions[0].query }}"
    timeout: 10s
    save_as: query_plan

  - name: "kill_blocking_session"
    type: sql
    query: "SELECT pg_terminate_backend({{ blocking_sessions[0].pid }})"
    timeout: 5s
    requires_approval: true               # autonomy_level < 3 이면 사람 승인 대기
    rollback:
      query: "-- no rollback needed for kill"
    validate:
      query: "SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock'"
      expect: "< {{ precondition.lock_count }}"

  - name: "apply_index_optimization"
    type: sql
    query: "CREATE INDEX CONCURRENTLY idx_orders_status ON orders(status)"
    timeout: 300s
    requires_approval: true
    rollback:
      query: "DROP INDEX CONCURRENTLY IF EXISTS idx_orders_status"
    validate:
      query: "SELECT count(*) FROM pg_indexes WHERE indexname = 'idx_orders_status'"
      expect: "= 1"

on_success:
  - notify: slack
    message: "Lock remediation 완료: {{ steps.kill_blocking_session.result }}"
  - update_score: +1                      # Playbook 성공 점수 +1

on_failure:
  - rollback: all                         # 모든 step 역순 롤백
  - notify: slack
    severity: critical
    message: "Lock remediation 실패: {{ error }}"
  - escalate: page_sre_team
  - downgrade_autonomy: 1                 # Autonomy Level 1단계 격하

slo_check:
  metric: p99_latency
  baseline_window: 5m                     # 실행 전 5분 평균
  post_window: 5m                         # 실행 후 5분 평균
  max_degradation: 10%                    # 10% 이상 악화 시 실패 판정
```

---

## 3. Field Reference

### metadata

| Field | Type | Required | Description |
|-------|------|---------|-------------|
| `name` | string | Yes | 고유 식별자 (kebab-case) |
| `version` | string | Yes | SemVer |
| `description` | string | Yes | 한줄 설명 |
| `author` | enum | Yes | `human` / `ai-agent` |
| `tags` | string[] | No | 분류 태그 |
| `min_autonomy_level` | int (0~4) | Yes | 이 등급 미만이면 실행 불가 |
| `target_db_types` | string[] | Yes | 지원 DB 유형 |
| `risk_level` | enum | Yes | `low` / `medium` / `high` / `critical` |

### trigger

| Field | Type | Required | Description |
|-------|------|---------|-------------|
| `type` | enum | Yes | 트리거 유형 |
| `metric` | string | If threshold | 메트릭명 |
| `condition` | string | If threshold | `>`, `<`, `>=`, `<=`, `==`, `between` |
| `threshold` | number | If threshold | 임계값 |
| `duration` | duration | No | 지속 시간 (일시 스파이크 무시) |
| `cooldown` | duration | No | 재트리거 방지 간격 |

### steps[]

| Field | Type | Required | Description |
|-------|------|---------|-------------|
| `name` | string | Yes | 단계명 |
| `type` | enum | Yes | `sql` / `command` / `api_call` / `agent_invoke` |
| `query` / `command` | string | Yes | 실행할 SQL 또는 명령 |
| `timeout` | duration | Yes | 최대 실행 시간 |
| `save_as` | string | No | 결과를 변수로 저장 |
| `requires_approval` | bool | No | true면 autonomy_level 체크 |
| `rollback` | object | No | 실패 시 롤백 명령 |
| `validate` | object | No | 실행 후 검증 쿼리 |
| `retry` | object | No | `{count: 3, backoff: "exponential"}` |

### slo_check

| Field | Type | Required | Description |
|-------|------|---------|-------------|
| `metric` | string | Yes | SLO 검증 메트릭 |
| `baseline_window` | duration | Yes | 실행 전 비교 구간 |
| `post_window` | duration | Yes | 실행 후 비교 구간 |
| `max_degradation` | percentage | Yes | 허용 최대 성능 저하 |

---

## 4. Template Variables

Playbook YAML에서 `{{ }}` 구문으로 동적 값을 참조:

| 변수 | 설명 |
|------|------|
| `{{ instance_id }}` | 대상 DB 인스턴스 ID |
| `{{ instance_name }}` | 인스턴스 표시명 |
| `{{ trigger.metric_value }}` | 트리거 시점 메트릭 값 |
| `{{ steps.<step_name>.result }}` | 이전 단계 실행 결과 |
| `{{ blocking_sessions }}` | `save_as`로 저장된 변수 |
| `{{ error }}` | 실패 시 에러 메시지 |
| `{{ now }}` | 현재 UTC timestamp |

---

## 5. Built-in Playbook Templates (Phase 2 제공)

| Playbook | Trigger | Risk | Description |
|----------|---------|------|-------------|
| `lock-remediation` | lock_wait > 5s | medium | 블로킹 세션 감지 → kill → 인덱스 추천 |
| `index-optimization` | seq_scan_ratio > 80% | medium | Missing index 감지 → CREATE CONCURRENTLY |
| `replication-lag` | replication_lag > 5s | high | WAL sender 점검 → 파라미터 조정 |
| `connection-pool` | connections > 80% max | medium | idle 세션 정리 → 풀 크기 조정 |
| `vacuum-maintenance` | dead_tuples > threshold | low | bloat 분석 → VACUUM → REINDEX |
| `query-timeout` | query_duration > 30s | low | 느린 쿼리 식별 → EXPLAIN → 최적화 제안 |
| `memory-pressure` | hit_ratio < 95% | high | 캐시 분석 → shared_buffers 조정 |

---

## 6. Git Versioning

```
backend/playbooks/
├── lock-remediation.yaml
├── index-optimization.yaml
├── replication-lag.yaml
└── ...
```

- 모든 Playbook은 Git으로 버전 관리
- 변경 시 PR → 리뷰 → 머지 워크플로우
- `playbooks.git_sha` 필드에 현재 커밋 해시 저장
- AI가 자동 생성한 Playbook은 `author: ai-agent` + 사람 리뷰 필수

---

### Confidence Score 연동 (v3.3)

Playbook 트리거 및 실행에 Confidence Score 정책을 적용합니다.

#### trigger 섹션 확장

```yaml
# Spec: FR-AI-011, FR-AI-012
trigger:
  condition: "anomaly_type == 'query_performance_degradation'"
  min_confidence: 0.8  # 최소 Confidence Score (기본값: 0.8)
  show_reasoning: true  # 실행 전 Reasoning Chain 표시
```

#### execution 섹션 확장

```yaml
execution:
  autonomy_level: 2
  confidence_override: true  # Confidence < 0.5 시 autonomy_level을 0으로 강제 하향
```

#### remediation_logs 확장 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| `confidence_score` | float | 트리거 시점의 MTL Confidence Score |
| `reasoning_chain` | list[str] | AI 추론 과정 (Explainable AI) |
| `was_auto_blocked` | bool | Confidence 부족으로 자동 차단되었는지 |
