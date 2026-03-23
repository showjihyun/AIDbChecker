# NeuralDB Use Case Specification

> **Version**: 1.0
> **Date**: 2026-03-23
> **PRD 참조**: AI_DB_Monitoring_System_PRD_v3.3.md
> **디자인 참조**: FRONTEND_DESIGN.md, UI_UX_PLAN.md
> **MVP 참조**: MVP.md
> **상태**: Approved

---

## 1. 액터 정의

| 액터 | 역할 | RBAC | 주요 목표 |
|------|------|------|----------|
| **DBA** (DB Admin) | DB 성능 관리, 장애 대응, 튜닝 | DB Admin | 장애 사전 예방, 성능 최적화, 자동화 신뢰 구축 |
| **SRE** (Operator) | 인프라 운영, 알림 대응, 에스컬레이션 | Operator | 빠른 장애 인지, 영향 범위 파악, 적절한 에스컬레이션 |
| **Manager** (Viewer) | 현황 파악, 리포트 확인 | Viewer | DB 건강 상태 한눈에 파악, 비기술적 요약 |
| **Admin** | 시스템 설정, 사용자 관리 | Super Admin | 시스템 운영, 보안, 사용자 권한 관리 |
| **External AI** | Claude Code, Copilot 등 외부 AI 도구 | API User | MCP를 통한 메트릭 조회, 진단 실행 |
| **AI Agent** (내부) | Monitoring / Diagnosis / Remediation / Reporting | System | 자동 탐지, 진단, 대응, 보고 |

---

## 2. Use Case 다이어그램

```
                          NeuralDB System
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ UC-ONBOARD  │  │ UC-MONITOR   │  │ UC-INVESTIGATE     │  │
│  │ 온보딩      │  │ 실시간 모니터 │  │ 장애 조사          │  │
│  └──────┬──────┘  └──────┬───────┘  └────────┬───────────┘  │
│         │                │                    │              │
│  ┌──────▼──────┐  ┌──────▼───────┐  ┌────────▼───────────┐  │
│  │ UC-REGISTER │  │ UC-ALERT     │  │ UC-RCA             │  │
│  │ DB 등록     │  │ 알림 수신    │  │ AI 근본원인 분석    │  │
│  └─────────────┘  └──────────────┘  └────────────────────┘  │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ UC-NL2SQL   │  │ UC-ASH       │  │ UC-CONFIDENCE      │  │
│  │ 자연어 질의  │  │ ASH 탐색     │  │ AI 신뢰도 검증     │  │
│  └─────────────┘  └──────────────┘  └────────────────────┘  │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ UC-SETTINGS │  │ UC-AUDIT     │  │ UC-MCP             │  │
│  │ 시스템 설정  │  │ 감사 로그    │  │ 외부 AI 연동        │  │
│  └─────────────┘  └──────────────┘  └────────────────────┘  │
│                                                              │
└──────────────────────────────────────────────────────────────┘

Phase 2+:
  UC-PLAYBOOK (Playbook 관리), UC-COPILOT (DB Copilot),
  UC-HEALING (Self-Healing), UC-LLM-OBS (AI 모니터링)
```

---

## 3. MVP Use Cases (Phase 1)

---

### UC-ONBOARD-001: 첫 사용자 온보딩

| 항목 | 내용 |
|------|------|
| **Spec ID** | UC-ONBOARD-001 |
| **액터** | Admin, DBA |
| **PRD 참조** | FR-ADMIN-001, FR-DB-001 |
| **화면** | Screen 6 (Add Database), Dashboard |
| **우선순위** | P0 (MVP) |
| **전제 조건** | NeuralDB가 Docker Compose로 기동된 상태 |

#### Main Flow

```
1. Admin이 브라우저에서 NeuralDB 접속 (localhost:3000)
2. 시스템이 초기 로그인 화면 표시 (기본 admin 계정)
3. Admin이 이메일/비밀번호로 로그인
4. Dashboard가 EmptyState로 표시 ("Add Your First Database" CTA)
5. Admin이 CTA 클릭 → DB 등록 화면 이동
   → UC-REGISTER-001로 이동
6. DB 등록 완료 후 Dashboard에 인스턴스 카드 표시
7. 30초 후 첫 메트릭 데이터가 차트에 표시
```

#### Exception Flow

| 예외 | 처리 |
|------|------|
| E1: Docker 서비스 미기동 | `docker compose up` 안내 메시지 |
| E2: 기본 admin 비밀번호 미변경 | 첫 로그인 시 비밀번호 변경 강제 |

#### 인수 기준
- AC: 로그인 후 3초 이내 Dashboard 표시 (AC-7)
- AC: Docker Compose 한 줄로 전체 기동 (AC-10)

---

### UC-REGISTER-001: DB 인스턴스 등록

| 항목 | 내용 |
|------|------|
| **Spec ID** | UC-REGISTER-001 |
| **액터** | DBA, Admin |
| **PRD 참조** | FR-DB-001, FR-DB-004 |
| **화면** | Screen 6 (Add Database Wizard) |
| **우선순위** | P0 (MVP) |
| **전제 조건** | 로그인 완료, DB Admin 이상 역할 |

#### Main Flow

```
1. DBA가 Settings → Instances → "Add Database" 클릭
2. Step 1: DB 유형 선택 (PostgreSQL 16 — MVP는 PG만)
3. Step 2: 연결 정보 입력
   - Host / Port / Database Name
   - Username / Password (또는 SSL 인증서)
   - 표시 이름 (예: "pg-prod-01")
4. "Test Connection" 클릭
5. 시스템이 asyncpg로 연결 테스트 + pg_stat_statements 존재 확인
6. ✅ 연결 성공 표시
7. Step 3: 수집 옵션 설정
   - ASH 활성화 (기본: ON)
   - 수집 해상도 (기본: Hot 1초)
   - 알림 채널 (Slack Webhook URL)
8. "Save & Start Monitoring" 클릭
9. 시스템이 db_instances 테이블에 저장 + Celery 수집 태스크 등록
10. Dashboard로 리다이렉트 → 새 인스턴스 카드 표시
```

#### Alternative Flow

| 분기 | 처리 |
|------|------|
| A1: 연결 실패 | 에러 메시지 표시 ("Connection refused: check host/port"), 재시도 가능 |
| A2: pg_stat_statements 미설치 | 경고 표시 + 설치 가이드 링크, 쿼리 통계 없이 진행 가능 |
| A3: SSL 필요 환경 | SSL 인증서 업로드 필드 표시 |
| A4: 이미 등록된 Host:Port | 중복 경고 + 기존 인스턴스로 이동 제안 |

#### Exception Flow

| 예외 | 처리 |
|------|------|
| E1: 네트워크 타임아웃 (5초) | "연결 시간 초과. 네트워크 확인" 메시지 |
| E2: 인증 실패 | "인증 실패. 사용자명/비밀번호 확인" 메시지 |
| E3: 최대 인스턴스 초과 (MVP: 10대) | "MVP 라이선스 최대 10대. 업그레이드 안내" |

#### 인수 기준
- AC: 연결 테스트 성공 시 3초 이내 응답 (AC-1)
- AC: 등록 후 1초 메트릭 수집 시작 (AC-1)

---

### UC-MONITOR-001: 실시간 대시보드 모니터링

| 항목 | 내용 |
|------|------|
| **Spec ID** | UC-MONITOR-001 |
| **액터** | DBA, SRE, Manager |
| **PRD 참조** | FR-DASH-001, FR-AI-001 |
| **화면** | Screen 1 (Dashboard — MVP는 인스턴스 카드 그리드) |
| **우선순위** | P0 (MVP) |
| **전제 조건** | 1개 이상 DB 인스턴스 등록, 메트릭 수집 중 |

#### Main Flow

```
1. 사용자가 Dashboard 접속
2. Summary 카드 4개 표시:
   - Total Instances: 등록된 DB 수
   - Active Sessions: 전체 활성 세션 수
   - Anomalies: 현재 이상 탐지 수 (AI 베이스라인 기반)
   - Avg Response Time: 전체 평균 응답 시간
3. 인스턴스 카드 그리드 표시 (각 카드: 이름, 상태, CPU, 커넥션, TPS)
4. WebSocket으로 1초마다 메트릭 갱신 (카드 내 수치 실시간 업데이트)
5. 이상 탐지 시 해당 카드에 빨간 테두리 + Anomaly 배지
6. 사용자가 카드 클릭 → 해당 인스턴스 ASH Explorer로 이동
   → UC-ASH-001로 이동
```

#### Alternative Flow

| 분기 | 처리 |
|------|------|
| A1: 인스턴스 0개 | EmptyState → UC-REGISTER-001로 유도 |
| A2: WebSocket 연결 끊김 | 자동 재연결 (3초 간격, 최대 5회), 실패 시 "연결 끊김" 배너 |
| A3: AI 베이스라인 미학습 (2주 미만) | "Learning" 배지 표시, 수동 임계값으로 탐지 |

#### 인수 기준
- AC: 초기 로딩 < 3초 (AC-7)
- AC: WebSocket 메트릭 갱신 < 1초 (AC-7)
- AC: AI 베이스라인 이상 탐지 동작 (AC-3)

---

### UC-ALERT-001: 알림 수신 및 대응

| 항목 | 내용 |
|------|------|
| **Spec ID** | UC-ALERT-001 |
| **액터** | DBA, SRE |
| **PRD 참조** | FR-ALERT-001, FR-ALERT-003, FR-AI-014 |
| **화면** | Slack + Dashboard (Incidents) |
| **우선순위** | P0 (MVP) |
| **전제 조건** | Slack Webhook 설정 완료, AI 베이스라인 학습 완료 |

#### Main Flow

```
1. AI가 이상 탐지 → 인시던트 자동 생성
2. 경량 RCA 자동 실행:
   a. pgvector로 유사 과거 인시던트 Top-3 검색 (경량 RAG)
   b. MTL Lite 4-Head 동시 추론 (이상분류/원인/심각도/액션)
   c. Confidence Score 계산
3. Slack 알림 발송 (30초 이내):
   ┌─────────────────────────────────────────┐
   │ 🔴 CRITICAL | pg-prod-01                │
   │ CPU 사용률 95% (베이스라인: 40~60%)       │
   │                                         │
   │ AI 판단: query_performance_degradation   │
   │ 원인: Missing index on orders.created_at │
   │ 신뢰도: 🟢 0.87 (HIGH)                   │
   │ 추천: CREATE INDEX CONCURRENTLY ...      │
   │                                         │
   │ [상세보기] [NL2SQL]                       │
   └─────────────────────────────────────────┘
4. SRE가 [상세보기] 클릭 → 웹 브라우저에서 인시던트 상세 표시
5. 인시던트 상세에서:
   - Confidence Badge (0.87 HIGH 녹색)
   - Reasoning Chain 펼침 가능
   - Evidence Links (메트릭/ASH 페이지 링크)
   - 추천 액션 목록
6. SRE가 액션 확인 후 DBA에게 에스컬레이션 또는 직접 조치
```

#### Alternative Flow

| 분기 | 처리 |
|------|------|
| A1: Confidence < 0.5 (LOW) | Slack에 "⚠️ AI 판단 불확실, 수동 분석 필요" 표시 |
| A2: 유사 인시던트 0건 (RAG) | "새로운 유형의 장애. 과거 사례 없음" 표시 |
| A3: LLM 타임아웃 | 메트릭 기반 기본 알림만 발송 (AI 분석 없이), 이후 비동기 RCA |
| A4: Slack Webhook 실패 | Webhook 알림으로 폴백 시도, 실패 시 대시보드 인시던트만 |

#### Exception Flow

| 예외 | 처리 |
|------|------|
| E1: 알림 폭주 (5분 내 10건+) | Alert Throttling: 동일 인스턴스 알림 5분 쿨다운 |
| E2: 오탐 (False Positive) | 사용자가 "Dismiss" → 베이스라인 재학습 데이터로 활용 |

#### 인수 기준
- AC: 이상 탐지 → Slack 알림 30초 이내 (AC-4)
- AC: 경량 RCA 1줄 요약 + Confidence Score (AC-11)
- AC: MTL Lite 4-Head 동시 응답 (AC-12)
- AC: RAG 검색 결과가 RCA에 포함 (AC-13)

---

### UC-ASH-001: ASH Explorer 심층 분석

| 항목 | 내용 |
|------|------|
| **Spec ID** | UC-ASH-001 |
| **액터** | DBA |
| **PRD 참조** | FR-DASH-003, FR-DB-001 |
| **화면** | Screen 3 (ASH Explorer) |
| **우선순위** | P0 (MVP) |
| **전제 조건** | 대상 인스턴스 ASH 수집 활성화 |

#### Main Flow

```
1. DBA가 인스턴스 카드 또는 SideNav "ASH Explorer" 클릭
2. Temporal Zoom 바에서 시간 범위 선택 (기본: 최근 1시간)
3. ASH Heatmap 표시:
   - 행: Network, I/O, Lock, CPU (Wait Event 카테고리)
   - 열: 시간 (해상도에 따라 1초~1분)
   - 셀 색상: 대기 세션 수 기반 (Idle→I/O→Lock→Critical)
4. DBA가 빨간 셀(Lock) 클릭
5. Session Detail Table이 해당 시점으로 필터링:
   - PID, Query, State, Wait Event, Duration
6. DBA가 특정 세션의 "Explain" 버튼 클릭
7. AI Interpretation 플로팅 카드 표시:
   - 자연어 해석: "이 쿼리는 orders 테이블에서 200만 행을 전체 스캔 중"
   - SQL 추천: "CREATE INDEX idx_orders_status ON orders(status)"
8. DBA가 SQL을 클립보드 복사 → 직접 실행 또는 DBA 채널에 공유
```

#### Alternative Flow

| 분기 | 처리 |
|------|------|
| A1: 해상도 전환 (시→분→초) | Temporal Zoom 드래그로 자동 해상도 변경 |
| A2: Wait Event 특정 카테고리 필터 | 우측 Wait Breakdown에서 카테고리 클릭 → Heatmap 필터링 |
| A3: ASH 데이터 없음 (수집 비활성화) | "ASH 수집이 비활성화됨. Settings에서 활성화하세요" |

#### 인수 기준
- AC: ASH 1초 히트맵 실시간 표시 (AC-2)
- AC: 셀 클릭 → 세션 테이블 필터링 동작

---

### UC-RCA-001: AI 근본원인 분석 (경량 RCA)

| 항목 | 내용 |
|------|------|
| **Spec ID** | UC-RCA-001 |
| **액터** | DBA, AI Agent |
| **PRD 참조** | FR-AI-010, FR-AI-011, FR-AI-014 |
| **AI Spec 참조** | MTL_RCA_SPEC.md, CONFIDENCE_SCORE_SPEC.md, LIGHTWEIGHT_RAG_SPEC.md |
| **화면** | Incidents 상세 |
| **우선순위** | P0 (MVP) |
| **전제 조건** | 인시던트 존재 |

#### Main Flow

```
1. 인시던트 생성 (자동 또는 수동)
2. [자동] 경량 RAG 검색:
   a. 인시던트 설명 + 메트릭 스냅샷을 임베딩 (sentence-transformers)
   b. pgvector cosine similarity로 Top-3 유사 과거 사례 검색
   c. similarity ≥ 0.7인 결과만 사용
3. [자동] MTL Lite 추론 (LLM Few-shot):
   a. 현재 메트릭 + ASH 요약 + Top 쿼리 + RAG 결과를 프롬프트 구성
   b. LLM에 단일 요청으로 4-Head 동시 추론:
      - Head 1: 이상 분류 (query_performance, resource_exhaustion, ...)
      - Head 2: 근본 원인 ("Missing index on orders.created_at")
      - Head 3: 심각도 (0.72 → WARNING)
      - Head 4: 추천 액션 (CREATE INDEX ..., confidence: 0.91)
   c. Reasoning Chain 생성 (4단계 추론 과정)
   d. Evidence Links 생성 (메트릭/ASH API 경로)
4. [자동] Confidence Score 계산:
   - 가중 평균: anomaly(0.25) + root_cause(0.35) + severity(0.15) + action(0.25)
   - 결과: 0.87 (HIGH)
5. mtl_predictions 테이블에 저장
6. 대시보드 인시던트 상세에 결과 표시:
   ┌─ AI Root Cause Analysis ─────────────────────┐
   │ 🟢 Confidence: 0.87 (HIGH)                    │
   │                                               │
   │ Type: query_performance_degradation            │
   │ Cause: Missing index on orders.created_at      │
   │ Severity: WARNING (0.72)                       │
   │                                               │
   │ ▼ Reasoning Chain                             │
   │   ① CPU 95% (baseline +40%) → 쿼리 부하 증가   │
   │   ② Top 쿼리: SELECT * FROM orders... (12.8s)  │
   │   ③ EXPLAIN: Seq Scan on orders (cost=45000)   │
   │   ④ 유사 사례 3건 → 인덱스 생성으로 해결         │
   │                                               │
   │ Suggested: CREATE INDEX CONCURRENTLY ...       │
   │                                               │
   │ [피드백: 👍 👎]                                 │
   └───────────────────────────────────────────────┘
7. DBA가 피드백 제출 (👍/👎) → 정확도 추적에 활용
```

#### Alternative Flow

| 분기 | 처리 |
|------|------|
| A1: Confidence < 0.5 (LOW) | 🟠 배지 표시, "수동 분석 권장" 메시지 |
| A2: RAG 결과 0건 | "새로운 유형 장애" 표시, 메트릭만으로 분석 |
| A3: LLM JSON 파싱 실패 | 2회 재시도 → 실패 시 confidence: 0.0, type: unknown |
| A4: 오프라인 모드 | Ollama Mistral:7b로 자동 전환, 응답 지연 허용 |

#### Exception Flow

| 예외 | 처리 |
|------|------|
| E1: LLM API 타임아웃 (30초) | Offline LLM 폴백 → 재실패 시 "AI 분석 불가" + 수동 알림 |
| E2: pgvector 검색 실패 | RAG 없이 MTL 실행 (rag_results = "No similar incidents") |
| E3: 동시 다발 인시던트 (5건+) | severity 기준 우선순위 큐 처리 |

#### 인수 기준
- AC: 인시던트 → RCA 30초 이내 (AC-11)
- AC: 4-Head 동시 JSON 응답 (AC-12)
- AC: RAG 검색 결과 포함 (AC-13)
- AC: Confidence Score 0.0~1.0 범위 (FS-AI-010 AC-2)
- AC: Reasoning Chain 최소 3단계 (FS-AI-010 AC-3)

---

### UC-CONFIDENCE-001: AI 신뢰도 검증 및 피드백

| 항목 | 내용 |
|------|------|
| **Spec ID** | UC-CONFIDENCE-001 |
| **액터** | DBA, SRE |
| **PRD 참조** | FR-AI-011 |
| **AI Spec 참조** | CONFIDENCE_SCORE_SPEC.md |
| **화면** | Incidents 상세 (Confidence Badge + Reasoning Chain) |
| **우선순위** | P0 (MVP) |
| **전제 조건** | MTL 예측 결과 존재 |

#### Main Flow

```
1. DBA가 인시던트 상세에서 Confidence Badge 확인
   - 🟢 0.87 HIGH → "신뢰할 수 있는 분석"
2. Badge 클릭 → Reasoning Chain 펼침 패널 표시
3. 각 추론 단계를 검토:
   - 단계별 근거 태그 (metric / ash / query / rag)
   - 데이터 포인트 (CPU: 95%, similarity: 0.92 등)
4. Evidence Links 클릭 → 해당 메트릭/ASH 페이지로 이동하여 원본 데이터 검증
5. DBA가 AI 판단의 정확성을 평가하여 피드백 제출:
   - 👍 (정확) → feedback_correct: true
   - 👎 (부정확) → feedback_correct: false + 정답 입력 (선택)
6. 피드백이 mtl_predictions.feedback_* 에 저장
7. 주간 정확도 집계에 반영
```

#### Alternative Flow

| 분기 | 처리 |
|------|------|
| A1: Confidence < 0.3 (VERY_LOW) | 🔴 배지 + "AI 판단 불확실. 수동 분석 필수" 경고 |
| A2: Evidence Link 만료 (7일+) | "(데이터 만료)" 표시, 클릭 차단 |
| A3: 피드백에서 정답 제공 | correct_anomaly_type, correct_root_cause 저장 → Phase 2 재학습 데이터 |

#### 인수 기준
- AC: Confidence Badge 4단계 색상 표시 (FS-AI-011 AC-4)
- AC: Reasoning Chain 펼침 패널 동작 (FS-AI-011 AC-5)
- AC: Evidence Links 네비게이션 (FS-AI-011 AC-6)
- AC: 피드백 저장 (FS-AI-011 AC-7)

---

### UC-NL2SQL-001: 자연어 DB 질의

| 항목 | 내용 |
|------|------|
| **Spec ID** | UC-NL2SQL-001 |
| **액터** | DBA, SRE, Manager |
| **PRD 참조** | FR-AI-003 |
| **화면** | NL2SQL Floating Chat (전체 화면에서 접근 가능) |
| **우선순위** | P0 (MVP) |
| **전제 조건** | 1개 이상 DB 인스턴스 등록 |

#### Main Flow

```
1. 사용자가 SideNav 하단 "NL2SQL Assistant" 버튼 클릭
2. 플로팅 챗 위젯 열림 (우하단)
3. 사용자가 자연어 입력: "오늘 가장 느린 쿼리 TOP 5"
4. 시스템이 LangChain SQL Agent로 처리:
   a. 자연어 → SQL 변환 (읽기 전용 SELECT만 허용)
   b. 생성된 SQL 표시 (코드 블록)
   c. SQL 자동 실행 → 결과 테이블 표시
5. 사용자가 결과 확인 → 추가 질문 가능
   - "이 중 orders 테이블 관련 쿼리만"
   - "실행 계획 보여줘" (Phase 2 EXPLAIN 해석)
```

#### Alternative Flow

| 분기 | 처리 |
|------|------|
| A1: SQL 생성 실패 | "질문을 이해하지 못했습니다. 다시 시도해 주세요" |
| A2: 결과 0건 | "해당 조건의 데이터가 없습니다" |
| A3: 쓰기 쿼리 시도 | "읽기 전용 질의만 지원합니다" 차단 |
| A4: 대상 인스턴스 미선택 | 인스턴스 선택 드롭다운 표시 |

#### 인수 기준
- AC: "가장 느린 쿼리 5개" → 올바른 SQL 생성 (AC-5, 성공률 >80%)

---

### UC-SETTINGS-001: 시스템 설정 관리

| 항목 | 내용 |
|------|------|
| **Spec ID** | UC-SETTINGS-001 |
| **액터** | Admin |
| **PRD 참조** | FR-ADMIN-001~003 |
| **화면** | Settings |
| **우선순위** | P0 (MVP) |

#### Main Flow

```
1. Admin이 SideNav "Settings" 클릭
2. 설정 탭:
   a. Instances: DB 인스턴스 목록/추가/수정/삭제
   b. Alerts: 알림 채널 관리 (Slack Webhook, 이메일)
   c. Users: 사용자 관리 (RBAC 5역할)
   d. System: 시스템 상태 (/health)
3. Users 탭에서:
   - 사용자 목록 (이름, 역할, 최종 로그인)
   - "Add User" → 이메일, 역할 선택, 임시 비밀번호 생성
   - 역할 변경: 드롭다운으로 역할 선택 → 저장
4. 모든 변경이 audit_logs에 기록
```

#### 인수 기준
- AC: RBAC 5역할 동작 — Viewer는 쓰기 불가 (AC-6)
- AC: 모든 변경에 감사 로그 기록 (AC-9)

---

### UC-SCHEMA-001: 스키마 변경 감지

| 항목 | 내용 |
|------|------|
| **Spec ID** | UC-SCHEMA-001 |
| **액터** | DBA, AI Agent |
| **PRD 참조** | FR-DASH-004 (Phase 2), MVP-SCHEMA-001~002 |
| **화면** | Dashboard 타임라인 |
| **우선순위** | P0 (MVP — 감지만, 영향 분석은 Phase 2) |

#### Main Flow

```
1. DBA가 대상 DB에서 DDL 실행 (CREATE INDEX, ALTER TABLE 등)
2. PostgreSQL Event Trigger가 DDL 이벤트 캡처
3. schema_changes 테이블에 저장
4. Dashboard에서 스키마 변경 타임라인 표시:
   - 시간 / DDL 유형 / 테이블 / 실행자
5. DBA가 변경 이력을 시간순으로 조회
```

#### 인수 기준
- AC: CREATE/ALTER/DROP 감지 및 이력 표시 (AC-8)

---

## 4. Phase 2+ Use Cases (사전 정의)

### UC-COPILOT-001: DB Copilot 자율 진단 (Phase 2)

| 항목 | 내용 |
|------|------|
| **Spec ID** | UC-COPILOT-001 |
| **액터** | DBA, AI Agent |
| **PRD 참조** | FR-AI-012 |
| **AI Spec 참조** | COPILOT_SPEC.md |
| **우선순위** | P1 (Phase 2) |

#### Main Flow 요약

```
1. DBA가 인시던트에서 "Run DB Copilot" 클릭
2. Tree-of-Thought 추론으로 4+ Branch 동시 탐색
3. 각 Branch Score 계산 → 최적 경로 선택
4. Confidence + Autonomy Level 확인 후 실행/추천
5. 결과 표시: Branch 스코어 비교 + 선택 경로 상세
```

---

### UC-HEALING-001: Self-Healing 자동 복구 (Phase 2)

| 항목 | 내용 |
|------|------|
| **Spec ID** | UC-HEALING-001 |
| **PRD 참조** | FR-AUTO-001~005 |
| **화면** | Screen 2 (Self-Healing Dashboard) |
| **우선순위** | P1 (Phase 2) |

#### Main Flow 요약

```
1. 인시던트 → RCA → Playbook 매칭
2. Autonomy Level 확인:
   - L3+: 자동 실행 → SLO 검증 → 성공/롤백
   - L2: 관리자 승인 대기 → 승인 → 실행
   - L0~1: 추천만 표시
3. 실행 결과 Before/After 비교
4. 실패 시 자동 롤백 + Autonomy 1단계 격하
```

---

### UC-LLM-OBS-001: AI 시스템 모니터링 (Phase 2)

| 항목 | 내용 |
|------|------|
| **Spec ID** | UC-LLM-OBS-001 |
| **PRD 참조** | FR-AI-013 |
| **AI Spec 참조** | LLM_OBSERVABILITY_SPEC.md |
| **화면** | System Health → AI Health 탭 |
| **우선순위** | P1 (Phase 2) |

#### Main Flow 요약

```
1. Admin이 System Health → "AI Health" 탭 클릭
2. 위젯 4개 표시: 토큰 사용량, 응답 지연, 정확도, 할루시네이션
3. 일일 토큰 예산 초과 시 Offline LLM 자동 전환 확인
4. 주간 정확도 < 70% 시 재학습 트리거
```

---

### UC-MCP-001: 외부 AI 도구 연동 (Phase 3)

| 항목 | 내용 |
|------|------|
| **Spec ID** | UC-MCP-001 |
| **PRD 참조** | FR-ALERT-004 |
| **Spec 참조** | MCP_INTEGRATION.md |
| **우선순위** | P1 (Phase 3) |

#### Main Flow 요약

```
1. External AI (Claude Code)가 MCP Protocol로 NeuralDB 접속
2. Resources 조회: 인스턴스 목록, 메트릭, 인시던트
3. Tools 호출: query_metrics, nl2sql, copilot_diagnose
4. Prompts 활용: diagnose-incident, optimize-query
5. 결과를 AI 도구 내에서 표시/활용
```

---

## 5. Use Case → Spec → Test 추적 매트릭스

| Use Case | PRD FR | Feature Spec | Test Spec AC | 화면 |
|----------|--------|-------------|-------------|------|
| UC-ONBOARD-001 | FR-ADMIN-001 | API_SPEC §Auth | AC-7, AC-10 | Dashboard, Login |
| UC-REGISTER-001 | FR-DB-001 | API_SPEC §Instances | AC-1 | Screen 6 |
| UC-MONITOR-001 | FR-DASH-001, FR-AI-001 | API_SPEC §Metrics, AGENT_SPEC §Monitoring | AC-3, AC-7 | Screen 1 |
| UC-ALERT-001 | FR-ALERT-001, FR-AI-014 | MTL_RCA_SPEC, CONFIDENCE_SCORE_SPEC | AC-4, AC-11, AC-12, AC-13 | Slack, Incidents |
| UC-ASH-001 | FR-DASH-003, FR-DB-001 | API_SPEC §ASH | AC-2 | Screen 3 |
| UC-RCA-001 | FR-AI-010~011 | MTL_RCA_SPEC, LIGHTWEIGHT_RAG_SPEC | AC-11, AC-12, AC-13 | Incidents |
| UC-CONFIDENCE-001 | FR-AI-011 | CONFIDENCE_SCORE_SPEC | FS-AI-011 AC-4~7 | Incidents |
| UC-NL2SQL-001 | FR-AI-003 | API_SPEC §NL2SQL | AC-5 | NL2SQL Chat |
| UC-SETTINGS-001 | FR-ADMIN-001~003 | API_SPEC §Users, §Alerts | AC-6, AC-9 | Settings |
| UC-SCHEMA-001 | MVP-SCHEMA-001~002 | API_SPEC §Schema | AC-8 | Dashboard |

---

## 6. Use Case 변경 추적

| Use Case 변경 | 후속 조치 |
|-------------|----------|
| Main Flow 변경 | 대응 Feature Spec AC 갱신 → TEST_STRATEGY에 따라 테스트 갱신 |
| 액터 추가 | RBAC 역할 확인 → API_SPEC 권한 갱신 |
| 화면 변경 | FRONTEND_DESIGN.md 컴포넌트 갱신 → Frontend Test 갱신 |
| Exception Flow 추가 | API_SPEC Error Code 갱신 → Backend Test 에러 케이스 추가 |
| Phase 2+ Use Case 활성화 | Feature Spec 상태 Draft→Approved → 테스트 생성 |
