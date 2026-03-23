# Kafka Event Spec: NeuralDB 메시징 설계

> **Spec ID**: PROTO-KAFKA-001
> **PRD 참조**: FR-DASH-001, FR-DB-001, FR-ALERT-001~003, FR-AUTO-001
> **상태**: Approved
> **Broker**: Apache Kafka 3.7+ (KRaft mode, no Zookeeper)

---

## 1. Overview

Kafka는 NeuralDB에서 **3가지 역할**을 수행합니다:

```
1. 메트릭 버퍼: Adapter → Kafka → Metric Ingestion Service → PostgreSQL
2. 이벤트 버스: 인시던트/알림/스키마 변경 이벤트 전파
3. Agent 통신: A2A 메시지 전달 (Phase 3)
```

> **MVP (Phase 1)**: 역할 1, 2만 사용. A2A는 Phase 3.

---

## 2. Topic Naming Convention

```
neuraldb.{domain}.{event-type}

예:
  neuraldb.metrics.hot
  neuraldb.metrics.warm
  neuraldb.incidents.created
  neuraldb.alerts.dispatch
```

---

## 3. Topic Definitions

### 3.1 메트릭 수집 (MVP)

| Topic | Producer | Consumer | Partitions | Retention |
|-------|----------|----------|-----------|-----------|
| `neuraldb.metrics.hot` | Celery Collector | MetricIngestionService | 10 | 1h |
| `neuraldb.metrics.warm` | Celery Collector | MetricIngestionService | 4 | 6h |
| `neuraldb.metrics.cold` | Celery Collector | MetricIngestionService | 2 | 24h |
| `neuraldb.metrics.ash` | ASH Collector | ASHIngestionService | 10 | 1h |

**Partition Key**: `instance_id` (동일 인스턴스 메트릭이 같은 파티션 → 순서 보장)

#### Payload: `neuraldb.metrics.hot`
```json
{
  "instance_id": "uuid",
  "sampled_at": "2026-03-21T14:32:01.000Z",
  "category": "hot",
  "metrics": {
    "cpu_usage": 45.2,
    "memory_usage": 72.1,
    "active_connections": 42,
    "tps": 1240,
    "buffer_hit_ratio": 99.2,
    "transactions_committed": 15234,
    "transactions_rolled_back": 3
  }
}
```

#### Payload: `neuraldb.metrics.ash`
```json
{
  "instance_id": "uuid",
  "sampled_at": "2026-03-21T14:32:01.000Z",
  "sessions": [
    {
      "pid": 8829,
      "query": "SELECT * FROM orders WHERE status = 'PENDING'...",
      "query_hash": 1234567890,
      "state": "active",
      "wait_event_type": "Lock",
      "wait_event": "transactionid",
      "backend_type": "client backend",
      "client_addr": "10.0.1.50",
      "application_name": "order-service",
      "query_start": "2026-03-21T14:31:59.800Z",
      "duration_ms": 1200.5
    }
  ]
}
```

### 3.2 이벤트 버스 (MVP)

| Topic | Producer | Consumer | Partitions | Retention |
|-------|----------|----------|-----------|-----------|
| `neuraldb.incidents.lifecycle` | AnomalyDetector | IncidentService, AlertEngine, WebSocket | 4 | 7d |
| `neuraldb.alerts.dispatch` | AlertEngine | SlackNotifier, WebhookNotifier | 2 | 24h |
| `neuraldb.schema.changes` | SchemaTracker | IncidentService, AuditLogger | 2 | 7d |
| `neuraldb.audit.events` | 모든 서비스 | AuditLogWriter | 4 | 30d |

#### Payload: `neuraldb.incidents.lifecycle`
```json
{
  "event_type": "created",
  "incident": {
    "id": "uuid",
    "instance_id": "uuid",
    "severity": "critical",
    "status": "open",
    "title": "CPU usage 95% (baseline: 40~60%)",
    "source": "ai_baseline",
    "metric_type": "cpu_usage",
    "metric_value": 95.2,
    "baseline_value": 50.0,
    "detected_at": "2026-03-21T14:32:01.000Z"
  },
  "timestamp": "2026-03-21T14:32:01.100Z"
}
```
`event_type`: `created` | `acknowledged` | `resolved` | `closed`

#### Payload: `neuraldb.alerts.dispatch`
```json
{
  "channel_type": "slack",
  "channel_config": { "webhook_url": "..." },
  "severity": "critical",
  "title": "🔴 CRITICAL | pg-prod-01",
  "body": "CPU 사용률 95% (베이스라인: 40~60%)\nAI 판단: 워크로드 급증",
  "incident_id": "uuid",
  "instance_name": "pg-prod-01",
  "timestamp": "2026-03-21T14:32:01.200Z"
}
```

#### Payload: `neuraldb.schema.changes`
```json
{
  "instance_id": "uuid",
  "change_type": "ALTER",
  "object_type": "TABLE",
  "object_name": "orders",
  "ddl_command": "ALTER TABLE orders ADD COLUMN tax_id VARCHAR(20)",
  "executed_by": "dev_ops_bot",
  "detected_at": "2026-03-21T14:32:00.000Z"
}
```

### 3.3 Agent 통신 (Phase 3)

| Topic | Producer | Consumer | Partitions | Retention |
|-------|----------|----------|-----------|-----------|
| `neuraldb.a2a.tasks` | 모든 Agent | Task Orchestrator | 4 | 7d |
| `neuraldb.a2a.results` | 모든 Agent | 요청 Agent | 4 | 7d |

> Phase 3에서 `docs/specs/protocols/A2A_PROTOCOL.md` 참조.

---

## 4. Consumer Group 설계

| Group ID | 구독 Topics | Instances | 역할 |
|----------|------------|-----------|------|
| `metric-ingestor` | `neuraldb.metrics.*` | 2 | 메트릭 → PostgreSQL 저장 |
| `ash-ingestor` | `neuraldb.metrics.ash` | 2 | ASH → PostgreSQL 저장 |
| `incident-processor` | `neuraldb.incidents.lifecycle` | 1 | 인시던트 후처리 |
| `alert-dispatcher` | `neuraldb.alerts.dispatch` | 1 | 알림 발송 |
| `audit-writer` | `neuraldb.audit.events` | 1 | 감사 로그 저장 |
| `websocket-relay` | `neuraldb.incidents.*`, `neuraldb.metrics.hot` | 1 | WebSocket 실시간 전달 |

---

## 5. 직렬화

| 형식 | 용도 |
|------|------|
| **JSON** | 모든 토픽 (Phase 1~2) |
| Protobuf | 검토 예정 (Phase 4, 대규모 시 성능 최적화) |

```python
# Producer
import json
from aiokafka import AIOKafkaProducer

producer = AIOKafkaProducer(
    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
    value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
    key_serializer=lambda k: k.encode('utf-8') if k else None,
)
await producer.send(
    topic="neuraldb.metrics.hot",
    key=instance_id,          # Partition key
    value=metric_payload,
)
```

---

## 6. 운영 설정

### MVP Docker Compose
```yaml
kafka:
  image: bitnami/kafka:3.8
  environment:
    KAFKA_CFG_NODE_ID: 0
    KAFKA_CFG_PROCESS_ROLES: controller,broker
    KAFKA_CFG_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
    KAFKA_CFG_CONTROLLER_QUORUM_VOTERS: 0@kafka:9093
    KAFKA_CFG_CONTROLLER_LISTENER_NAMES: CONTROLLER
    KAFKA_CFG_AUTO_CREATE_TOPICS_ENABLE: "false"
    KAFKA_CFG_NUM_PARTITIONS: 4
    KAFKA_CFG_DEFAULT_REPLICATION_FACTOR: 1
    KAFKA_CFG_LOG_RETENTION_HOURS: 24
```

### Topic 초기화 스크립트
```bash
# infra/scripts/init-kafka-topics.sh
kafka-topics.sh --create --topic neuraldb.metrics.hot --partitions 10 --replication-factor 1
kafka-topics.sh --create --topic neuraldb.metrics.warm --partitions 4 --replication-factor 1
kafka-topics.sh --create --topic neuraldb.metrics.cold --partitions 2 --replication-factor 1
kafka-topics.sh --create --topic neuraldb.metrics.ash --partitions 10 --replication-factor 1
kafka-topics.sh --create --topic neuraldb.incidents.lifecycle --partitions 4 --replication-factor 1
kafka-topics.sh --create --topic neuraldb.alerts.dispatch --partitions 2 --replication-factor 1
kafka-topics.sh --create --topic neuraldb.schema.changes --partitions 2 --replication-factor 1
kafka-topics.sh --create --topic neuraldb.audit.events --partitions 4 --replication-factor 1
```

> `AUTO_CREATE_TOPICS_ENABLE=false` — 오타 토픽 자동 생성 방지. 명시적 생성만 허용.
