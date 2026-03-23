# AI-Powered Intelligent DB Monitoring System
## 아키텍처 설계 사양서 v3.1 — 산업 표준 AI DB 모니터링 + 차별화 전략 통합

---

## 변경 이력

| 버전 | 핵심 변경 사항 |
|------|---------------|
| v1.0 | 기본 아키텍처 (5-Layer, Plugin, On/Offline AI, Slack 알림, RBAC, 로깅) |
| v2.0 | +MCP Server, +A2A Multi-Agent, +Self-Healing, +Playbook-as-Code, +Adaptive Autonomy, +NL2SQL, +RAG |
| v3.0 | +Auto-Baselining, +Full-Stack Observability, +1s Granularity, +ASH/Wait Events, +Schema Change Tracking, +Auto Query Tuning, +AIGC Interface |
| v3.1 | +MTL 기반 통합 RCA, +DB Copilot(ToT), +Explainable AI(Confidence Score), +LLM Observability, +경량 RAG/RCA MVP 반영 |

---

## v3.0 신규 기능 상세

### 1. AI 자동 베이스라인 학습 (Auto-Baselining)

**참조**: IBM Instana, Dynatrace Davis AI, LogicMonitor Edwin AI

**개요**: 수동으로 임계값을 설정하는 대신, AI가 DB의 정상 행동 패턴을 자동으로 학습하여 동적 베이스라인을 생성합니다. 시간대별(업무/야간), 요일별(평일/주말), 시즌별 패턴을 구분하여 오탐(false positive)을 최소화합니다.

**아키텍처 연결 (Monitoring Agent → AI Engine)**

- Monitoring Agent가 최소 2주간 메트릭을 수집하여 정상 패턴 자동 학습
- 시계열 분해(STL Decomposition) + Isolation Forest 기반 동적 임계값 생성
- 수동 임계값은 '안전 상한선(Hard Ceiling)'으로 유지하고, AI 베이스라인은 '미세 이상 탐지(Soft Anomaly)'로 병행
- 새로운 배포, 마이그레이션, 트래픽 패턴 변경 시 Change-Point Detection 알고리즘으로 자동 재학습
- 학습된 베이스라인 모델을 Valkey에 캐싱하여 실시간 비교 성능 보장

**기존 수동 임계값과의 관계**: 수동 임계값은 제거되지 않습니다. AI 베이스라인이 미세한 이상을 탐지하는 1차 방어선이 되고, 수동 임계값은 확실한 위험 상황에 대한 2차 안전망으로 작동합니다.

---

### 2. 풀스택 옵저버빌리티 (Full-Stack Observability)

**참조**: Dynatrace Smartscape, Datadog Service Map, IBM Instana Topology

**개요**: DB만 단독 모니터링하는 것이 아니라, 애플리케이션 → 미들웨어 → DB → 인프라 간 의존성을 자동으로 발견하여 토폴로지 맵을 생성합니다. 장애 발생 시 영향 범위를 즉시 파악하고, 근본원인이 DB인지 인프라인지 애플리케이션인지 크로스 스택으로 분석합니다.

**아키텍처 연결 (Monitoring Agent + API Gateway + Infrastructure)**

- API Gateway에 OpenTelemetry Collector를 추가하여 애플리케이션 분산 트레이스 수신
- 트레이스에서 DB 호출(span)을 추출하여 서비스 → DB 의존성 자동 매핑
- Adapter가 pg_stat_activity의 client_addr, application_name을 수집하여 역방향 의존성 확인
- Core Engine에 Topology Engine(신규) 추가: 의존성 그래프를 PostgreSQL 메타 DB에 저장하고 실시간 갱신
- Diagnosis Agent가 RCA 수행 시 토폴로지 그래프를 참조하여 업스트림/다운스트림 영향도 분석

**토폴로지 데이터 모델**:
```
Service(name, type, endpoint)
  ──depends_on──▶ Database(instance, schema, table)
  ──runs_on──▶ Infrastructure(host, container, pod)
```

---

### 3. ASH & Wait Event 분석 (Active Session History)

**참조**: Oracle Active Session History(ASH), Datadog Wait Events

**개요**: Oracle의 ASH 개념을 PostgreSQL에 구현합니다. 1초 간격으로 활성 세션을 샘플링하여, 특정 시점에 어떤 쿼리가 어떤 Wait Event(Lock, I/O, CPU 등)에 걸려 있었는지 심층 분석할 수 있습니다.

**아키텍처 연결 (Adapter + Query Analyzer + PostgreSQL 16)**

- PostgreSQL Adapter가 pg_stat_activity를 1초 간격으로 샘플링하여 ASH 테이블 구축
- 수집 필드: pid, query, state, wait_event_type, wait_event, query_start, backend_type, client_addr
- Wait Event를 카테고리별 분류: CPU, LWLock, Lock, BufferPin, I/O, IPC, Network, Timeout, Extension, Client, Activity
- PostgreSQL 16 네이티브 파티셔닝(pg_partman)으로 1초 단위 스냅샷 저장, Materialized View로 10초/1분/1시간 자동 다운샘플링
- 대시보드에서 시간축 드릴다운: 시간 → 분 → 초 단위로 세션 상태 타임라인 추적
- Query Analyzer가 Wait Event 집중 시간대를 탐지하여 병목 원인 자동 분류

---

### 4. 스키마 변경 추적 & 영향도 분석 (Schema Change Tracking)

**참조**: DBmarlin

**개요**: DDL 변경(테이블 생성/삭제, 컬럼 추가, 인덱스 변경, 파라미터 변경)을 자동 감지하고, 변경 전후 성능 메트릭을 비교하여 영향도를 분석합니다.

**아키텍처 연결 (Adapter + Audit Logger + Diagnosis Agent)**

- PostgreSQL: Event Trigger로 모든 DDL 이벤트를 실시간 캡처 (CREATE, ALTER, DROP, REINDEX 등)
- 파라미터 변경: pg_settings를 주기적 스냅샷하여 변경 감지
- 변경 이벤트를 대시보드 타임라인에 Annotation으로 자동 표시 (성능 그래프 위 핀)
- Schema Change Tracker(Adapter Layer 신규 모듈)가 변경 전후 30분 성능 메트릭 자동 비교 (Before/After Analysis)
- Diagnosis Agent가 DDL 변경과 성능 저하 사이의 인과관계를 Causal Inference로 추론
- 성능이 악화된 경우 AI가 변경 롤백을 Playbook으로 자동 추천

---

### 5. AI 자동 쿼리 튜닝 (Auto Query Tuning)

**참조**: Oracle Auto Index, SQL Server Intelligent Query Processing, Chat2DB SQL Optimization

**개요**: 단순 추천을 넘어, AI가 쿼리 실행 계획을 분석하여 인덱스 생성, 쿼리 구조 최적화, DB 파라미터 튜닝을 자동 적용합니다.

**아키텍처 연결 (Query Analyzer + AI Engine + Remediation Agent)**

- Query Analyzer가 EXPLAIN ANALYZE 결과를 LLM으로 분석하여 병목 지점 식별
- 인덱스 자동 추천/생성: Missing Index 감지 → CREATE INDEX SQL 생성 → Playbook을 통해 실행
- 쿼리 리라이트 제안: LLM이 비효율적 패턴(Nested Loop → Hash Join 유도, Seq Scan 제거 등)을 식별하고 최적화된 SQL 버전 제안
- 파라미터 튜닝: work_mem, shared_buffers, effective_cache_size 등을 워크로드 패턴 기반으로 최적값 추천
- 실행 모드는 Adaptive Autonomy Level에 따라 결정: Level 1(추천만) / Level 2(승인 후 적용) / Level 3(자동 적용 후 보고)
- Auto-Tuning 결과를 Before/After 비교로 자동 검증하고, 성능이 개선되지 않으면 자동 롤백

---

### 6. AIGC 인터페이스 (Chat2DB-Style)

**참조**: Chat2DB, BlazeSQL

**개요**: Chat2DB에서 영감을 받아, 모니터링 데이터 조회뿐 아니라 SQL 생성, 쿼리 최적화 제안, 실행 계획 자연어 해석, BI 리포트 자동 생성까지 AIGC(AI Generated Content) 전 기능을 대시보드에 통합합니다.

**아키텍처 연결 (Presentation Layer + AI Engine)**

- NL2SQL 확장: 모니터링 메트릭 질의 + 실제 대상 DB 비즈니스 데이터 질의 모두 지원
- SQL 최적화 어시스턴트: 사용자가 SQL 입력 → AI가 최적화 버전 + 두 실행 계획 비교 제공
- 실행 계획 자연어 해석: EXPLAIN 결과를 비기술자도 이해할 수 있는 자연어로 번역 ("이 쿼리는 orders 테이블에서 200만 행을 전체 스캔하고 있어 느립니다. created_at 컬럼에 인덱스를 추가하면 0.3초로 단축될 수 있습니다.")
- AI 리포트 생성: "이번 주 DB 건강 리포트 만들어줘" → 자동 차트 + 이상 분석 + 추천 사항이 포함된 PDF/HTML 리포트 생성
- 커스텀 AI 데이터셋: 사용자가 비즈니스 용어(예: "주문 = orders 테이블")를 등록하면 NL2SQL 정확도 향상
- MCP Server를 통해 외부 AI 도구에서도 동일한 AIGC 기능 호출 가능

---

### 7. 1초 단위 고해상도 모니터링 (1-Second Granularity)

**참조**: IBM Instana (1-second granularity observability)

**개요**: 핵심 메트릭을 1초 간격으로 수집하여 순간적인 스파이크나 마이크로 버스트를 놓치지 않습니다. 계층형 보관 정책으로 저장 비용을 최적화합니다.

**아키텍처 연결 (Adapter + PostgreSQL 16)**

- Hot 메트릭 (CPU, 커넥션, 활성 쿼리, TPS): 1초 간격 수집 → 7일 원본 보관
- Warm 메트릭 (디스크, 테이블 크기, WAL): 10초 간격 → 90일 보관
- Cold 메트릭 (백업 상태, 인증서, 복제): 1분 간격 → 1년 보관
- PostgreSQL 16 네이티브 파티셔닝(pg_partman) + Materialized View로 자동 다운샘플링: 1초 → 10초 → 1분 → 1시간 → 1일
- 이상 탐지 시 해당 시간대의 1초 원본 데이터 보존 기간을 자동 연장 (증거 보존)
- 대시보드에서 줌인 시 자동으로 해상도 전환: 일 뷰(1시간 집계) → 시간 뷰(1분) → 분 뷰(1초)

---

### 8. MTL 기반 통합 RCA (Multi-Task Learning)

**참조**: GaussMaster (Huawei), Dynatrace Davis AI

**개요**: 기존 단일 목적 RCA를 넘어, Multi-Task Learning 아키텍처로 하나의 Shared Encoder가 메트릭/로그/쿼리/토폴로지 데이터를 통합 표현으로 학습하고, 4개 Task Head가 동시에 추론합니다.

**아키텍처 연결 (Diagnosis Agent + AI Engine)**

- Shared Encoder: 메트릭 시계열 + ASH + pg_stat_statements + Wait Events + 토폴로지를 단일 벡터로 인코딩
- Task Head 1 (이상 분류): query_degradation / resource_exhaustion / lock_contention / replication_lag 등 유형 분류
- Task Head 2 (근본 원인 식별): 문제를 일으킨 구체적 쿼리/테이블/인덱스/파라미터 식별
- Task Head 3 (심각도 평가): CRITICAL / WARNING / NOTICE / INFO 4단계 + 수치 점수 (0.0~1.0)
- Task Head 4 (액션 추천): 해결을 위한 구체적 SQL/설정 변경/Playbook 추천
- 크로스 태스크 지식 전이로 소규모 데이터에서도 견고한 성능 (정규화 효과)

**단계적 구현 전략**:
- Phase 1 (MVP): LLM Few-shot Prompting으로 4개 태스크를 단일 프롬프트에서 동시 요청 (MTL Lite)
- Phase 2: 축적된 인시던트 데이터로 경량 Transformer Encoder 파인튜닝 (PyTorch)
- Phase 3: 풀 MTL 모델 + Continual Learning으로 새 장애 유형 자동 적응

---

### 9. DB Copilot 모드 (Tree-of-Thought)

**참조**: GaussMaster (arXiv:2506.23322) — LLM 기반 DB Copilot

**개요**: 복합 장애를 Tree-of-Thought(ToT) 추론으로 다중 진단 경로를 동시 탐색하여 최적 해결책을 도출합니다. 34개 이상의 DB 유지보수 시나리오를 목표합니다.

**아키텍처 연결 (Diagnosis Agent + Remediation Agent + Task Orchestrator)**

- 트리거 이벤트 수신 → 관련 메트릭/로그 Top-K 수집 (RAG)
- Tree-of-Thought 분기: 쿼리 문제 / 리소스 병목 / Lock Contention / 파라미터 이슈 등 다중 경로 동시 탐색
- 각 경로의 Confidence Score 평가 → 최고 점수 경로 선택
- Autonomy Level에 따라 자동 실행 또는 추천 표시
- GaussMaster 대비 차별점: 멀티 DB 플러그인 + Adaptive Autonomy + MCP/A2A 개방형 표준

---

### 10. Explainable AI & LLM Observability

**참조**: BigPanda Open Box AI, OpenObserve + OpenLIT

**Explainable AI**: 모든 AI 출력에 Confidence Score(0.0~1.0) + Reasoning Chain + Evidence Links 필수 포함. Score에 따라 Autonomy Level 자동 조정 (< 0.5 실행 불가, 0.5~0.8 관리자 확인 필수).

**LLM Observability**: AI 파이프라인 자체를 모니터링하는 메타 옵저버빌리티 레이어.
- 추적 메트릭: 토큰 사용량, 응답 지연(P50/P95/P99), RCA 정확도, 할루시네이션 비율, 모델 드리프트, API 비용
- 자동 조치: 정확도 < 70% 시 재학습 트리거, 월 예산 80% 도달 시 Offline LLM 전환 권고
- System Health 대시보드의 "AI Health" 탭으로 시각화

---

## 통합 아키텍처 다이어그램 (v3.0)

```
                    ┌──────────────────────────────────────────────┐
                    │            External AI Tools                  │
                    │  (Claude, Copilot, ChatGPT, IDE, Slack Bot)  │
                    └─────────────────┬────────────────────────────┘
                                      │ MCP Protocol
┌─────────────────┐                   │
│   Application    │  OTel Traces     │
│   (서비스들)      │────────────┐     │
└─────────────────┘            │     │
                    ┌──────────▼─────▼────────────────────────────┐
                    │      API Gateway & Integration Layer          │
                    │  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌──────────┐  │
                    │  │REST│ │ WS │ │MCP │ │A2A │ │OTel      │  │
                    │  │API │ │    │ │Srv │ │ GW │ │Collector │  │
                    │  └──┬─┘ └──┬─┘ └──┬─┘ └──┬─┘ └────┬─────┘  │
                    │     └──────┼──────┼──────┘        │         │
                    │            │  Auth Service         │         │
                    └────────────┼──────────────────────┼─────────┘
                                 │                      │
     ┌───────────────────────────┼──────────────────────┼─────────┐
     │         Core Engine Layer (Multi-Agent System)              │
     │                                                             │
     │  ┌─────────────┐  A2A  ┌──────────────┐  A2A              │
     │  │ Monitoring   │──────►│  Diagnosis    │──────►           │
     │  │ Agent        │       │  Agent        │       │          │
     │  │ +AutoBaseline│       │ +Topology RCA │       │          │
     │  │              │       │ +MTL RCA      │       │          │
     │  └──────────────┘       └──────┬────────┘       │          │
     │         │                      │RAG             │          │
     │  ┌──────▼──────┐  ┌───────────▼──┐  ┌──────────▼────────┐│
     │  │ Topology     │  │ Playbook     │  │  Remediation      ││
     │  │ Engine       │  │ Engine       │  │  Agent            ││
     │  │ (OTel→의존성) │  └──────────────┘  │ +Auto Query Tuning││
     │  └─────────────┘                     │ +DB Copilot(ToT)  ││
     │                                      └────────┬──────────┘│
     │                                               │           │
     │  ┌─────────┐ ┌───────────┐ ┌─────────────────▼─────────┐ │
     │  │  Alert   │ │   Task    │ │     Reporting Agent       │ │
     │  │ Engine   │ │ Orchestr. │ │  +AIGC +NL2SQL +EXPLAIN해석│ │
     │  │+Dynamic  │ │+5-Level   │ └───────────────────────────┘ │
     │  │Baseline  │ │Autonomy   │                               │
     │  └──────────┘ └───────────┘                               │
     │  ┌───────────────────┐  ┌───────────────────────┐         │
     │  │  Query Analyzer   │  │    Audit Logger        │         │
     │  │ +ASH +WaitEvent   │  │ +Schema Change Tracking│         │
     │  │ +Auto Tuning      │  │ +AI Reasoning Log      │         │
     │  └───────────────────┘  └───────────────────────┘         │
     │  LLM Observability (+Token/Latency/Accuracy Tracking)           │
     └────────────────────────────┬──────────────────────────────┘
                                  │
     ┌────────────────────────────┼──────────────────────────────┐
     │       Database Adapter Layer (Plugin Architecture)         │
     │  ┌─────────────┐ ┌────────┐ ┌────────┐ ┌───────────────┐ │
     │  │ PostgreSQL   │ │ MySQL  │ │ MS-SQL │ │ Schema Change │ │
     │  │ +1s ASH      │ │Adapter │ │Adapter │ │   Tracker     │ │
     │  │ +DDL Trigger │ │        │ │        │ │ (DDL 감지)     │ │
     │  └─────────────┘ └────────┘ └────────┘ └───────────────┘ │
     │                     Plugin Interface (SPI)                 │
     └────────────────────────────┬──────────────────────────────┘
                                  │
     ┌────────────────────────────┼──────────────────────────────┐
     │               Infrastructure Layer                         │
     │  ┌──────────────┐ ┌───────┐ ┌───────┐ ┌────────────────┐ │
     │  │ PostgreSQL 16 │ │Valkey │ │ Kafka │ │ pgvector + RAG │ │
     │  │ (1s metrics)  │ │       │ │       │ │                │ │
     │  │ +ASH Tables   │ │       │ │       │ │                │ │
     │  │ +pg_partman   │ │       │ │       │ │                │ │
     │  └──────────────┘ └───────┘ └───────┘ └────────────────┘ │
     │  ┌──────────┐ ┌─────────────────────────────────────────┐ │
     │  │ Meta DB   │ │    Playbook Git Repository              │ │
     │  │(Postgres) │ │    + Topology Graph Storage             │ │
     │  └──────────┘ └─────────────────────────────────────────┘ │
     └───────────────────────────────────────────────────────────┘
```

---

## 참조 솔루션 매핑

| 솔루션 | 참조한 핵심 기능 | 적용된 아키텍처 모듈 |
|--------|-----------------|---------------------|
| Oracle Autonomous AI DB | Auto-Tuning, Self-Healing, AI Agent 내장 | Auto Query Tuning, Self-Healing Pipeline, A2A Agent |
| Dynatrace Davis AI | Smartscape 토폴로지, 크로스 스택 RCA, OneAgent 자동 발견 | Full-Stack Observability, Topology Engine |
| IBM Instana | 1초 단위 메트릭, 자동 의존성 맵, 실시간 RCA | 1-Second Granularity, Auto-Baselining |
| Datadog DB Monitoring | Wait Event 분석, 실행 계획 뷰, 서비스 맵 | ASH & Wait Events, Full-Stack Observability |
| LogicMonitor Edwin AI | AI 이상 탐지, 트렌드 분석, 자연어 인시던트 요약 | Auto-Baselining, AIGC Reporting |
| DBmarlin | 스키마 변경 추적, Before/After 성능 비교 | Schema Change Tracking |
| Chat2DB | NL2SQL, AI SQL 최적화, BI 대시보드 자동 생성 | AIGC Interface, NL2SQL 확장 |
| Percona PMM 3.x | 오픈소스 멀티 DB, 오프라인 Advisor, Query Analytics | Plugin Architecture, Offline Mode |
| Xata Agent | LLM Playbook, PostgreSQL 전문 에이전트 | Playbook-as-Code, Multi-Agent |
| pganalyze + MCP | MCP 서버, EXPLAIN 추적, 쿼리 분석 | MCP Server, Query Analyzer |
| GaussMaster | Tree-of-Thought 추론, 자율 DB 유지보수 | DB Copilot, MTL RCA |
| BigPanda | Open Box AI (투명한 의사결정) | Explainable AI, Confidence Score |
| OpenObserve | 3-Layer AI, LLM Observability | LLM Observability |

---

## 전체 기능 맵 (v3.0 최종)

### 핵심 AI/LLM 기능 (7개)
1. AI 자동 베이스라인 학습 — 수동 임계값 없이 동적 이상 탐지
2. RAG 기반 맥락적 진단 — 문서+이력 참조 AI 근본원인 분석
3. NL2SQL + AIGC — 자연어 DB 질의, SQL 최적화, 리포트 생성
4. AI 자동 쿼리 튜닝 — 인덱스/쿼리/파라미터 자동 최적화
5. LLM Playbook 자동 생성 — 새 장애 유형에 대한 대응 절차 자동 작성
6. AI 실행 계획 해석 — EXPLAIN 결과를 자연어로 번역
7. Causal Inference — 스키마 변경과 성능 저하 사이의 인과관계 추론

### 옵저버빌리티 기능 (5개)
1. 1초 단위 고해상도 메트릭 수집 + 계층형 보관
2. ASH (Active Session History) + Wait Event 카테고리 분석
3. 풀스택 토폴로지 자동 발견 (App→DB→Infra 의존성 맵)
4. 스키마 변경 추적 + Before/After 성능 영향도 분석
5. OpenTelemetry 기반 분산 트레이싱 연동

### 자동화 기능 (5개)
1. Self-Healing Closed-Loop (감지→진단→대응→검증→롤백)
2. Adaptive Autonomy 5단계 자율 등급
3. Playbook-as-Code (YAML + Git + LLM 자동 생성)
4. Auto Query Tuning (추천 + 자동 적용 + 자동 검증)
5. 동적 Autonomy Level 격하 (실패 시 자동 보수적 전환)

### 연동 기능 (4개)
1. MCP Server — 외부 AI 도구(Claude, Copilot 등) 직접 연동
2. A2A Protocol — 멀티 에이전트 협업 + 외부 에이전트 연동
3. Slack/Email/Webhook 알림 + 액션 버튼
4. OTel Collector — 애플리케이션 트레이스 수신

### 관리 기능 (4개)
1. RBAC 사용자 관리 (5개 역할) + SSO/LDAP
2. 상세 감사 로깅 (AI Reasoning + Schema Change + 전 과정)
3. 멀티 DB 플러그인 아키텍처 (PostgreSQL/MySQL/MS-SQL + Custom)
4. 온/오프라인 AI (Cloud LLM + Ollama/vLLM 전환)

### 차별화 기능 (v3.3 신규, 4개)
1. MTL 기반 통합 RCA — 이상분류/원인식별/심각도/액션추천 단일 추론
2. DB Copilot (Tree-of-Thought) — 다중 진단 경로 동시 탐색 자율 유지보수
3. Explainable AI — Confidence Score + Reasoning Chain 투명 공개
4. LLM Observability — AI 파이프라인 토큰/지연/정확도/비용 자체 모니터링

---

## 솔루션 확장 로드맵 (v3.0)

### Phase 1 — MVP (3개월)
- PostgreSQL Adapter (기본 메트릭 + ASH + DDL Trigger)
- 1초 메트릭 수집 + PostgreSQL 16 네이티브 파티셔닝 계층형 보관
- 기본 대시보드 + Slack 알림 + AI 자동 베이스라인
- NL2SQL 자연어 질의 기본 기능

### Phase 2 — AI 강화 (3개월)
- RAG Pipeline + pgvector 구축
- AIGC 인터페이스 확장 (SQL 최적화, EXPLAIN 해석, 리포트 생성)
- Playbook-as-Code + Git 연동
- Auto Query Tuning (인덱스 추천 → 자동 적용)
- Schema Change Tracking + Before/After 분석
- Adaptive Autonomy 5단계

### Phase 3 — 멀티 에이전트 + 풀스택 (3개월)
- 단일 Engine → Multi-Agent(A2A) 전환
- OTel Collector + Topology Engine (풀스택 의존성 발견)
- MCP Server 노출
- Self-Healing Closed-Loop 구현
- Wait Event 심층 분석 대시보드

### Phase 4 — 멀티 DB + 솔루션화 (3개월)
- MySQL, MS-SQL Adapter 추가
- A2A 기반 외부 에이전트 연동
- 에이전트 마켓플레이스
- 멀티테넌시 + SaaS 모드
- 엔터프라이즈 라이선스 / 화이트라벨

---

## 기술 스택 (v3.2 갱신)

> **최신 기술 스택은 `docs/TECH_STACK.md`를 참조하세요.** 아래는 v3.2 반영본입니다.

| 영역 | 기술 | 비고 |
|------|------|------|
| Frontend | React 18+ + Vite, TailwindCSS, ECharts | AIGC Chat + ASH Timeline + Topology Map |
| API | **Python/FastAPI**, Strawberry(GraphQL), python-socketio | 1초 WebSocket 스트리밍 |
| MCP Server | Python, mcp SDK | MCP 표준 사양 |
| A2A Gateway | Python, A2A SDK | Google A2A 프로토콜 |
| OTel | OpenTelemetry Collector | 앱 트레이스 수신/의존성 추출 |
| Multi-Agent | LangGraph, CrewAI, LangChain | 에이전트 프레임워크 |
| AI/LLM | OpenAI GPT-4o, Claude, Ollama, vLLM | On/Offline 전환 |
| RAG | LangChain RAG, pgvector | 임베딩 + 유사도 검색 |
| NL2SQL | LangChain SQL Agent | 스키마 인식 변환 |
| Auto-Baseline | Prophet, Isolation Forest, STL | 시계열 이상 탐지 |
| DB (통합) | **PostgreSQL 16** (네이티브 파티셔닝 + pgvector) | 메타 + 메트릭 + 벡터 통합 |
| Message Queue | Kafka | A2A + 이벤트 + 1초 메트릭 |
| Cache | **Valkey** (BSD 3-Clause) | 베이스라인 캐시, Agent 상태 |
| Container | Docker, Kubernetes | 에이전트별 독립 배포 |
| Observability | OpenTelemetry, Prometheus | 자체 시스템 모니터링 (Grafana 제외 — AGPL) |
| Playbook | YAML, Git, Woodpecker CI | Playbook CI/CD |
| Package Manager | **uv** (pip 사용 금지) | Python 의존성 관리 |

---

*버전: 3.1 (기술 스택 v3.2 반영) | 작성일: 2026-03-23*
*v1.0 기본 아키텍처 + v2.0 2026 트렌드(MCP/A2A/Self-Healing/Playbook/RAG) + v3.0 산업 표준(Auto-Baselining/Full-Stack/ASH/Schema Tracking/Auto-Tuning/AIGC/1s Granularity) + v3.1 차별화(MTL RCA/DB Copilot ToT/Explainable AI/LLM Observability) 통합*
