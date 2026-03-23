# NeuralDB MVP (Phase 1) Specification

> **Version**: 1.0
> **Date**: 2026-03-21
> **목표**: 동일 네트워크 내 PostgreSQL **10대** 모니터링
> **기간**: 3개월
> **수집 방식**: Remote Adapter only (RTT <2ms, 1초 수집 가능)
> **PRD 참조**: Phase 1 (P0 항목 중 MVP 필수)

---

## 1. MVP Scope 정의

### 1.1 핵심 전제

| 항목 | MVP 범위 |
|------|---------|
| 대상 DB | PostgreSQL 16 only |
| 인스턴스 수 | 최대 10대 |
| 네트워크 | 동일 DC / VPC (RTT <2ms) |
| 수집 방식 | Remote Adapter (Collector 없음) |
| 수집 해상도 | Hot 1초, Warm 10초, Cold 1분 |
| AI 모드 | Online(Cloud LLM) 우선, Offline 선택적 |
| 사용자 수 | ~20명 |
| 배포 | Docker Compose 단일 노드 |

### 1.2 MVP에 포함 / 제외

| 포함 (Build) | 제외 (Phase 2+) |
|-------------|-----------------|
| 실시간 대시보드 (메트릭 + ASH) | 풀스택 토폴로지 맵 |
| AI 자동 베이스라인 (이상 탐지) | 풀 RAG Pipeline (Phase 2) |
| **경량 RAG** (pgvector 인시던트 이력 유사 검색) | 풀 RAG (문서/매뉴얼 임베딩) |
| **경량 RCA** (1줄 요약 + 추천 액션 + Confidence Score) | AI RCA 패널 (상세 분석) |
| **MTL Lite** (LLM Few-shot 4-Head 동시 추론) | MTL Transformer 파인튜닝 |
| NL2SQL 기본 질의 | AIGC 리포트 생성, EXPLAIN 해석 |
| Slack 알림 (4단계) | Email/PagerDuty 에스컬레이션 |
| RBAC 사용자 관리 (로컬 인증) | SSO/LDAP 연동 |
| 감사 로그 | AI Decision Log (상세 추론) |
| PostgreSQL Adapter + ASH | MySQL/MSSQL Adapter |
| 수동 임계값 + AI 베이스라인 | Playbook-as-Code |
| 기본 스키마 변경 감지 | Schema Change 영향도 분석 |
| System Health 기본 (`/health`) | Prometheus exporter 연동 |
| 단일 FastAPI 서버 | Multi-Agent (A2A), MCP Server |
| Docker Compose 배포 | Kubernetes, Helm Chart |

---

## 2. 기능 상세

### 2.1 대시보드 [MVP-DASH]

| ID | 기능 | PRD 참조 | 설명 |
|----|------|---------|------|
| MVP-DASH-001 | 인스턴스 목록 | FR-DASH-001 | 등록된 PostgreSQL 인스턴스 카드 뷰 (상태, 핵심 메트릭) |
| MVP-DASH-002 | 실시간 메트릭 차트 | FR-DASH-001 | CPU, Memory, Connections, TPS 시계열 차트 (ECharts). 1초 WebSocket 스트리밍 |
| MVP-DASH-003 | ASH Timeline | FR-DASH-003 | 1초 ASH 히트맵 (Wait Event 카테고리별). 시간 드릴다운 (시→분→초) |
| MVP-DASH-004 | 인시던트 목록 | FR-DASH-001 | 활성 인시던트 리스트 (severity 필터, 시간순) |
| MVP-DASH-005 | System Health | FR-SELF-001 | NeuralDB 자체 상태 (DB/Valkey/Kafka/Celery UP/DOWN) |

**디자인 참조**: `docs/FRONTEND_DESIGN.md`
- Screen 1 (Topology) → MVP에서는 토폴로지 맵 대신 인스턴스 카드 그리드
- Screen 3 (ASH) → ASH 히트맵 + 세션 테이블 그대로 구현
- Screen 4 (Diagnosis) → 인시던트 목록만 (AI RCA 패널은 Phase 2)

### 2.2 메트릭 수집 [MVP-COLLECT]

| ID | 기능 | PRD 참조 | 설명 |
|----|------|---------|------|
| MVP-COLLECT-001 | Hot 메트릭 수집 | FR-DB-001 | 1초: CPU, Memory, Active Connections, TPS, Buffer Hit Ratio |
| MVP-COLLECT-002 | Warm 메트릭 수집 | FR-DB-001 | 10초: Disk I/O, Table Sizes, WAL Generation |
| MVP-COLLECT-003 | Cold 메트릭 수집 | FR-DB-001 | 1분: Replication Lag, Vacuum Status, Bloat |
| MVP-COLLECT-004 | ASH 샘플링 | FR-DB-001 | 1초: pg_stat_activity → active_sessions 테이블 |
| MVP-COLLECT-005 | 쿼리 통계 | FR-DB-001 | 10초: pg_stat_statements Top 100 |

**수집 소스 (PostgreSQL)**:
```sql
-- Hot (1초)
pg_stat_activity          -- ASH, Active Sessions
pg_stat_database          -- TPS, Transactions
pg_stat_bgwriter          -- Buffer, Checkpoint

-- Warm (10초)
pg_stat_statements        -- Query Stats
pg_stat_user_tables       -- Table Stats, Seq Scan
pg_statio_user_tables     -- I/O Stats

-- Cold (1분)
pg_stat_replication       -- Replication Lag
pg_stat_progress_vacuum   -- Vacuum Progress
pg_settings               -- Parameter Changes
```

**구현 방식**:
- Remote Adapter: `asyncpg` 커넥션 풀 (인스턴스당 2개 커넥션)
- Celery Beat: 주기적 수집 태스크
- 총 커넥션: 10대 × 2 = 20개 (대상 DB 부하 미미)
- `statement_timeout = '500ms'` 안전 장치

### 2.3 AI 이상 탐지 [MVP-AI]

| ID | 기능 | PRD 참조 | 설명 |
|----|------|---------|------|
| MVP-AI-001 | 자동 베이스라인 학습 | FR-AI-001 | 최소 2주 데이터로 정상 패턴 학습. STL 분해 + Isolation Forest |
| MVP-AI-002 | 동적 이상 탐지 | FR-ALERT-003 | 베이스라인 대비 이상 감지 → 인시던트 자동 생성 |
| MVP-AI-003 | 수동 임계값 병행 | FR-ALERT-003 | AI 베이스라인 = 1차 방어선, 수동 임계값 = 2차 안전망 |
| MVP-AI-004 | NL2SQL 기본 | FR-AI-003 | "현재 가장 느린 쿼리?" → SQL 변환 → 결과 표시. 읽기 전용 |
| MVP-AI-005 | Online/Offline 전환 | FR-AI-008 | 환경변수로 Cloud LLM ↔ Ollama 전환 |

**학습 파이프라인**:
```
2주 메트릭 축적 → STL 분해 (Trend/Seasonal/Residual)
  → Isolation Forest 학습 (contamination=0.05)
  → 시간대별 베이스라인 생성 (weekday_business/night/weekend)
  → Valkey에 캐싱 (실시간 비교용)
  → 6시간마다 재학습 (Celery Beat)
```

### 2.4 알림 [MVP-ALERT]

| ID | 기능 | PRD 참조 | 설명 |
|----|------|---------|------|
| MVP-ALERT-001 | Slack 알림 | FR-ALERT-001 | CRITICAL/WARNING/NOTICE/INFO 4단계. 메트릭 값 + AI 판단 포함 |
| MVP-ALERT-002 | Webhook 알림 | FR-ALERT-002 | 범용 Webhook 엔드포인트 (추후 Email/PagerDuty 확장 기반) |

**Slack 메시지 형태**:
```
🔴 CRITICAL | pg-prod-01
CPU 사용률 95% (베이스라인: 40~60%)
AI 판단: 워크로드 급증 또는 비효율 쿼리
[상세보기] [NL2SQL]
```

### 2.5 사용자 관리 [MVP-ADMIN]

| ID | 기능 | PRD 참조 | 설명 |
|----|------|---------|------|
| MVP-ADMIN-001 | 로컬 인증 | FR-ADMIN-001 | Email + Password (bcrypt). JWT Access/Refresh Token |
| MVP-ADMIN-002 | RBAC 5역할 | FR-ADMIN-001 | Super Admin, DB Admin, Operator, Viewer, API User |
| MVP-ADMIN-003 | 감사 로그 | FR-ADMIN-003 | 모든 상태 변경 WHO/WHAT/WHEN 기록 |

### 2.6 스키마 변경 감지 [MVP-SCHEMA]

| ID | 기능 | PRD 참조 | 설명 |
|----|------|---------|------|
| MVP-SCHEMA-001 | DDL 이벤트 감지 | - | PostgreSQL Event Trigger로 CREATE/ALTER/DROP 캡처 |
| MVP-SCHEMA-002 | 변경 이력 조회 | - | 대시보드에서 스키마 변경 타임라인 표시 |

> 영향도 분석 (Before/After 성능 비교)은 Phase 2로 연기.

### 2.7 경량 RAG + RCA [MVP-RAG]

| ID | 기능 | PRD 참조 | 설명 |
|----|------|---------|------|
| MVP-RAG-001 | 인시던트 이력 임베딩 | FR-AI-002 | 인시던트 생성 시 description + metrics snapshot을 sentence-transformers로 임베딩 → pgvector 저장 |
| MVP-RAG-002 | 유사 인시던트 검색 | FR-AI-002 | 새 인시던트 발생 시 pgvector cosine similarity로 Top-3 유사 과거 사례 자동 검색 |
| MVP-RAG-003 | 경량 RCA 요약 | FR-AI-014 | LLM에 현재 메트릭 + 유사 과거 사례를 제공하여 1줄 Root Cause Summary + 추천 액션 1~3개 생성 |
| MVP-RAG-004 | Confidence Score | FR-AI-011 | 모든 AI 출력에 Confidence Score (0.0~1.0) 포함. 대시보드에 신뢰도 배지 표시 |
| MVP-RAG-005 | MTL Lite | FR-AI-010 | 단일 LLM 프롬프트에서 이상분류/원인식별/심각도/액션추천 4개 태스크를 Few-shot으로 동시 요청 |

**MTL Lite 프롬프트 구조**:
```text
Given the following DB incident context:
- Metrics: {metrics_snapshot}
- Similar past incidents: {rag_results}
- Current ASH: {ash_summary}

Respond in JSON with ALL of the following:
1. anomaly_type: classify the anomaly type
2. root_cause: identify the specific root cause
3. severity: score from 0.0 to 1.0
4. suggested_actions: list of concrete actions
5. confidence: your confidence score (0.0-1.0)
6. reasoning_chain: step-by-step reasoning
```

---

## 3. 기술 스택 (MVP 한정)

### 3.1 사용하는 것

| 영역 | 기술 | 비고 |
|------|------|------|
| **Frontend** | React 18, Vite, TypeScript, TailwindCSS, Zustand, TanStack Query/Router, ECharts, Socket.io-client | |
| **Backend** | Python 3.12, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2.0, asyncpg, Alembic | 단일 서버 |
| **Task Queue** | Celery + Valkey (broker) | Worker 4개 |
| **WebSocket** | python-socketio | 실시간 메트릭 |
| **AI/ML** | LangChain (NL2SQL), scikit-learn (Isolation Forest), statsmodels (STL) | |
| **LLM** | OpenAI GPT-4o (online), Ollama Mistral:7b (offline) | 환경변수 전환 |
| **DB** | PostgreSQL 16, pgvector, pg_partman, pg_cron, pg_stat_statements | 단일 인스턴스 |
| **Cache** | Valkey 8 | 베이스라인 캐싱 |
| **Messaging** | Apache Kafka | 메트릭 이벤트 버퍼 |
| **배포** | Docker Compose | 단일 노드 |
| **모니터링** | prometheus-fastapi-instrumentator | `/metrics` 엔드포인트 |
| **RAG** | sentence-transformers, pgvector | 경량 인시던트 유사 검색 |

### 3.2 사용하지 않는 것 (Phase 2+)

| 기술 | 이유 |
|------|------|
| Strawberry (GraphQL) | MVP는 REST API만으로 충분 |
| CrewAI / LangGraph | Multi-Agent는 Phase 3 |
| MCP SDK / A2A SDK | External AI 연동은 Phase 3 |
| Kubernetes / Helm | 단일 노드 Docker Compose |
| Playwright | E2E 테스트는 Phase 2 |
| Prometheus Server | `/metrics` 노출만 하고 수집은 선택적 |
| 풀 RAG Pipeline (문서/매뉴얼 임베딩) | Phase 2 (MVP는 인시던트 이력 경량 RAG만) |
| PyTorch / transformers | MTL Transformer 파인튜닝은 Phase 2 (MVP는 LLM Few-shot) |
| OpenLIT | LLM Observability는 Phase 2 (MVP는 tokens_used/inference_time_ms 기본 기록만) |

---

## 4. API Endpoints (MVP)

> 전체 API Spec의 부분 집합. `docs/specs/api/API_SPEC.md` 중 MVP에 구현하는 것만.

### 4.1 Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/login` | JWT 발급 |
| POST | `/api/v1/auth/refresh` | 토큰 갱신 |
| GET | `/api/v1/auth/me` | 현재 사용자 |

### 4.2 Instances
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/instances` | 인스턴스 목록 |
| POST | `/api/v1/instances` | 인스턴스 등록 |
| GET | `/api/v1/instances/{id}` | 인스턴스 상세 |
| PUT | `/api/v1/instances/{id}` | 인스턴스 수정 |
| DELETE | `/api/v1/instances/{id}` | 인스턴스 삭제 |
| POST | `/api/v1/instances/{id}/test-connection` | 연결 테스트 |

### 4.3 Metrics
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/instances/{id}/metrics` | 메트릭 조회 (time range) |
| GET | `/api/v1/instances/{id}/metrics/latest` | 최신 스냅샷 |

### 4.4 ASH
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/instances/{id}/ash` | ASH 세션 조회 |
| GET | `/api/v1/instances/{id}/ash/heatmap` | 히트맵 데이터 |
| GET | `/api/v1/instances/{id}/ash/wait-breakdown` | Wait 유형 집계 |

### 4.5 Incidents
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/incidents` | 인시던트 목록 |
| GET | `/api/v1/incidents/{id}` | 인시던트 상세 |
| PUT | `/api/v1/incidents/{id}/status` | 상태 변경 |

### 4.6 NL2SQL
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/nl2sql/query` | 자연어 → SQL → 결과 |

### 4.7 Schema Changes
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/instances/{id}/schema-changes` | DDL 변경 이력 |

### 4.8 Baselines
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/instances/{id}/baselines` | 베이스라인 목록 |
| POST | `/api/v1/instances/{id}/baselines/retrain` | 재학습 트리거 |

### 4.9 System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/system/health` | 시스템 헬스 체크 |
| GET | `/metrics` | Prometheus 메트릭 |

### 4.10 Users
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/users` | 사용자 목록 |
| POST | `/api/v1/users` | 사용자 생성 |
| PUT | `/api/v1/users/{id}` | 사용자 수정 |
| DELETE | `/api/v1/users/{id}` | 사용자 삭제 |
| GET | `/api/v1/audit-logs` | 감사 로그 |

### 4.11 Alerts
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/alerts/channels` | 알림 채널 목록 |
| POST | `/api/v1/alerts/channels` | 채널 추가 (Slack, Webhook) |
| POST | `/api/v1/alerts/test` | 테스트 알림 |

### 4.12 WebSocket
| Namespace | Events | Description |
|-----------|--------|-------------|
| `/ws/metrics` | `metric:update` | 1초 실시간 메트릭 |
| `/ws/incidents` | `incident:new`, `incident:update` | 인시던트 실시간 |

---

## 5. Data Model (MVP)

ERD 전체는 `docs/specs/data-model/ERD.md` 참조. MVP에서 생성하는 테이블:

| 테이블 | 파티셔닝 | 비고 |
|--------|---------|------|
| `db_instances` | - | |
| `metric_samples` | 일별 (pg_partman) | Hot/Warm/Cold 통합 |
| `active_sessions` | 일별 (pg_partman) | ASH 1초 샘플링 |
| `incidents` | - | |
| `baselines` | - | |
| `schema_changes` | - | |
| `users` | - | |
| `audit_logs` | 월별 (pg_partman) | |
| `nl2sql_histories` | - | |
| `rag_documents` | - | 인시던트 이력 임베딩 저장 (MVP에서 경량 RAG 활성화) |
| `mtl_predictions` | - | MTL 4-Head 예측 결과 + Confidence Score (FR-AI-010) |
| `reasoning_chains` | - | Explainable AI 추론 단계 (FR-AI-011) |
| `evidence_links` | - | 근거 데이터 링크 (FR-AI-011) |

**생성하지 않는 테이블** (Phase 2+):
- `rca_results` — 풀 AI RCA 패널은 Phase 2 (MVP는 mtl_predictions로 경량 RCA)
- `playbooks`, `remediation_logs` — Playbook은 Phase 2
- `topology_nodes`, `topology_edges` — 토폴로지는 Phase 3

---

## 6. Frontend Screens (MVP)

| Screen | 디자인 참조 | MVP 구현 범위 |
|--------|-----------|-------------|
| **Dashboard (메인)** | screen1_topology | 토폴로지 맵 대신 **인스턴스 카드 그리드** + Summary 카드 4개 (총 인스턴스, 활성 세션, 이상, 응답시간) + 메트릭 차트 |
| **ASH Explorer** | screen3_ash | Temporal Zoom + ASH 히트맵 + 세션 테이블 + Wait Breakdown (**전부 구현**) |
| **Incidents** | screen4_diagnosis | 인시던트 목록만 (AI RCA 패널 제외) |
| **NL2SQL** | screen4_diagnosis 하단 채팅 | 플로팅 챗 위젯 (자연어 입력 → SQL → 결과 테이블) |
| **Settings** | - | 인스턴스 등록/수정, 알림 채널 설정, 사용자 관리 |

**구현하지 않는 Screen**:
- Playbook 편집기 (Phase 2)
- Self-Healing 대시보드 (Phase 2)
- 풀스택 토폴로지 맵 (Phase 3)
- AI RCA 패널 (Phase 2)

---

## 7. Infrastructure (MVP)

### 7.1 Docker Compose 구성

```yaml
services:
  postgres:        # 시스템 DB (PostgreSQL 16 + pgvector)
  valkey:          # 캐시 + Celery 브로커
  kafka:           # 메트릭 이벤트 버퍼
  backend:         # FastAPI (port 8000)
  celery-worker:   # Worker ×4
  celery-beat:     # 스케줄러
  frontend:        # React SPA (nginx, port 3000)
  ollama:          # 로컬 LLM (오프라인 모드, 선택적)

volumes:
  pg_data:         # PostgreSQL 데이터
  model_cache:     # sentence-transformers + Ollama 모델 캐시
```

### 7.2 리소스 추정 (단일 노드)

| 컴포넌트 | CPU | Memory | Disk |
|----------|-----|--------|------|
| PostgreSQL 16 | 2 core | 4 GB | 50 GB (7일 1초 × 10대) |
| Valkey | 0.5 core | 1 GB | - |
| Kafka | 1 core | 2 GB | 10 GB |
| Backend + Workers | 2 core | 4 GB | - |
| Frontend (nginx) | 0.1 core | 128 MB | - |
| **합계** | **~6 core** | **~12 GB** | **~60 GB** |

### 7.3 스토리지 추정 (10대 × 7일)

```
Hot 메트릭 (1초):  10대 × 86,400 rows/day × 7일 × ~200 bytes = ~12 GB
ASH (1초):         10대 × 86,400 rows/day × 7일 × ~300 bytes = ~18 GB
Warm/Cold:         미미 (~500 MB)
감사 로그:          ~200 MB
──────────────────────────────────
합계:              ~30 GB (인덱스 포함 ~50 GB)
```

---

## 8. 개발 마일스톤

### Month 1: Foundation

| Week | Deliverable |
|------|-------------|
| W1 | 프로젝트 초기화 (`/init-project`). Docker Compose. DB 스키마 + Alembic 마이그레이션 |
| W2 | Auth API (JWT + RBAC). User CRUD. 감사 로그 기본 |
| W3 | Instance CRUD. PostgreSQL Remote Adapter (커넥션 + 기본 메트릭 수집) |
| W4 | Hot 메트릭 1초 수집 (Celery Beat). metric_samples 파티셔닝. 기본 API |

### Month 2: Core Features

| Week | Deliverable |
|------|-------------|
| W5 | ASH 1초 샘플링. Wait Event 분류. ASH API |
| W6 | AI 베이스라인 학습 (STL + Isolation Forest). 이상 탐지 → 인시던트 자동 생성 |
| W7 | Frontend: Dashboard (인스턴스 카드 + 메트릭 차트 + WebSocket). ASH 히트맵 |
| W8 | Slack/Webhook 알림. NL2SQL 기본. 스키마 변경 감지. **경량 RAG(pgvector 임베딩) + MTL Lite RCA + Confidence Score** |

### Month 3: Polish & Ship

| Week | Deliverable |
|------|-------------|
| W9 | Frontend: Incidents, NL2SQL 챗, Settings. 디자인 토큰 적용 |
| W10 | System Health. 통합 테스트. 성능 테스트 (10대 동시 수집) |
| W11 | 버그 수정. 문서화. Docker Compose 프로덕션 설정 |
| W12 | 인수 테스트. 배포 가이드. MVP 릴리스 |

---

## 9. 인수 기준 (MVP Acceptance Criteria)

- [ ] **AC-1**: PostgreSQL 10대 인스턴스 동시 등록 및 1초 Hot 메트릭 수집 정상 동작 (누락률 <1%)
- [ ] **AC-2**: ASH 1초 샘플링으로 Wait Event 히트맵이 대시보드에 실시간 표시
- [ ] **AC-3**: AI 베이스라인이 2주 학습 후 이상 탐지 동작 (오탐률 <10%)
- [ ] **AC-4**: 이상 탐지 시 Slack 알림이 30초 이내 발송 (CRITICAL/WARNING/NOTICE/INFO)
- [ ] **AC-5**: NL2SQL로 "현재 가장 느린 쿼리 5개" 질의 시 올바른 SQL 생성 (성공률 >80%)
- [ ] **AC-6**: RBAC 5개 역할 기반 인증/인가 동작 (Viewer는 쓰기 불가 등)
- [ ] **AC-7**: 대시보드 초기 로딩 <3초, WebSocket 메트릭 갱신 <1초
- [ ] **AC-8**: DDL 변경(CREATE/ALTER/DROP) 감지 및 이력 표시
- [ ] **AC-9**: 모든 상태 변경에 대한 감사 로그 기록 확인
- [ ] **AC-10**: Docker Compose 한 줄(`docker compose up`)로 전체 시스템 기동
- [ ] **AC-11**: 인시던트 발생 시 경량 RCA (1줄 요약 + 추천 액션 + Confidence Score)가 30초 이내 자동 생성
- [ ] **AC-12**: MTL Lite로 이상분류/원인/심각도/액션 4가지가 동시에 JSON 응답으로 반환
- [ ] **AC-13**: pgvector 유사 인시던트 검색 결과가 RCA 프롬프트에 포함되어 컨텍스트 제공

---

## 10. MVP → Phase 2 전환 기준

MVP가 완료되면 다음 조건 충족 시 Phase 2 진입:

| 조건 | 기준 |
|------|------|
| MVP 인수 기준 | 13개 항목(AC-1~AC-13) 전부 통과 |
| 운영 안정성 | 2주간 무장애 운영 |
| 데이터 축적 | AI 베이스라인 학습 완료 (2주+) |
| 피드백 수집 | 사용자 피드백 기반 Phase 2 우선순위 조정 |

### Phase 2에서 추가되는 것

| 기능 | 근거 |
|------|------|
| RAG Pipeline (pgvector) | 축적된 인시던트 데이터로 유사 사례 검색 가능 |
| AI RCA Panel | RAG + LLM으로 근본 원인 분석 |
| Playbook-as-Code | 반복 장애 패턴에 대한 자동화 |
| Auto Query Tuning | 수집된 pg_stat_statements 기반 최적화 |
| EXPLAIN 자연어 해석 | NL2SQL 확장 |
| Adaptive Autonomy 5단계 | Playbook 실행 제어 |
| SSO/LDAP | 엔터프라이즈 인증 |
| Schema Change 영향도 | Before/After 성능 비교 |
