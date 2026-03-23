# Data Model Spec: NeuralDB ERD

> **Spec ID**: DM-001
> **PRD 참조**: FR-DB-001, FR-DB-004, FR-DASH-001~005, FR-AI-001~014, FR-AUTO-001~005
> **상태**: Approved
> **DB**: PostgreSQL 16 (단일 인스턴스 — 메타 + 메트릭 + 벡터)

---

## 1. ER Diagram (Conceptual)

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────┐
│  db_instances │──1:N──│  metric_samples   │       │   users      │
│              │       │  (PARTITIONED)    │       │              │
└──────┬───────┘       └──────────────────┘       └──────┬───────┘
       │                                                  │
       │1:N            ┌──────────────────┐              │1:N
       ├──────────────│  active_sessions  │              │
       │              │  (PARTITIONED)    │       ┌──────┴───────┐
       │              └──────────────────┘       │  audit_logs   │
       │                                         └──────────────┘
       │1:N            ┌──────────────────┐
       ├──────────────│   incidents       │──1:N──┐
       │              └──────┬───────────┘       │
       │                     │1:1                 │
       │              ┌──────┴───────────┐       │
       │              │  rca_results      │       │
       │              └──────────────────┘       │
       │                                         │
       │1:N            ┌──────────────────┐      │
       ├──────────────│  schema_changes   │      │
       │              └──────────────────┘      │
       │                                         │
       │              ┌──────────────────┐       │N:1
       │              │   playbooks       │──────┤
       │              └──────┬───────────┘       │
       │                     │1:N                 │
       │              ┌──────┴───────────┐       │
       │              │ remediation_logs  │───────┘
       │              └──────────────────┘
       │
       │1:N            ┌──────────────────┐
       ├──────────────│ topology_nodes    │──N:M──┐
       │              └──────────────────┘       │
       │                                   ┌──────┴───────┐
       │                                   │ topology_edges│
       │                                   └──────────────┘
       │1:N
       ├──────────────┐
       │       ┌──────┴───────────┐
       │       │   baselines       │
       │       └──────────────────┘
       │
       │       ┌──────────────────┐
       └──────│ nl2sql_histories  │
              └──────────────────┘

       ┌──────────────────┐
       │ rag_documents     │  (pgvector embeddings)
       └──────────────────┘

       ┌──────────────────┐       ┌──────────────────┐
       │ alert_channels    │──1:N──│ alert_policies    │
       └──────────────────┘       └──────────────────┘
```

---

### SQLAlchemy 2.0 ORM 기본 패턴

```python
# backend/app/models/base.py
# Spec: DM-001

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, func
from uuid import UUID, uuid4

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

class UUIDMixin:
    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4
    )
```

### DB 커넥션 풀 설정

```python
# backend/app/db/session.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,         # 20
    max_overflow=settings.DB_POOL_OVERFLOW,   # 10
    pool_timeout=settings.DB_POOL_TIMEOUT,    # 30s
    pool_recycle=settings.DB_POOL_RECYCLE,    # 3600s
    echo=settings.DB_ECHO,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
```

---

## 2. Table Definitions

### 2.1 `db_instances` — 모니터링 대상 DB 인스턴스

| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| `id` | `UUID` | PK, `gen_random_uuid()` | |
| `name` | `VARCHAR(255)` | NOT NULL, UNIQUE | 인스턴스 표시명 |
| `db_type` | `VARCHAR(20)` | NOT NULL | `postgresql` / `mysql` / `mssql` |
| `host` | `VARCHAR(255)` | NOT NULL | 호스트 주소 |
| `port` | `INTEGER` | NOT NULL, DEFAULT 5432 | 포트 |
| `database_name` | `VARCHAR(255)` | NOT NULL | 데이터베이스명 |
| `cluster_id` | `VARCHAR(100)` | | 클러스터 그룹 식별자 |
| `environment` | `VARCHAR(20)` | NOT NULL | `production` / `staging` / `development` |
| `connection_config` | `JSONB` | NOT NULL, DEFAULT '{}' | SSL, 풀 설정 등 (암호화 저장) |
| `is_active` | `BOOLEAN` | NOT NULL, DEFAULT true | 모니터링 활성 여부 |
| `autonomy_level` | `SMALLINT` | NOT NULL, DEFAULT 0 | 현재 자율 등급 (0~4) |
| `metadata` | `JSONB` | DEFAULT '{}' | 태그, 라벨 등 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |

**Indexes**:
- `ix_db_instances_cluster` ON (`cluster_id`)
- `ix_db_instances_active` ON (`is_active`) WHERE `is_active = true`

---

### 2.2 `metric_samples` — 1초 메트릭 스냅샷 (PARTITIONED)

| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| `id` | `UUID` | `gen_random_uuid()` | |
| `instance_id` | `UUID` | NOT NULL, FK → db_instances | |
| `sampled_at` | `TIMESTAMPTZ` | NOT NULL | 샘플링 시각 |
| `category` | `VARCHAR(10)` | NOT NULL | `hot` / `warm` / `cold` |
| `metrics` | `JSONB` | NOT NULL | cpu, memory, iops, connections, tps 등 |

**Primary Key**: `(id, sampled_at)` — 파티션 테이블은 PK에 파티션 키 포함 필수
**Partitioning**: `PARTITION BY RANGE (sampled_at)` — pg_partman 일별 자동 파티션
**Retention**: hot=7일, warm=90일, cold=365일
**Indexes**:
- `ix_metric_instance_time` ON (`instance_id`, `sampled_at`)

---

### 2.3 `active_sessions` — ASH 1초 샘플링 (PARTITIONED)

| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| `id` | `UUID` | `gen_random_uuid()` | |
| `instance_id` | `UUID` | NOT NULL, FK → db_instances | |
| `sampled_at` | `TIMESTAMPTZ` | NOT NULL | 샘플링 시각 |
| `pid` | `INTEGER` | NOT NULL | 백엔드 프로세스 ID |
| `query` | `TEXT` | | 실행 중 쿼리 (truncated) |
| `query_hash` | `BIGINT` | | pg_stat_statements queryid |
| `state` | `VARCHAR(20)` | NOT NULL | `active` / `idle` / `idle in transaction` / `locked` |
| `wait_event_type` | `VARCHAR(30)` | | CPU, LWLock, Lock, I/O, IPC 등 |
| `wait_event` | `VARCHAR(100)` | | 상세 wait event |
| `backend_type` | `VARCHAR(30)` | | client backend, autovacuum 등 |
| `client_addr` | `INET` | | 클라이언트 IP |
| `application_name` | `VARCHAR(255)` | | 연결 앱 이름 |
| `query_start` | `TIMESTAMPTZ` | | 쿼리 시작 시각 |
| `duration_ms` | `FLOAT` | | 경과 시간 (ms) |

**Primary Key**: `(id, sampled_at)` — 파티션 테이블은 PK에 파티션 키 포함 필수
**Partitioning**: `PARTITION BY RANGE (sampled_at)` — 일별
**Retention**: 7일 원본, Materialized View로 다운샘플링
**Indexes**:
- `ix_ash_instance_time` ON (`instance_id`, `sampled_at`)
- `ix_ash_wait_event` ON (`wait_event_type`, `wait_event`)
- `ix_ash_state` ON (`state`) WHERE `state != 'idle'`

---

### 2.4 `incidents` — 탐지된 이상/장애

| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| `id` | `UUID` | PK, `gen_random_uuid()` | |
| `instance_id` | `UUID` | NOT NULL, FK → db_instances | |
| `severity` | `VARCHAR(10)` | NOT NULL | `critical` / `warning` / `notice` / `info` |
| `status` | `VARCHAR(15)` | NOT NULL, DEFAULT 'open' | `open` / `acknowledged` / `in_progress` / `resolved` / `closed` |
| `title` | `VARCHAR(500)` | NOT NULL | 인시던트 제목 |
| `description` | `TEXT` | | 상세 설명 |
| `source` | `VARCHAR(30)` | NOT NULL | `ai_baseline` / `threshold` / `manual` / `schema_change` |
| `metric_type` | `VARCHAR(50)` | | 관련 메트릭 유형 |
| `metric_value` | `FLOAT` | | 탐지 시점 메트릭 값 |
| `baseline_value` | `FLOAT` | | 베이스라인 기대값 |
| `detected_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | 탐지 시각 |
| `acknowledged_at` | `TIMESTAMPTZ` | | 확인 시각 |
| `resolved_at` | `TIMESTAMPTZ` | | 해결 시각 |
| `resolved_by` | `UUID` | FK → users | 해결자 (사용자 또는 에이전트) |
| `metadata` | `JSONB` | DEFAULT '{}' | 추가 컨텍스트 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |

**Indexes**:
- `ix_incidents_instance_status` ON (`instance_id`, `status`)
- `ix_incidents_severity` ON (`severity`) WHERE `status IN ('open', 'in_progress')`
- `ix_incidents_detected` ON (`detected_at` DESC)

---

### 2.5 `rca_results` — AI 근본 원인 분석 결과

| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| `id` | `UUID` | PK, `gen_random_uuid()` | |
| `incident_id` | `UUID` | NOT NULL, UNIQUE, FK → incidents | 1:1 관계 |
| `root_cause` | `TEXT` | NOT NULL | 근본 원인 설명 |
| `confidence` | `FLOAT` | NOT NULL | 신뢰도 (0.0~1.0) |
| `causal_chain` | `JSONB` | NOT NULL | 인과 관계 체인 `[{node, type, description}]` |
| `similar_incidents` | `JSONB` | DEFAULT '[]' | RAG 검색된 유사 과거 사례 |
| `recommendations` | `JSONB` | NOT NULL | 추천 조치 목록 |
| `ai_model` | `VARCHAR(50)` | NOT NULL | 사용된 AI 모델 |
| `ai_reasoning` | `TEXT` | | LLM 추론 과정 (투명성) |
| `token_usage` | `JSONB` | | 토큰 사용량 `{prompt, completion, total}` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |

---

### 2.6 `playbooks` — Playbook-as-Code 정의

| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| `id` | `UUID` | PK, `gen_random_uuid()` | |
| `name` | `VARCHAR(255)` | NOT NULL, UNIQUE | Playbook 이름 (kebab-case) |
| `version` | `VARCHAR(20)` | NOT NULL, DEFAULT '1.0' | 버전 |
| `description` | `TEXT` | | 설명 |
| `yaml_content` | `TEXT` | NOT NULL | YAML 원본 |
| `parsed_config` | `JSONB` | NOT NULL | 파싱된 구조화 데이터 |
| `trigger_type` | `VARCHAR(30)` | NOT NULL | `metric_threshold` / `anomaly` / `schema_change` / `manual` |
| `min_autonomy_level` | `SMALLINT` | NOT NULL, DEFAULT 2 | 최소 자율 등급 |
| `target_db_types` | `VARCHAR[]` | NOT NULL | `{postgresql}` / `{postgresql,mysql}` |
| `author` | `VARCHAR(50)` | NOT NULL | `human` / `ai-agent` |
| `success_rate` | `FLOAT` | DEFAULT 0.0 | 누적 성공률 |
| `execution_count` | `INTEGER` | DEFAULT 0 | 총 실행 횟수 |
| `is_active` | `BOOLEAN` | NOT NULL, DEFAULT true | 활성 여부 |
| `git_sha` | `VARCHAR(40)` | | Git 커밋 해시 |
| `tags` | `VARCHAR[]` | DEFAULT '{}' | 태그 (performance, lock 등) |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |

**Indexes**:
- `ix_playbooks_trigger` ON (`trigger_type`)
- `ix_playbooks_tags` ON (`tags`) USING GIN

---

### 2.7 `remediation_logs` — 자가 치유 감사 로그

| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| `id` | `UUID` | PK, `gen_random_uuid()` | |
| `playbook_id` | `UUID` | NOT NULL, FK → playbooks | |
| `incident_id` | `UUID` | FK → incidents | |
| `instance_id` | `UUID` | NOT NULL, FK → db_instances | |
| `autonomy_level` | `SMALLINT` | NOT NULL | 실행 시 자율 등급 |
| `status` | `VARCHAR(15)` | NOT NULL | `pending` / `running` / `success` / `failed` / `rolled_back` |
| `actions` | `JSONB` | NOT NULL | 실행된 액션 목록 `[{step, command, result, duration_ms}]` |
| `started_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |
| `completed_at` | `TIMESTAMPTZ` | | |
| `executed_by` | `VARCHAR(50)` | NOT NULL | 실행 주체 (agent ID 또는 user ID) |
| `rollback_reason` | `TEXT` | | 롤백 사유 |
| `slo_check` | `JSONB` | | SLO 검증 결과 `{metric, before, after, passed}` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |

**Indexes**:
- `ix_remediation_instance_status` ON (`instance_id`, `status`)
- `ix_remediation_started` ON (`started_at` DESC)

---

### 2.8 `topology_nodes` — 풀스택 토폴로지 노드

| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| `id` | `UUID` | PK, `gen_random_uuid()` | |
| `name` | `VARCHAR(255)` | NOT NULL | 노드 이름 |
| `node_type` | `VARCHAR(20)` | NOT NULL | `application` / `middleware` / `database` / `infrastructure` |
| `instance_id` | `UUID` | FK → db_instances | DB 노드인 경우 |
| `endpoint` | `VARCHAR(500)` | | 서비스 엔드포인트 |
| `metadata` | `JSONB` | DEFAULT '{}' | 호스트, 컨테이너, Pod 정보 |
| `health_status` | `VARCHAR(15)` | DEFAULT 'unknown' | `healthy` / `degraded` / `down` / `unknown` |
| `last_seen_at` | `TIMESTAMPTZ` | | 마지막 활동 시각 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |

### 2.9 `topology_edges` — 노드 간 의존성

| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| `id` | `UUID` | PK, `gen_random_uuid()` | |
| `source_id` | `UUID` | NOT NULL, FK → topology_nodes | 호출하는 쪽 |
| `target_id` | `UUID` | NOT NULL, FK → topology_nodes | 호출받는 쪽 |
| `edge_type` | `VARCHAR(20)` | NOT NULL | `depends_on` / `runs_on` / `replicates_to` |
| `avg_latency_ms` | `FLOAT` | | 평균 지연 시간 |
| `request_rate` | `FLOAT` | | 초당 요청 수 |
| `status` | `VARCHAR(15)` | DEFAULT 'active' | `active` / `degraded` / `inactive` |
| `metadata` | `JSONB` | DEFAULT '{}' | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |

**Constraints**:
- `UNIQUE(source_id, target_id, edge_type)` — 동일 유형 중복 간선 방지

---

### 2.10 `baselines` — AI 자동 베이스라인

| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| `id` | `UUID` | PK, `gen_random_uuid()` | |
| `instance_id` | `UUID` | NOT NULL, FK → db_instances | |
| `metric_type` | `VARCHAR(50)` | NOT NULL | cpu_usage, connections, tps 등 |
| `time_bucket` | `VARCHAR(20)` | NOT NULL | `weekday_business` / `weekday_night` / `weekend` 등 |
| `normal_min` | `FLOAT` | NOT NULL | 정상 범위 하한 |
| `normal_max` | `FLOAT` | NOT NULL | 정상 범위 상한 |
| `mean` | `FLOAT` | NOT NULL | 평균 |
| `stddev` | `FLOAT` | NOT NULL | 표준편차 |
| `model_type` | `VARCHAR(20)` | NOT NULL | `stl` / `isolation_forest` / `prophet` |
| `model_params` | `JSONB` | NOT NULL | 모델 파라미터 |
| `training_samples` | `INTEGER` | NOT NULL | 학습 샘플 수 |
| `last_trained_at` | `TIMESTAMPTZ` | NOT NULL | 마지막 학습 시각 |
| `is_active` | `BOOLEAN` | NOT NULL, DEFAULT true | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |

**Indexes**:
- `ix_baselines_lookup` ON (`instance_id`, `metric_type`, `time_bucket`) UNIQUE

---

### 2.11 `schema_changes` — DDL 변경 추적

| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| `id` | `UUID` | PK, `gen_random_uuid()` | |
| `instance_id` | `UUID` | NOT NULL, FK → db_instances | |
| `change_type` | `VARCHAR(20)` | NOT NULL | `CREATE` / `ALTER` / `DROP` / `REINDEX` / `PARAM_CHANGE` |
| `object_type` | `VARCHAR(20)` | NOT NULL | `TABLE` / `INDEX` / `COLUMN` / `FUNCTION` / `PARAMETER` |
| `object_name` | `VARCHAR(255)` | NOT NULL | 대상 객체명 |
| `ddl_command` | `TEXT` | | 실행된 DDL 문 |
| `before_state` | `JSONB` | | 변경 전 상태 |
| `after_state` | `JSONB` | | 변경 후 상태 |
| `executed_by` | `VARCHAR(255)` | | 실행자 (DB user) |
| `detected_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |
| `impact_analysis` | `JSONB` | | AI 영향도 분석 결과 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |

**Indexes**:
- `ix_schema_changes_instance_time` ON (`instance_id`, `detected_at` DESC)

---

### 2.12 `users` — 사용자

| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| `id` | `UUID` | PK, `gen_random_uuid()` | |
| `email` | `VARCHAR(255)` | NOT NULL, UNIQUE | 이메일 |
| `name` | `VARCHAR(255)` | NOT NULL | 표시명 |
| `hashed_password` | `VARCHAR(255)` | | bcrypt 해시 (SSO 시 null) |
| `role` | `VARCHAR(20)` | NOT NULL | `super_admin` / `db_admin` / `operator` / `viewer` / `api_user` |
| `auth_provider` | `VARCHAR(20)` | DEFAULT 'local' | `local` / `saml` / `oidc` / `ldap` |
| `is_active` | `BOOLEAN` | NOT NULL, DEFAULT true | |
| `last_login_at` | `TIMESTAMPTZ` | | |
| `preferences` | `JSONB` | DEFAULT '{}' | 대시보드 레이아웃, 알림 설정 등 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |

---

### 2.13 `audit_logs` — 감사 로그

| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| `id` | `UUID` | PK, `gen_random_uuid()` | |
| `user_id` | `UUID` | FK → users | 행위자 (null = system) |
| `action` | `VARCHAR(50)` | NOT NULL | `login` / `create` / `update` / `delete` / `execute` / `ai_decision` |
| `resource_type` | `VARCHAR(50)` | NOT NULL | `incident` / `playbook` / `instance` / `user` 등 |
| `resource_id` | `UUID` | | 대상 리소스 ID |
| `details` | `JSONB` | NOT NULL | WHO/WHAT/WHEN/WHERE/WHY + before/after |
| `ip_address` | `INET` | | 클라이언트 IP |
| `user_agent` | `VARCHAR(500)` | | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |

**Partitioning**: `PARTITION BY RANGE (created_at)` — 월별
**Indexes**:
- `ix_audit_user_time` ON (`user_id`, `created_at` DESC)
- `ix_audit_resource` ON (`resource_type`, `resource_id`)

---

### 2.14 `nl2sql_histories` — NL2SQL 질의 이력

| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| `id` | `UUID` | PK, `gen_random_uuid()` | |
| `user_id` | `UUID` | NOT NULL, FK → users | |
| `instance_id` | `UUID` | FK → db_instances | |
| `natural_query` | `TEXT` | NOT NULL | 사용자 자연어 입력 |
| `generated_sql` | `TEXT` | NOT NULL | 생성된 SQL |
| `execution_result` | `JSONB` | | 실행 결과 (rows, columns) |
| `is_correct` | `BOOLEAN` | | 사용자 피드백 (맞음/틀림) |
| `ai_model` | `VARCHAR(50)` | NOT NULL | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |

---

### 2.15 `rag_documents` — RAG 벡터 임베딩 (pgvector)

| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| `id` | `UUID` | PK, `gen_random_uuid()` | |
| `collection` | `VARCHAR(50)` | NOT NULL | `db_docs` / `incidents` / `playbooks` / `query_patterns` |
| `content` | `TEXT` | NOT NULL | 원본 텍스트 청크 |
| `embedding` | `VECTOR(384)` | NOT NULL | 임베딩 벡터 (MiniLM: 384, OpenAI ada-002: 1536 — 모델에 따라 테이블 재생성 또는 별도 컬럼) |
| `metadata` | `JSONB` | DEFAULT '{}' | source, tags, timestamp |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |

**Indexes**:
- `ix_rag_collection` ON (`collection`)
- `ix_rag_embedding` ON (`embedding`) USING ivfflat (lists = 100) WITH (vector_cosine_ops)

---

### 2.16 `alert_channels` — 알림 채널 설정

| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| `id` | `UUID` | PK, `gen_random_uuid()` | |
| `name` | `VARCHAR(255)` | NOT NULL | 채널 표시명 (e.g., "#db-alerts") |
| `channel_type` | `VARCHAR(20)` | NOT NULL | `slack` / `email` / `webhook` / `pagerduty` |
| `config` | `JSONB` | NOT NULL | 채널별 설정 (webhook_url, smtp_host 등 — 암호화) |
| `severity_filter` | `VARCHAR[]` | NOT NULL, DEFAULT '{critical,warning}' | 수신할 심각도 |
| `is_active` | `BOOLEAN` | NOT NULL, DEFAULT true | |
| `last_test_at` | `TIMESTAMPTZ` | | 마지막 테스트 발송 시각 |
| `last_test_result` | `BOOLEAN` | | 테스트 성공 여부 |
| `created_by` | `UUID` | FK → users | 생성자 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |

**Indexes**:
- `ix_alert_channels_type` ON (`channel_type`)
- `ix_alert_channels_active` ON (`is_active`) WHERE `is_active = true`

---

### 2.17 `alert_policies` — 에스컬레이션 정책

| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| `id` | `UUID` | PK, `gen_random_uuid()` | |
| `name` | `VARCHAR(255)` | NOT NULL, UNIQUE | 정책명 |
| `description` | `TEXT` | | 정책 설명 |
| `escalation_chain` | `JSONB` | NOT NULL | 에스컬레이션 체인 `[{level, channel_id, delay_minutes}]` |
| `severity` | `VARCHAR(10)` | NOT NULL | 적용 심각도 (`critical` / `warning` / `notice` / `info`) |
| `cooldown_minutes` | `INTEGER` | NOT NULL, DEFAULT 30 | 동일 인시던트 재알림 방지 간격 |
| `is_active` | `BOOLEAN` | NOT NULL, DEFAULT true | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |

**예시**: `escalation_chain`
```json
[
  { "level": 1, "channel_id": "uuid-slack", "delay_minutes": 0 },
  { "level": 2, "channel_id": "uuid-email", "delay_minutes": 15 },
  { "level": 3, "channel_id": "uuid-pagerduty", "delay_minutes": 30 }
]
```

---

### 2.18 `alert_history` — 알림 발송 이력

| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| `id` | `UUID` | PK, `gen_random_uuid()` | |
| `incident_id` | `UUID` | NOT NULL, FK → incidents | |
| `channel_id` | `UUID` | NOT NULL, FK → alert_channels | |
| `policy_id` | `UUID` | FK → alert_policies | |
| `escalation_level` | `SMALLINT` | NOT NULL, DEFAULT 1 | 에스컬레이션 단계 |
| `status` | `VARCHAR(15)` | NOT NULL | `sent` / `failed` / `suppressed` |
| `response_code` | `INTEGER` | | HTTP 응답 코드 (Webhook) |
| `error_message` | `TEXT` | | 실패 시 에러 메시지 |
| `sent_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |

**Indexes**:
- `ix_alert_history_incident` ON (`incident_id`, `sent_at` DESC)

---

### v3.3 신규 테이블 (FR-AI-010~014)

| 테이블 | 파티셔닝 | Phase | 비고 |
|--------|---------|-------|------|
| `mtl_predictions` | - | MVP | MTL 4-Head 예측 결과 + Confidence Score |
| `reasoning_chains` | - | MVP | Explainable AI 추론 단계 |
| `evidence_links` | - | MVP | 근거 데이터 링크 |
| `rag_documents` | - | MVP | pgvector 인시던트 임베딩 (경량 RAG) |
| `copilot_sessions` | - | Phase 2 | DB Copilot ToT 세션 이력 |
| `llm_metrics` | 일별 (pg_partman) | Phase 2 | LLM 호출 메트릭 (토큰/지연/비용) |
| `model_drift_metrics` | - | Phase 2 | 모델 드리프트 감지 |

> 각 테이블의 상세 스키마는 해당 Feature Spec 참조:
> - `mtl_predictions`, `reasoning_chains`, `evidence_links` → `docs/specs/ai/MTL_RCA_SPEC.md`
> - `rag_documents` → `docs/specs/ai/LIGHTWEIGHT_RAG_SPEC.md`
> - `copilot_sessions` → `docs/specs/ai/COPILOT_SPEC.md`
> - `llm_metrics`, `model_drift_metrics` → `docs/specs/ai/LLM_OBSERVABILITY_SPEC.md`

---

### FK Cascade 정책

| Parent → Child | ON DELETE | 이유 |
|----------------|-----------|------|
| db_instances → metric_samples | CASCADE | 인스턴스 삭제 시 메트릭 삭제 |
| db_instances → active_sessions | CASCADE | 인스턴스 삭제 시 ASH 삭제 |
| db_instances → incidents | SET NULL | 인시던트 이력 보존 |
| incidents → mtl_predictions | CASCADE | 인시던트 삭제 시 예측 삭제 |
| mtl_predictions → reasoning_chains | CASCADE | 예측 삭제 시 추론 삭제 |
| mtl_predictions → evidence_links | CASCADE | 예측 삭제 시 증거 삭제 |
| users → audit_logs | SET NULL | 사용자 삭제 시 로그 보존 |
| incidents → rag_documents | CASCADE | 인시던트 삭제 시 임베딩 삭제 |

---

## 3. Soft Delete 전략

삭제 가능한 엔티티에 `deleted_at` 컬럼을 추가합니다. `NULL`이면 활성, 값이 있으면 소프트 삭제.

| 테이블 | Soft Delete 적용 | 이유 |
|--------|-----------------|------|
| `db_instances` | ✅ | 인스턴스 삭제 시 연관 메트릭 보존 |
| `users` | ✅ | 감사 로그에서 삭제된 사용자 참조 보존 |
| `playbooks` | ✅ | 과거 실행 이력에서 삭제된 Playbook 참조 보존 |
| `alert_channels` | ✅ | 발송 이력 참조 보존 |
| `metric_samples` | ❌ | Retention 정책으로 자동 삭제 (파티션 DROP) |
| `active_sessions` | ❌ | Retention 정책으로 자동 삭제 |
| `incidents` | ❌ | 닫기(close)만 가능, 삭제 불가 |
| `audit_logs` | ❌ | 삭제 불가 (규정 준수) |

```sql
-- 적용 대상 테이블에 추가
ALTER TABLE db_instances ADD COLUMN deleted_at TIMESTAMPTZ DEFAULT NULL;
ALTER TABLE users ADD COLUMN deleted_at TIMESTAMPTZ DEFAULT NULL;
ALTER TABLE playbooks ADD COLUMN deleted_at TIMESTAMPTZ DEFAULT NULL;
ALTER TABLE alert_channels ADD COLUMN deleted_at TIMESTAMPTZ DEFAULT NULL;

-- 조회 시 기본 필터
WHERE deleted_at IS NULL
```

---

## 4. Partitioning Strategy

| Table | Partition Key | Interval | Retention | pg_partman |
|-------|-------------|----------|-----------|-----------|
| `metric_samples` | `sampled_at` | 1 day | hot:7d, warm:90d, cold:365d | Yes |
| `active_sessions` | `sampled_at` | 1 day | 7d raw + Materialized View | Yes |
| `audit_logs` | `created_at` | 1 month | 365d hot + glacier archive | Yes |

## 4. Materialized Views (다운샘플링)

```sql
-- 10초 집계
CREATE MATERIALIZED VIEW mv_metrics_10s AS
SELECT
    instance_id,
    date_trunc('second', sampled_at)
        - (EXTRACT(SECOND FROM sampled_at)::int % 10) * INTERVAL '1 second' AS bucket,
    category,
    count(*) AS sample_count,
    -- 수치 메트릭만 집계 (JSONB에서 숫자 값만 추출)
    jsonb_build_object(
        'cpu_usage',         avg((metrics->>'cpu_usage')::numeric),
        'memory_usage',      avg((metrics->>'memory_usage')::numeric),
        'active_connections', avg((metrics->>'active_connections')::numeric),
        'tps',               avg((metrics->>'tps')::numeric),
        'buffer_hit_ratio',  avg((metrics->>'buffer_hit_ratio')::numeric)
    ) AS avg_metrics
FROM metric_samples
WHERE category = 'hot'
GROUP BY 1, 2, 3;

CREATE UNIQUE INDEX ix_mv_metrics_10s ON mv_metrics_10s (instance_id, bucket);

-- 1분 집계
CREATE MATERIALIZED VIEW mv_metrics_1m AS
SELECT instance_id, date_trunc('minute', bucket) AS bucket, category,
       sum(sample_count) AS sample_count,
       jsonb_build_object(
           'cpu_usage',         avg((avg_metrics->>'cpu_usage')::numeric),
           'memory_usage',      avg((avg_metrics->>'memory_usage')::numeric),
           'active_connections', avg((avg_metrics->>'active_connections')::numeric),
           'tps',               avg((avg_metrics->>'tps')::numeric),
           'buffer_hit_ratio',  avg((avg_metrics->>'buffer_hit_ratio')::numeric)
       ) AS avg_metrics
FROM mv_metrics_10s
GROUP BY 1, 2, 3;

CREATE UNIQUE INDEX ix_mv_metrics_1m ON mv_metrics_1m (instance_id, bucket);

-- 1시간 / 1일 동일 패턴 (상위 MV에서 집계)

-- pg_cron으로 갱신 (5분마다)
SELECT cron.schedule('refresh-mv-10s', '*/5 * * * *',
    'REFRESH MATERIALIZED VIEW CONCURRENTLY mv_metrics_10s');
SELECT cron.schedule('refresh-mv-1m', '*/5 * * * *',
    'REFRESH MATERIALIZED VIEW CONCURRENTLY mv_metrics_1m');
```

## 5. PostgreSQL Extensions Required

```sql
CREATE EXTENSION IF NOT EXISTS vector;        -- pgvector
CREATE EXTENSION IF NOT EXISTS pg_partman;     -- 자동 파티셔닝
CREATE EXTENSION IF NOT EXISTS pg_cron;        -- 스케줄 작업
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;  -- 쿼리 통계
```
