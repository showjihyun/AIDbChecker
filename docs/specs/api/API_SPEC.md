# API Spec: NeuralDB REST & GraphQL & WebSocket

> **Spec ID**: API-001
> **PRD 참조**: FR-DASH-001~005, FR-AI-001~014, FR-AUTO-001~005, FR-ALERT-001~005, FR-ADMIN-001~005
> **상태**: Approved
> **Base URL**: `/api/v1`
> **GraphQL**: `/graphql`
> **WebSocket**: `/ws`

---

## 1. Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/login` | JWT 토큰 발급 (email + password) |
| POST | `/api/v1/auth/refresh` | Access Token 갱신 |
| POST | `/api/v1/auth/logout` | 토큰 무효화 |
| GET | `/api/v1/auth/me` | 현재 사용자 정보 |
| POST | `/api/v1/auth/sso/callback` | SSO/OIDC 콜백 |

**Token**: `Authorization: Bearer <JWT>`
**TTL**: Access 30분, Refresh 7일

---

## 2. DB Instances

| Method | Endpoint | Description | Role |
|--------|----------|-------------|------|
| GET | `/api/v1/instances` | 인스턴스 목록 조회 | Viewer+ |
| POST | `/api/v1/instances` | 인스턴스 등록 | DB Admin+ |
| GET | `/api/v1/instances/{id}` | 인스턴스 상세 | Viewer+ |
| PUT | `/api/v1/instances/{id}` | 인스턴스 수정 | DB Admin+ |
| DELETE | `/api/v1/instances/{id}` | 인스턴스 삭제 | Super Admin |
| POST | `/api/v1/instances/{id}/test-connection` | 연결 테스트 | DB Admin+ |
| PUT | `/api/v1/instances/{id}/autonomy-level` | 자율 등급 변경 | DB Admin+ |

### Response: `GET /api/v1/instances`
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "pg-prod-01",
      "db_type": "postgresql",
      "host": "10.0.1.100",
      "port": 5432,
      "environment": "production",
      "is_active": true,
      "autonomy_level": 3,
      "health_status": "healthy",
      "metadata": {}
    }
  ],
  "total": 52,
  "has_next": true,
  "next_cursor": "eyJpZCI6..."
}
```

---

## 3. Monitoring / Metrics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/instances/{id}/metrics` | 메트릭 조회 (time range, category) |
| GET | `/api/v1/instances/{id}/metrics/latest` | 최신 메트릭 스냅샷 |
| GET | `/api/v1/instances/{id}/metrics/summary` | 요약 통계 (avg, max, p95, p99) |

### Query Parameters: `GET /api/v1/instances/{id}/metrics`
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `from` | `ISO8601` | -1h | 시작 시각 |
| `to` | `ISO8601` | now | 종료 시각 |
| `category` | `string` | hot | `hot` / `warm` / `cold` |
| `resolution` | `string` | auto | `1s` / `10s` / `1m` / `1h` / `1d` / `auto` |

---

## 4. ASH (Active Session History)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/instances/{id}/ash` | ASH 세션 샘플 조회 |
| GET | `/api/v1/instances/{id}/ash/heatmap` | Wait Event 히트맵 데이터 |
| GET | `/api/v1/instances/{id}/ash/wait-breakdown` | Wait 유형별 집계 |
| GET | `/api/v1/instances/{id}/ash/sessions/{pid}` | 특정 세션 상세 |

### Response: `GET /api/v1/instances/{id}/ash/heatmap`
```json
{
  "time_range": { "from": "...", "to": "..." },
  "resolution": "1s",
  "categories": ["CPU", "I/O", "Lock", "Network"],
  "data": [
    { "time": "2026-03-21T14:32:00Z", "CPU": 0.3, "IO": 0.7, "Lock": 0.9, "Network": 0.1 }
  ]
}
```

---

## 5. Incidents / Diagnosis

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/incidents` | 인시던트 목록 (severity, status 필터) |
| GET | `/api/v1/incidents/{id}` | 인시던트 상세 |
| PUT | `/api/v1/incidents/{id}/status` | 상태 변경 (acknowledge, resolve, close) |
| POST | `/api/v1/incidents/{id}/diagnose` | AI RCA 실행 요청 |
| GET | `/api/v1/incidents/{id}/rca` | RCA 결과 조회 |

### Response: `GET /api/v1/incidents/{id}/rca`
```json
{
  "id": "uuid",
  "incident_id": "uuid",
  "root_cause": "High Lock Contention in 'orders' table...",
  "confidence": 0.94,
  "causal_chain": [
    { "node": "Schema Change", "type": "trigger", "description": "ALTER TABLE orders ADD COLUMN tax_id" },
    { "node": "Sequential Scan", "type": "effect", "description": "Missing index on new column" },
    { "node": "Lock Wait", "type": "effect", "description": "Row-level lock contention" },
    { "node": "Latency Spike", "type": "symptom", "description": "P99 latency 45ms → 1200ms" }
  ],
  "recommendations": [...],
  "ai_model": "claude-sonnet-4-20250514",
  "similar_incidents": [...]
}
```

---

## 6. Topology

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/topology` | 전체 토폴로지 그래프 |
| GET | `/api/v1/topology/nodes` | 노드 목록 |
| GET | `/api/v1/topology/edges` | 간선 목록 |
| GET | `/api/v1/topology/impact/{node_id}` | 영향 범위 분석 (upstream/downstream) |

---

## 7. Playbooks

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/playbooks` | Playbook 목록 |
| POST | `/api/v1/playbooks` | Playbook 생성 |
| GET | `/api/v1/playbooks/{id}` | Playbook 상세 (YAML 포함) |
| PUT | `/api/v1/playbooks/{id}` | Playbook 수정 |
| DELETE | `/api/v1/playbooks/{id}` | Playbook 삭제 |
| POST | `/api/v1/playbooks/{id}/execute` | Playbook 실행 (dry_run 지원) |
| GET | `/api/v1/playbooks/{id}/history` | 실행 이력 |

### Request: `POST /api/v1/playbooks/{id}/execute`
```json
{
  "instance_id": "uuid",
  "dry_run": true,
  "override_autonomy_level": null
}
```

---

## 8. NL2SQL

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/nl2sql/query` | 자연어 → SQL 변환 + 실행 |
| POST | `/api/v1/nl2sql/explain` | SQL 실행 계획 자연어 해석 |
| POST | `/api/v1/nl2sql/optimize` | SQL 최적화 제안 |
| GET | `/api/v1/nl2sql/history` | 질의 이력 |

### Request: `POST /api/v1/nl2sql/query`
```json
{
  "question": "오늘 가장 느린 쿼리 TOP 5 보여줘",
  "instance_id": "uuid",
  "execute": true
}
```

### Response:
```json
{
  "natural_query": "오늘 가장 느린 쿼리 TOP 5 보여줘",
  "generated_sql": "SELECT query, mean_exec_time ... ORDER BY mean_exec_time DESC LIMIT 5",
  "result": { "columns": [...], "rows": [...] },
  "ai_model": "gpt-4o"
}
```

---

## 9. Self-Healing / Remediation

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/remediation/queue` | 활성 대기열 |
| GET | `/api/v1/remediation/logs` | 감사 로그 |
| POST | `/api/v1/remediation/{id}/halt` | 실행 중 작업 중단 |
| POST | `/api/v1/remediation/{id}/rollback` | 롤백 실행 |

---

## 10. Schema Changes

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/instances/{id}/schema-changes` | DDL 변경 이력 |
| GET | `/api/v1/instances/{id}/schema-changes/{id}/impact` | 변경 영향도 분석 (before/after) |

---

## 11. Baselines

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/instances/{id}/baselines` | 베이스라인 목록 |
| POST | `/api/v1/instances/{id}/baselines/retrain` | 재학습 트리거 |

---

## 12. AI Advanced Endpoints

### MTL RCA (FR-AI-010)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/mtl/predict` | DB Admin+ | MTL 4-Head 동시 추론 실행 |
| GET | `/api/v1/mtl/predictions` | Operator+ | MTL 예측 이력 조회 |
| GET | `/api/v1/mtl/predictions/{id}` | Operator+ | MTL 예측 상세 |
| POST | `/api/v1/mtl/predictions/{id}/feedback` | Operator+ | 운영자 피드백 (👍/👎) |
| GET | `/api/v1/mtl/predictions/{id}/reasoning` | Operator+ | Reasoning Chain 상세 |

### Confidence Score & XAI (FR-AI-011)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/confidence/stats` | DB Admin+ | Confidence 통계 조회 |

### DB Copilot (FR-AI-012, Phase 2)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/copilot/diagnose` | DB Admin+ | ToT 진단 실행 |
| POST | `/api/v1/copilot/sessions/{id}/execute` | DB Admin+ | 승인 후 액션 실행 |
| GET | `/api/v1/copilot/sessions` | Operator+ | Copilot 세션 이력 |

### LLM Observability (FR-AI-013, Phase 2)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/llm-observability/summary` | Super Admin+ | LLM 메트릭 요약 |
| GET | `/api/v1/llm-observability/timeseries` | Super Admin+ | LLM 메트릭 시계열 |
| GET | `/api/v1/llm-observability/hallucinations` | Super Admin+ | 할루시네이션 로그 |
| PUT | `/api/v1/llm-observability/budget` | Super Admin | 비용 예산 설정 |

### Lightweight RAG (FR-AI-002 MVP 확장)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/rag/search` | Operator+ | 유사 인시던트 검색 |
| GET | `/api/v1/rag/status` | Operator+ | 임베딩 현황 조회 |

---

## 13. Users & Admin

| Method | Endpoint | Description | Role |
|--------|----------|-------------|------|
| GET | `/api/v1/users` | 사용자 목록 | Super Admin |
| POST | `/api/v1/users` | 사용자 생성 | Super Admin |
| PUT | `/api/v1/users/{id}` | 사용자 수정 | Super Admin |
| DELETE | `/api/v1/users/{id}` | 사용자 삭제 | Super Admin |
| GET | `/api/v1/audit-logs` | 감사 로그 조회 | DB Admin+ |

---

## 14. System Health (Self-Monitoring)

> **대상 DB 메트릭이 아닌, NeuralDB 시스템 자체의 헬스 상태.**
> Prometheus에서 수집된 자체 메트릭을 프론트엔드에 제공.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/system/health` | 시스템 전체 헬스 체크 (UP/DEGRADED/DOWN) |
| GET | `/api/v1/system/health/details` | 컴포넌트별 헬스 상세 (DB, Valkey, Kafka, Celery) |
| GET | `/api/v1/system/metrics` | Prometheus 메트릭 프록시 (대시보드용) |
| GET | `/api/v1/system/agents/status` | 에이전트별 실행 상태/성공률 |
| GET | `/api/v1/system/workers` | Celery Worker 상태/큐 깊이 |
| GET | `/metrics` | Prometheus scrape 엔드포인트 (직접 노출) |

### Response: `GET /api/v1/system/health`
```json
{
  "status": "healthy",
  "uptime_seconds": 86400,
  "version": "1.0.0",
  "components": {
    "database": { "status": "healthy", "latency_ms": 2.1 },
    "valkey": { "status": "healthy", "latency_ms": 0.3 },
    "kafka": { "status": "healthy", "consumer_lag": 12 },
    "celery": { "status": "healthy", "active_workers": 4, "queued_tasks": 3 }
  }
}
```

### Response: `GET /api/v1/system/agents/status`
```json
{
  "agents": [
    {
      "id": "agent-monitoring",
      "status": "running",
      "last_execution": "2026-03-21T14:32:00Z",
      "success_rate_24h": 0.998,
      "avg_duration_ms": 45,
      "instances_managed": 52
    },
    {
      "id": "agent-diagnosis",
      "status": "idle",
      "last_execution": "2026-03-21T14:28:11Z",
      "success_rate_24h": 0.95,
      "avg_duration_ms": 3200
    }
  ]
}
```

---

## 15. Alerts / Notifications

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/alerts/channels` | 알림 채널 목록 |
| POST | `/api/v1/alerts/channels` | 알림 채널 추가 (Slack, Email, Webhook) |
| PUT | `/api/v1/alerts/policies` | 에스컬레이션 정책 설정 |
| POST | `/api/v1/alerts/test` | 테스트 알림 발송 |

---

## 16. WebSocket Namespaces

| Namespace | Events (Server → Client) | Description |
|-----------|--------------------------|-------------|
| `/ws/metrics` | `metric:update`, `metric:spike` | 1초 실시간 메트릭 |
| `/ws/incidents` | `incident:new`, `incident:update`, `incident:resolve` | 인시던트 실시간 피드 |
| `/ws/agents` | `agent:status`, `agent:action`, `agent:complete` | 에이전트 실행 상태 |
| `/ws/ash` | `ash:sample`, `ash:heatmap` | 실시간 ASH 데이터 |
| `/ws/remediation` | `remediation:start`, `remediation:progress`, `remediation:complete` | 자가 치유 진행 상황 |

**Auth**: JWT token in handshake `auth` parameter
**Rooms**: `instance:{instance_id}` — 인스턴스별 격리

---

## 17. GraphQL (Strawberry)

`/graphql` 엔드포인트로 제공. REST와 동일 데이터를 쿼리 가능.
주로 대시보드의 복합 조회(여러 엔티티 조인)에 사용.

```graphql
type Query {
  instances(filter: InstanceFilter): InstanceConnection!
  instance(id: UUID!): Instance
  incidents(status: IncidentStatus, severity: Severity): IncidentConnection!
  topology: TopologyGraph!
  metrics(instanceId: UUID!, from: DateTime!, to: DateTime!): [MetricSample!]!
}

type Subscription {
  metricUpdated(instanceId: UUID!): MetricSample!
  incidentCreated: Incident!
  remediationProgress(logId: UUID!): RemediationLog!
}
```

---

## 18. Response Schemas (MVP 필수)

### Instance Response
```json
{
  "id": "uuid",
  "name": "pg-prod-01",
  "host": "192.168.1.10",
  "port": 5432,
  "db_name": "production",
  "db_type": "postgresql",
  "status": "healthy",
  "ash_enabled": true,
  "autonomy_level": 2,
  "connection_config": {},
  "latest_metrics": {
    "cpu_usage": 45.2,
    "memory_usage": 72.1,
    "active_connections": 42,
    "tps": 1240,
    "buffer_hit_ratio": 99.2
  },
  "created_at": "2026-03-21T00:00:00Z",
  "updated_at": "2026-03-21T12:00:00Z"
}
```

### Metrics Response
```json
{
  "instance_id": "uuid",
  "resolution": "1s",
  "from": "2026-03-21T14:00:00Z",
  "to": "2026-03-21T15:00:00Z",
  "samples": [
    {
      "sampled_at": "2026-03-21T14:32:01Z",
      "metrics": {
        "cpu_usage": 45.2,
        "memory_usage": 72.1,
        "active_connections": 42,
        "tps": 1240,
        "buffer_hit_ratio": 99.2
      }
    }
  ]
}
```

### Incident List Response
```json
{
  "items": [
    {
      "id": "uuid",
      "instance_id": "uuid",
      "instance_name": "pg-prod-01",
      "severity": "CRITICAL",
      "status": "open",
      "title": "CPU usage anomaly",
      "description": "CPU 95% (baseline: 40-60%)",
      "anomaly_type": "resource_exhaustion",
      "detected_at": "2026-03-21T14:32:00Z",
      "resolved_at": null,
      "prediction": {
        "confidence": 0.87,
        "root_cause": "Missing index on orders.created_at",
        "suggested_actions_count": 2
      }
    }
  ],
  "total": 42,
  "has_next": true,
  "next_cursor": "eyJpZCI6..."
}
```

### NL2SQL Response
```json
{
  "question": "오늘 가장 느린 쿼리 TOP 5",
  "generated_sql": "SELECT query, mean_exec_time, calls FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 5",
  "is_read_only": true,
  "columns": ["query", "mean_exec_time", "calls"],
  "rows": [
    ["SELECT * FROM orders WHERE...", 12.843, 4521],
    ["UPDATE inventory SET...", 8.234, 1203]
  ],
  "execution_time_ms": 45,
  "row_count": 5
}
```

### ASH Heatmap Response
```json
{
  "instance_id": "uuid",
  "from": "2026-03-21T14:00:00Z",
  "to": "2026-03-21T15:00:00Z",
  "resolution": "1m",
  "categories": ["CPU", "I/O", "Lock", "Network"],
  "timestamps": ["14:00", "14:01", "14:02"],
  "values": [[2,5,8,1], [3,4,12,0], [1,6,3,2]]
}
```

### Wait Breakdown Response
```json
{
  "instance_id": "uuid",
  "breakdown": [
    {"category": "Lock", "percentage": 45.2, "count": 1234, "color": "#f97316"},
    {"category": "I/O", "percentage": 30.1, "count": 823, "color": "#0ea5e9"},
    {"category": "CPU", "percentage": 24.7, "count": 675, "color": "#d0bcff"}
  ]
}
```

### JWT Token Structure

```json
{
  "sub": "user-uuid",
  "email": "admin@neuraldb.io",
  "role": "super_admin",
  "iat": 1711022400,
  "exp": 1711024200,
  "type": "access"
}
```

Refresh token:
```json
{
  "sub": "user-uuid",
  "iat": 1711022400,
  "exp": 1711627200,
  "type": "refresh"
}
```

---

## 19. Common Patterns

### Pagination (Cursor-based)
```json
{
  "items": [...],
  "total": 100,
  "has_next": true,
  "next_cursor": "base64-encoded-cursor"
}
```
Query: `?cursor={next_cursor}&limit=20`

### Error Response
```json
{
  "detail": "Instance not found",
  "error_code": "INSTANCE_NOT_FOUND",
  "status_code": 404
}
```

### RBAC Roles
| Role | 권한 |
|------|------|
| `super_admin` | 전체 시스템 관리 |
| `db_admin` | 인스턴스 관리, Playbook 실행, 자율 등급 변경 |
| `operator` | 인시던트 처리, NL2SQL, 읽기+제한된 쓰기 |
| `viewer` | 읽기 전용 |
| `api_user` | API Key 기반, 제한된 엔드포인트 |
