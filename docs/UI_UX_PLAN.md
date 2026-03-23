# NeuralDB UI/UX 기획서

> **Version**: 1.0
> **Date**: 2026-03-21
> **Design Source**: [Google Stitch Project](https://stitch.withgoogle.com/projects/11640044698331273458)
> **Design Spec**: `docs/FRONTEND_DESIGN.md`
> **MVP Spec**: `docs/MVP.md`
> **PRD 참조**: FR-DASH-001~005, FR-AI-003, FR-ADMIN-001

---

## 1. 전체 화면 구성

### 1.1 화면 목록 (7개 디자인 + 2개 신규)

| # | 화면명 | Stitch | Phase | MVP | 설명 |
|---|--------|--------|-------|-----|------|
| 1 | Dashboard | screen1_topology | MVP | **변형** | 토폴로지 → 인스턴스 카드 그리드로 변경 |
| 2 | Self-Healing & Playbook | screen2_selfhealing | Phase 2 | 제외 | 자동화 큐, Playbook 에디터, 감사 로그 |
| 3 | ASH Explorer | screen3_ash | MVP | **전체** | ASH 히트맵, 세션 테이블, AI 해석 |
| 4 | Diagnosis & RCA | screen4_diagnosis | Phase 2 | **부분** | 인시던트 목록만 (RCA 패널 제외) |
| 5 | Topology Explorer | screen5_topology_explorer | Phase 3 | 제외 | 풀스택 토폴로지 전용 탐색 |
| 6 | Add Database Wizard | screen6_add_database | MVP | **전체** | 3단계 DB 등록 마법사 |
| 7 | Diagnosis User Flow | screen7_diagnosis_flow | - | 참조 | UX 문서 (구현 대상 아님) |
| 8 | Settings (신규) | 없음 | MVP | **신규** | 인스턴스 관리, 알림, 사용자 관리 |
| 9 | System Health (신규) | 없음 | MVP | **신규** | 자체 시스템 상태 (간단) |

---

## 2. 라우팅 구조 (TanStack Router)

```
/                           → Dashboard (redirect)
/dashboard                  → Screen 1: 메인 대시보드
/ash/:instanceId            → Screen 3: ASH Explorer
/incidents                  → Screen 4: 인시던트 목록 (MVP)
/incidents/:id              → Screen 4: 인시던트 상세 (Phase 2: RCA 포함)
/topology                   → Screen 5: 토폴로지 (Phase 3)
/playbook                   → Screen 2: Playbook 관리 (Phase 2)
/settings                   → Screen 8: 설정 메인
/settings/instances         → 인스턴스 목록/관리
/settings/instances/new     → Screen 6: DB 등록 마법사
/settings/instances/:id     → 인스턴스 상세/수정
/settings/alerts            → 알림 채널 관리
/settings/users             → 사용자 관리 (RBAC)
/system                     → Screen 9: System Health
/login                      → 로그인 (인증 전)
```

### MVP 라우트 (구현 대상)

```
/dashboard                  ✅
/ash/:instanceId            ✅
/incidents                  ✅
/settings                   ✅
/settings/instances         ✅
/settings/instances/new     ✅
/settings/instances/:id     ✅
/settings/alerts            ✅
/settings/users             ✅
/system                     ✅ (간단 버전)
/login                      ✅
```

---

## 3. 글로벌 레이아웃

```
┌─────────────────────────────────────────────────────────────┐
│  TopNavBar (fixed, h-16, z-50)                              │
│  [NeuralDB]  [Health: 98%] [On-Premise]     [🔍] [🔔] [👤]  │
├──────────┬──────────────────────────────────────────────────┤
│          │                                                  │
│ SideNav  │  <RouterOutlet />                               │
│ (w-64)   │                                                  │
│          │  Page Content                                    │
│ Dashboard│                                                  │
│ Topology │                                                  │
│ Diagnosis│                                                  │
│ ASH      │                                                  │
│ Playbook │                                                  │
│ Settings │                                                  │
│          │                                                  │
│ ─────── │                                                  │
│ [NL2SQL] │                                    ┌───────────┐│
│ ─────── │                                    │ NL2SQL    ││
│ Docs     │                                    │ 플로팅 챗  ││
│ Support  │                                    └───────────┘│
└──────────┴──────────────────────────────────────────────────┘
```

### TopNavBar 구성

| 위치 | 요소 | 동작 |
|------|------|------|
| 좌측 | "NeuralDB" 로고 | `/dashboard`로 이동 |
| 좌측 | Health 상태 탭 | 시스템 전체 헬스 요약 (WebSocket 실시간) |
| 좌측 | 환경 표시 | On-Premise / Cloud / Hybrid |
| 우측 | 검색바 | 인스턴스/인시던트 글로벌 검색 |
| 우측 | 알림 아이콘 | 미확인 인시던트 수 뱃지 |
| 우측 | 사용자 아이콘 | 프로필, 로그아웃 드롭다운 |

### SideNav 구성

| 요소 | 아이콘 | MVP | 동작 |
|------|--------|-----|------|
| 상태 카드 | cloud_done | ✅ | Autonomy Level + Latency 표시 |
| Dashboard | dashboard | ✅ | `/dashboard` |
| Topology | hub | Phase 3 | `/topology` (비활성 표시) |
| Diagnosis | troubleshoot | ✅ | `/incidents` |
| ASH Explorer | analytics | ✅ | 인스턴스 선택 후 `/ash/:id` |
| Playbook | menu_book | Phase 2 | `/playbook` (비활성 표시) |
| Settings | settings | ✅ | `/settings` |
| 구분선 | | | |
| NL2SQL 버튼 | bolt | ✅ | 플로팅 챗 토글 |
| Documentation | help | ✅ | 외부 링크 |
| Support | contact_support | ✅ | 외부 링크 |

**비활성 메뉴 처리**: Phase 2+ 기능은 메뉴에 표시하되 `opacity-40 cursor-not-allowed` + "Coming Soon" 툴팁.

---

## 4. 화면별 상세 기획

### 4.1 Dashboard (MVP — Screen 1 변형)

**URL**: `/dashboard`
**디자인 참조**: `screen1_topology.html` + `screenshots/screen1_topology.png`

#### 레이아웃
```
┌──────────────────────────────────────────────────────┐
│  Summary Cards (4열 grid)                            │
│  [Total: 52] [Active: 1,240] [Anomalies: 2] [12ms]  │
├──────────────────────────────────────────────────────┤
│  Instance Card Grid (2×5 또는 3×4)                    │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐               │
│  │pg-01 │ │pg-02 │ │pg-03 │ │pg-04 │               │
│  │✅ 45% │ │⚠️ 82%│ │✅ 30% │ │✅ 55% │               │
│  └──────┘ └──────┘ └──────┘ └──────┘               │
├──────────────────────┬───────────────────────────────┤
│  Resource Chart      │  AI Insights Feed             │
│  (ECharts 시계열)     │  [Predictive] [Anomaly] [Opt] │
└──────────────────────┴───────────────────────────────┘
```

#### 컴포넌트

| 컴포넌트 | Props | 데이터 소스 | 실시간 |
|---------|-------|-----------|--------|
| `SummaryCard` ×4 | label, value, icon, trend, borderColor | `GET /instances` 집계 | WebSocket |
| `InstanceGrid` | instances[] | `GET /instances` | WebSocket (헬스 변경 시) |
| `InstanceCard` | name, dbType, cpu, memory, status | `GET /instances/{id}/metrics/latest` | WebSocket |
| `ResourceChart` | instanceId, timeRange | `GET /instances/{id}/metrics` | WebSocket (1초) |
| `AIInsightsFeed` | incidents[] | `GET /incidents?source=ai_baseline` | WebSocket |

#### 인터랙션
- 인스턴스 카드 클릭 → `/ash/{instanceId}` (ASH Explorer 이동)
- Summary Card "Anomalies" 클릭 → `/incidents?severity=critical`
- AI Insight "Apply Tune" 클릭 → Phase 2 알림 ("Playbook 기능은 Phase 2에서 제공")

---

### 4.2 ASH Explorer (MVP — Screen 3 전체)

**URL**: `/ash/:instanceId`
**디자인 참조**: `screen3_ash.html` + `screenshots/screen3_ash.png`

#### 레이아웃
```
┌──────────────────────────────────────────┬───────────┐
│  Temporal Zoom                           │           │
│  [1s] [10s] [1m]   Range: 14:32:00-59   │ Aggregate │
├──────────────────────────────────────────┤ Wait      │
│  ASH Heatmap (4행 × 24열)                │ Breakdown │
│  Network ░░░░░░░░░░░░░░░░░░░░░░░░       │           │
│  I/O     ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓      │ Lock: 45% │
│  Lock    ░░████████░░░░░███░░░░░░       │ I/O:  30% │
│  CPU     ▒▒▒▒▓▓▒▒░░▒▒▒▓▓▒▒░░▒▒▒▓      │ CPU:  25% │
├──────────────────────────────────────────┤           │
│  Session Detail Table                    │ AI        │
│  PID | Query | State | Wait | Duration  │ Insights  │
│  8829| SELECT| Locked| TX   | 1.2s     │ Card      │
│  4431| INSERT| Active| I/O  | 0.4s  [AI]│           │
└──────────────────────────────────────────┴───────────┘
                                    ┌─────────────────┐
                                    │ AI Interpretation│
                                    │ (플로팅 카드)     │
                                    └─────────────────┘
```

#### 컴포넌트

| 컴포넌트 | 설명 | 데이터 소스 |
|---------|------|-----------|
| `TemporalZoom` | 해상도 버튼(1s/10s/1m) + 미니 바차트 + 슬라이더 | 로컬 상태 |
| `ASHHeatmap` | 4×24 그리드, Wait Event 카테고리별 색상 | `GET /ash/heatmap` |
| `SessionTable` | PID, Query, State, Wait Event, Duration | `GET /ash` |
| `WaitBreakdown` | 프로그레스 바 3개 (Lock/I/O/CPU) | `GET /ash/wait-breakdown` |
| `AIInterpretation` | 플로팅 카드, SQL 추천, Execute/Ignore 버튼 | `POST /nl2sql/explain` |

#### 인터랙션
- 히트맵 셀 클릭 → 세션 테이블 해당 시간대 필터링
- 세션 행 hover → "Explain" 버튼 표시 (`opacity-0 → opacity-100`)
- "Explain" 클릭 → AI Interpretation 플로팅 카드 표시
- "Execute Fix" 클릭 → Phase 2 알림 (MVP에서는 SQL 복사만 제공)

---

### 4.3 Incidents (MVP — Screen 4 부분)

**URL**: `/incidents`
**디자인 참조**: `screen4_diagnosis.html` + `screenshots/screen4_diagnosis.png`

#### MVP 범위
- ✅ 좌측: 인시던트 목록 (severity 뱃지, 시간순, 필터)
- ❌ 우측: AI RCA 패널 → Phase 2
- ❌ 인과 관계 체인 시각화 → Phase 2
- ❌ Generate Playbook / Auto-Tune 버튼 → Phase 2

#### 레이아웃 (MVP)
```
┌──────────────────────────────────────────────────────┐
│  Active Incidents                        [Live Feed] │
├──────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────┐      │
│  │ 🔴 CRITICAL | Response Time Spike (PG-01) │ 2m   │
│  │ Latency 45ms → 1200ms. High CPU node-04   │      │
│  └────────────────────────────────────────────┘      │
│  ┌────────────────────────────────────────────┐      │
│  │ 🟠 WARNING | Sequential Scan Detection    │ 14m  │
│  │ Schema: reporting | Table: legacy_logs     │      │
│  └────────────────────────────────────────────┘      │
│  ┌────────────────────────────────────────────┐      │
│  │ 🟠 WARNING | Replication Lag Exceeded      │ 45m  │
│  │ Node: replica-us-east-1 | Lag: 4.2s       │      │
│  └────────────────────────────────────────────┘      │
│  ┌────────────────────────────────────────────┐      │
│  │ 🟢 RESOLVED | Memory Pressure Analytics-02│ 2h   │
│  │ Auto-scaling triggered. New node added.    │      │
│  └────────────────────────────────────────────┘      │
├──────────────────────────────────────────────────────┤
│  Filter: [All] [Critical] [Warning] [Resolved]      │
└──────────────────────────────────────────────────────┘
```

#### 컴포넌트

| 컴포넌트 | 데이터 소스 | 실시간 |
|---------|-----------|--------|
| `IncidentList` | `GET /incidents` | WebSocket `incident:new` |
| `IncidentCard` | 인시던트 단건 | |
| `SeverityBadge` | severity prop | |
| `IncidentFilter` | 로컬 상태 (severity/status 필터) | |

#### 인시던트 카드 스타일

| Severity | 카드 스타일 | 뱃지 |
|----------|-----------|------|
| Critical | `bg-error-container/10 border-error/20` + 좌측 1px error 라인 | `bg-error text-on-error` |
| Warning | `bg-surface-container-high` | `bg-amber-500/20 text-amber-400` |
| Resolved | `bg-surface-container-high opacity-60` | `bg-tertiary/20 text-tertiary` |

---

### 4.4 Settings (MVP — 신규 화면)

**URL**: `/settings`

#### 서브 메뉴 구조
```
Settings
├── Instances        ← 인스턴스 목록 + 관리
│   ├── /new         ← Screen 6: Add Database Wizard
│   └── /:id        ← 인스턴스 상세/수정
├── Alerts           ← 알림 채널 (Slack/Webhook)
└── Users            ← 사용자 CRUD + RBAC
```

#### Instances 목록 (`/settings/instances`)
```
┌──────────────────────────────────────────────────────┐
│  DB Instances                    [+ Add Instance]    │
├──────────────────────────────────────────────────────┤
│  Name        | Type       | Host         | Status    │
│  pg-prod-01  | PostgreSQL | 10.0.1.100   | ✅ Active │
│  pg-prod-02  | PostgreSQL | 10.0.1.101   | ⚠️ Warn  │
│  pg-staging  | PostgreSQL | 10.0.2.50    | ✅ Active │
│                                                      │
│  [Edit] [Test Connection] [Delete]                   │
└──────────────────────────────────────────────────────┘
```

#### Add Database Wizard (`/settings/instances/new` — Screen 6)

**3단계 마법사** (좌측 스텝 인디케이터):

| Step | 제목 | 내용 |
|------|------|------|
| 1. TYPE | Database Architecture | PostgreSQL / MySQL / MS-SQL 카드 선택 |
| 2. CONNECTION | Network & Authentication | Host, Port, User, Password, SSL 토글 |
| 3. OPTIONS | Intelligence Configuration | ASH Explorer 활성화, Autonomous Tuning 활성화 |

**하단 액션**: Test Connection (좌) / Cancel / Save & Start Monitoring (우)

---

### 4.5 NL2SQL Chat (MVP — 플로팅 위젯)

**위치**: 화면 우하단 고정 (`fixed bottom-8 right-8 w-80 z-50`)
**토글**: SideNav의 "NL2SQL Assistant" 버튼

#### 구성
```
┌──────────────────────────────┐
│ 🤖 NL2SQL Assistant      [X]│ ← secondary-container 헤더
├──────────────────────────────┤
│                              │
│ User: "가장 느린 쿼리 5개"    │ ← surface-variant 말풍선
│                              │
│ AI: SELECT ... ORDER BY      │ ← secondary-container/10 말풍선
│     mean_exec_time DESC      │
│     LIMIT 5                  │
│                              │
│ [결과 테이블 표시]             │
│                              │
├──────────────────────────────┤
│ [Ask follow up...      ] [▶]│ ← 입력 + 전송 버튼
└──────────────────────────────┘
```

#### 인터랙션
- 질문 입력 → `POST /nl2sql/query` → SQL + 결과 표시
- 결과 클릭 → 테이블 확대 모달
- 코드 블록 → 클릭 시 클립보드 복사

---

### 4.6 System Health (MVP — 신규 간단 버전)

**URL**: `/system`

```
┌──────────────────────────────────────────────────────┐
│  System Health                              [✅ UP]  │
├──────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │ Database │ │  Valkey  │ │  Kafka   │ │ Celery │ │
│  │ ✅ 2.1ms │ │ ✅ 0.3ms │ │ ✅ lag:12│ │ ✅ 4/4 │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────┘ │
├──────────────────────────────────────────────────────┤
│  Uptime: 24h 12m | Version: 1.0.0                   │
└──────────────────────────────────────────────────────┘
```

**데이터**: `GET /api/v1/system/health`

---

## 5. 공유 컴포넌트 트리

```
components/
├── layout/
│   ├── TopNav.tsx               ← 글로벌 상단바
│   ├── SideNav.tsx              ← 글로벌 좌측 내비
│   ├── MainLayout.tsx           ← TopNav + SideNav + <Outlet />
│   └── PageHeader.tsx           ← 페이지 제목 + 우측 액션 버튼
│
├── common/
│   ├── Button.tsx               ← Primary / Secondary / Tertiary / Danger
│   ├── Badge.tsx                ← Critical / Warning / Resolved / Predictive / Active
│   ├── Card.tsx                 ← Summary / Glass / Alert / AI Insight / Data
│   ├── Input.tsx                ← Text / Password / Search
│   ├── Toggle.tsx               ← SSL, ASH 활성화 등
│   ├── Modal.tsx                ← Glassmorphism 모달
│   ├── ProgressBar.tsx          ← Glow 효과 포함
│   ├── Tooltip.tsx              ← 정보 표시
│   ├── EmptyState.tsx           ← "No data" 표시
│   ├── LoadingSkeleton.tsx      ← 로딩 스켈레톤
│   └── ErrorBoundary.tsx        ← 에러 폴백
│
├── dashboard/
│   ├── SummaryCard.tsx          ← 4개 요약 카드
│   ├── InstanceGrid.tsx         ← 인스턴스 카드 그리드
│   ├── InstanceCard.tsx         ← 개별 인스턴스 상태
│   ├── ResourceChart.tsx        ← ECharts 시계열 차트
│   └── AIInsightsFeed.tsx       ← AI 인사이트 피드
│
├── ash/
│   ├── TemporalZoom.tsx         ← 시간 해상도 선택
│   ├── ASHHeatmap.tsx           ← 4×24 히트맵 (ECharts)
│   ├── SessionTable.tsx         ← 세션 목록 테이블
│   ├── WaitBreakdown.tsx        ← Wait 유형 집계 바
│   └── AIInterpretation.tsx     ← 플로팅 AI 해석 카드
│
├── incidents/
│   ├── IncidentList.tsx         ← 인시던트 목록
│   ├── IncidentCard.tsx         ← 인시던트 카드
│   ├── IncidentFilter.tsx       ← severity/status 필터
│   └── SeverityBadge.tsx        ← 심각도 뱃지
│
├── nl2sql/
│   ├── NL2SQLChat.tsx           ← 플로팅 챗 위젯
│   ├── ChatMessage.tsx          ← 사용자/AI 메시지 말풍선
│   └── SQLResultTable.tsx       ← 쿼리 결과 테이블
│
└── settings/
    ├── InstanceList.tsx         ← 인스턴스 관리 테이블
    ├── AddDatabaseWizard.tsx    ← 3단계 등록 마법사
    ├── AlertChannelForm.tsx     ← 알림 채널 설정
    └── UserManagement.tsx       ← 사용자 CRUD + 역할 선택
```

---

## 6. 실시간 데이터 흐름

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐
│ FastAPI   │────▶│ python-      │────▶│ React        │
│ Backend   │     │ socketio     │     │ Frontend     │
└──────────┘     └──────────────┘     └──────────────┘
                                            │
                                    ┌───────┴───────┐
                                    │               │
                              /ws/metrics     /ws/incidents
                                    │               │
                              Dashboard       IncidentList
                              MetricChart     SideNav 뱃지
                              ASHHeatmap
```

| 이벤트 | 발생 빈도 | 소비 컴포넌트 | 데이터 크기 |
|--------|----------|-------------|-----------|
| `metric:update` | 1초 | ResourceChart, SummaryCard, InstanceCard | ~200 bytes |
| `incident:new` | 이벤트 시 | IncidentList, TopNav 알림 뱃지 | ~500 bytes |
| `incident:update` | 이벤트 시 | IncidentList, IncidentCard | ~300 bytes |

---

## 7. 사용자 플로우

### Flow 1: 첫 사용 (온보딩)

```
로그인 → Dashboard (인스턴스 없음 — EmptyState)
  → "Add Your First Database" CTA 클릭
  → /settings/instances/new (Screen 6)
  → Step 1: PostgreSQL 선택
  → Step 2: Host/Port/User/Password 입력
  → "Test Connection" 클릭 → ✅ 성공
  → Step 3: ASH Explorer 활성화 ✅
  → "Save & Start Monitoring" 클릭
  → Dashboard (인스턴스 1개 표시, 메트릭 수집 시작)
```

### Flow 2: 이상 탐지 → 조사

```
Dashboard (CPU 카드 빨간색 강조)
  → 해당 InstanceCard 클릭
  → /ash/{instanceId}
  → ASH Heatmap에서 Lock 행 빨간색 확인
  → 해당 셀 클릭 → SessionTable 필터링
  → Lock 상태 세션의 "Explain" 클릭
  → AI Interpretation: "Lock contention on orders table"
  → SQL 추천 확인 → 클립보드 복사 → DBA에게 전달
```

### Flow 3: Slack 알림 → 대시보드

```
Slack 알림 수신: "🔴 CRITICAL | pg-prod-01 CPU 95%"
  → [상세보기] 버튼 클릭 → /incidents (웹 브라우저)
  → 해당 인시던트 카드 확인
  → 인스턴스 이름 클릭 → /ash/{instanceId}
  → 원인 조사
```

### Flow 4: NL2SQL 질의

```
아무 화면에서 SideNav "NL2SQL Assistant" 클릭
  → 플로팅 챗 열림
  → "오늘 가장 느린 쿼리 TOP 5" 입력
  → AI: SQL 생성 + 실행 결과 테이블 표시
  → 결과 행 클릭 → 쿼리 상세 (Phase 2에서 EXPLAIN 해석 연동)
```

---

## 8. 상태 관리 (Zustand + TanStack Query)

| 상태 유형 | 관리 방식 | 예시 |
|-----------|----------|------|
| **서버 상태** | TanStack Query | 인스턴스 목록, 메트릭, 인시던트 |
| **실시간 상태** | Zustand + WebSocket | 최신 메트릭, 인시던트 카운트 |
| **UI 상태** | Zustand | NL2SQL 챗 열림/닫힘, 선택된 인스턴스 |
| **폼 상태** | React Hook Form | Add Database Wizard |
| **URL 상태** | TanStack Router | 현재 페이지, 필터 파라미터 |

### Zustand Store 설계

```typescript
// stores/
├── metricStore.ts        // 실시간 메트릭 (WebSocket 수신)
├── incidentStore.ts      // 선택된 인시던트, 필터 상태
├── instanceStore.ts      // 선택된 인스턴스 ID
├── nl2sqlStore.ts        // 챗 열림/닫힘, 메시지 히스토리
└── authStore.ts          // 현재 사용자, 역할, JWT
```

---

## 9. Phase별 UI 로드맵

### MVP (Month 1~3)

| Week | UI 작업 |
|------|--------|
| W1 | 프로젝트 초기화, Tailwind 디자인 토큰 설정, MainLayout |
| W2 | TopNav, SideNav, 라우팅 설정, 로그인 페이지 |
| W3 | Dashboard: SummaryCard, InstanceGrid, InstanceCard |
| W4 | Dashboard: ResourceChart(ECharts) + WebSocket 연동 |
| W5 | ASH Explorer: TemporalZoom, ASHHeatmap |
| W6 | ASH Explorer: SessionTable, WaitBreakdown, AIInterpretation |
| W7 | Incidents: IncidentList, IncidentCard, SeverityBadge |
| W8 | Settings: InstanceList, AddDatabaseWizard (Screen 6) |
| W9 | Settings: AlertChannelForm, UserManagement |
| W10 | NL2SQL Chat, System Health, 디자인 폴리싱 |
| W11 | 통합 테스트, 반응형 조정, 접근성 |
| W12 | 버그 수정, 최종 QA |

### Phase 2 (Month 4~6)

| 기능 | 화면 |
|------|------|
| AI RCA Panel | Screen 4 우측 확장 (Glass 카드 + 인과 체인) |
| Playbook Editor | Screen 2 (코드 에디터 + 감사 로그 타임라인) |
| Self-Healing Dashboard | Screen 2 (Remediation Queue + 프로그레스) |
| Schema Change Timeline | Dashboard에 오버레이 마커 추가 |
| AIGC Report | 리포트 생성 + PDF/HTML 미리보기 |

### Phase 3 (Month 7~9)

| 기능 | 화면 |
|------|------|
| Full Topology Explorer | Screen 5 (ECharts Graph + Node Inspector) |
| Drift Detection | 토폴로지 맵에 알림 바 |
| Blast Radius Analysis | Node Inspector 패널 |

---

## 10. 미설계 화면 (MVP 중 신규 작성 필요)

| 화면 | 우선도 | 비고 |
|------|--------|------|
| **Login** | P0 | 간단한 Email + Password 폼. 디자인 토큰 적용 |
| **Settings 메인** | P0 | 3개 서브메뉴 카드 (Instances / Alerts / Users) |
| **Alert Channel Form** | P0 | Slack Webhook URL + Test 버튼 |
| **User Management** | P0 | 사용자 테이블 + Role 드롭다운 |
| **System Health** | P1 | 4개 컴포넌트 상태 카드 (간단) |
| **404 / Error** | P1 | 에러 페이지 |
| **Empty State** | P1 | "No instances registered" 등 |

> 이 화면들은 Stitch에 디자인이 없으므로, FRONTEND_DESIGN.md의 디자인 토큰과 컴포넌트 패턴을 따라 구현합니다.

---

## 11. 로그인 화면

**URL**: `/login`
**인증 전 유일하게 접근 가능한 페이지**. 나머지 모든 경로는 JWT 미보유 시 `/login`으로 리다이렉트.

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│                    ┌───────────────────┐                │
│                    │    NeuralDB       │                │
│                    │    ⚡ 로고          │                │
│                    │                   │                │
│                    │  Email            │                │
│                    │  [_______________]│                │
│                    │                   │                │
│                    │  Password         │                │
│                    │  [_______________]│                │
│                    │                   │                │
│                    │  [  Sign In     ] │                │
│                    │                   │                │
│                    │  SSO로 로그인 →    │ (Phase 2)      │
│                    └───────────────────┘                │
│                                                         │
│       bg: surface (#0b1326) + neural-grid 패턴           │
│       중앙 카드: glass-panel (blur-24 + border-white/5)  │
└─────────────────────────────────────────────────────────┘
```

**에러 상태**:
- 인증 실패: 카드 상단에 `bg-error/10 text-error` 배너 — "Invalid email or password"
- 네트워크 오류: `bg-amber-500/10 text-amber-400` 배너 — "Server unreachable"

---

## 12. RBAC 기반 UI 접근 제어

### 역할별 화면 접근

| 화면 / 기능 | Super Admin | DB Admin | Operator | Viewer | API User |
|------------|:-----------:|:--------:|:--------:|:------:|:--------:|
| Dashboard (조회) | ✅ | ✅ | ✅ | ✅ | - |
| ASH Explorer (조회) | ✅ | ✅ | ✅ | ✅ | - |
| Incidents (조회) | ✅ | ✅ | ✅ | ✅ | - |
| Incidents (상태 변경) | ✅ | ✅ | ✅ | ❌ | - |
| NL2SQL (질의) | ✅ | ✅ | ✅ | ✅ | - |
| Settings (인스턴스 조회) | ✅ | ✅ | ✅ | ✅ | - |
| Settings (인스턴스 CUD) | ✅ | ✅ | ❌ | ❌ | - |
| Settings (인스턴스 삭제) | ✅ | ❌ | ❌ | ❌ | - |
| Settings (알림 채널) | ✅ | ✅ | ❌ | ❌ | - |
| Settings (사용자 관리) | ✅ | ❌ | ❌ | ❌ | - |
| System Health | ✅ | ✅ | ✅ | ✅ | - |
| Autonomy Level 변경 | ✅ | ✅ | ❌ | ❌ | - |

### UI 처리 방식

| 권한 없는 경우 | 처리 |
|-------------|------|
| **메뉴/탭** | 표시하되 `opacity-40 cursor-not-allowed` + 클릭 시 "권한이 부족합니다" 토스트 |
| **버튼** (생성/수정/삭제) | `disabled` + 툴팁 "DB Admin 이상 권한이 필요합니다" |
| **페이지** (직접 URL 접근) | 403 페이지 표시 또는 `/dashboard`로 리다이렉트 |

### 구현 패턴
```typescript
// hooks/usePermission.ts
export function usePermission(action: string, resource: string): boolean {
  const { role } = useAuthStore();
  return checkPermission(role, action, resource);
}

// 사용 예시
const canCreateInstance = usePermission('create', 'instance');
<Button disabled={!canCreateInstance}>+ Add Instance</Button>
```

---

## 13. 로딩 / 에러 / 빈 상태 UI

### 13.1 로딩 상태 (Skeleton)

모든 데이터 영역은 로딩 시 **Skeleton Placeholder**를 표시합니다.

```
┌──────────────────────────┐
│  ████████                │  ← 제목 스켈레톤
│  ██████████████████      │  ← 텍스트 스켈레톤
│                          │
│  ┌─────┐ ┌─────┐ ┌─────┐│  ← 카드 스켈레톤
│  │░░░░░│ │░░░░░│ │░░░░░││
│  │░░░░░│ │░░░░░│ │░░░░░││
│  └─────┘ └─────┘ └─────┘│
└──────────────────────────┘
```

**스타일**: `bg-surface-container-high animate-pulse rounded`
**규칙**: 실제 콘텐츠와 동일한 크기/레이아웃의 스켈레톤 사용 (CLS 방지)

### 13.2 에러 상태

| 유형 | UI | 동작 |
|------|-----|------|
| **API 에러 (4xx/5xx)** | 해당 섹션에 에러 카드 표시 | "Retry" 버튼 포함 |
| **네트워크 끊김** | TopNav에 `bg-error` 배너 "Connection Lost" | 자동 재연결 시도 |
| **WebSocket 끊김** | 차트 위에 "Real-time paused" 오버레이 | 자동 재연결 시 제거 |
| **404** | 전체 페이지 에러 | "Go to Dashboard" 버튼 |
| **500 (Unhandled)** | `ErrorBoundary` 폴백 | "Reload" 버튼 |

**에러 카드 스타일**:
```
bg-error-container/10 border border-error/20 rounded-xl p-6
  icon: error_outline (error 색상)
  title: "Failed to load metrics"
  description: "Please try again or contact support"
  action: [Retry] 버튼
```

### 13.3 빈 상태 (Empty State)

| 상황 | 메시지 | CTA |
|------|--------|-----|
| 인스턴스 없음 (최초) | "No databases monitored yet" | [Add Your First Database] |
| 인시던트 없음 | "All clear! No active incidents" | (CTA 없음) |
| ASH 데이터 없음 | "No session data for this time range" | [Adjust Time Range] |
| NL2SQL 히스토리 없음 | "Ask your first question" | (입력 필드 포커스) |
| 검색 결과 없음 | "No results for '{query}'" | [Clear Search] |

**빈 상태 스타일**:
```
flex flex-col items-center justify-center py-20
  icon: inbox (outline 색상, 48px)
  title: text-lg font-headline text-on-surface
  description: text-sm text-on-surface-variant
  CTA: Button (primary)
```

---

## 14. 토스트 알림 & 인앱 알림

### 14.1 토스트 (일시적 알림)

화면 우상단에 표시. 5초 후 자동 사라짐. 최대 3개 스택.

| 유형 | 스타일 | 예시 |
|------|--------|------|
| Success | `bg-tertiary/10 border-tertiary/20 text-tertiary` | "Instance pg-prod-01 created" |
| Error | `bg-error/10 border-error/20 text-error` | "Failed to connect to database" |
| Warning | `bg-amber-500/10 border-amber-500/20 text-amber-400` | "Connection test timed out" |
| Info | `bg-primary/10 border-primary/20 text-primary` | "Baseline training started" |

```
┌──────────────────────────────┐
│ ✅ Instance pg-prod-01 saved │ [X]
└──────────────────────────────┘
```

**위치**: `fixed top-20 right-8 z-[60]` (TopNav 아래)
**애니메이션**: `slide-in-right` → 5초 → `fade-out` (ease-out)

### 14.2 인앱 알림 (TopNav 벨 아이콘)

```
[🔔 3]  ← 미확인 인시던트 수 (빨간 뱃지)

클릭 시 드롭다운:
┌──────────────────────────────────┐
│ Notifications                    │
├──────────────────────────────────┤
│ 🔴 CPU Spike pg-prod-01    2m   │
│ 🟠 Replication Lag          14m  │
│ 🟢 Memory Pressure resolved 2h  │
├──────────────────────────────────┤
│ [View All Incidents →]           │
└──────────────────────────────────┘
```

**데이터**: WebSocket `incident:new` → Zustand `notificationStore` → 뱃지 카운트

---

## 15. 알림 채널 설정 화면

**URL**: `/settings/alerts`

```
┌──────────────────────────────────────────────────────┐
│  Alert Channels                    [+ Add Channel]   │
├──────────────────────────────────────────────────────┤
│                                                      │
│  ┌────────────────────────────────────────────┐      │
│  │ 🔗 Slack - #db-alerts                      │      │
│  │ Webhook: https://hooks.slack.com/...       │      │
│  │ Severity: Critical, Warning                │      │
│  │ Status: ✅ Active        [Test] [Edit] [🗑] │      │
│  └────────────────────────────────────────────┘      │
│                                                      │
│  ┌────────────────────────────────────────────┐      │
│  │ 🌐 Webhook - PagerDuty                     │      │
│  │ URL: https://events.pagerduty.com/...      │      │
│  │ Severity: Critical only                    │      │
│  │ Status: ✅ Active        [Test] [Edit] [🗑] │      │
│  └────────────────────────────────────────────┘      │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### Add/Edit Channel 모달

```
┌──────────────────────────────────────┐
│  Add Alert Channel                   │
├──────────────────────────────────────┤
│  Type:  [Slack ▼]                    │
│                                      │
│  Channel Name:                       │
│  [#db-alerts________________]        │
│                                      │
│  Webhook URL:                        │
│  [https://hooks.slack.com/___]       │
│                                      │
│  Severity Filter:                    │
│  [✅ Critical] [✅ Warning]           │
│  [☐ Notice]   [☐ Info]              │
│                                      │
│  [Test Notification]   [Cancel] [Save]│
└──────────────────────────────────────┘
```

---

## 16. 사용자 관리 화면

**URL**: `/settings/users`
**접근 권한**: Super Admin only

```
┌──────────────────────────────────────────────────────┐
│  Users                                 [+ Add User]  │
├──────────────────────────────────────────────────────┤
│  Name       | Email              | Role        | Act │
│  Kim Admin  | admin@company.com  | Super Admin | ✅  │
│  Lee DBA    | lee@company.com    | DB Admin    | ✅  │
│  Park Op    | park@company.com   | Operator    | ✅  │
│  Choi View  | choi@company.com   | Viewer      | ✅  │
│                                       [Edit] [🗑]    │
└──────────────────────────────────────────────────────┘
```

### Add/Edit User 모달

```
┌──────────────────────────────────────┐
│  Add User                            │
├──────────────────────────────────────┤
│  Name:     [__________________]      │
│  Email:    [__________________]      │
│  Password: [__________________]      │
│                                      │
│  Role:     [DB Admin ▼]             │
│    ┌─────────────────┐               │
│    │ Super Admin      │               │
│    │ DB Admin    ✓    │               │
│    │ Operator         │               │
│    │ Viewer           │               │
│    │ API User         │               │
│    └─────────────────┘               │
│                                      │
│  [Cancel]  [Save]                    │
└──────────────────────────────────────┘
```

**역할 설명 툴팁**: 드롭다운 옆에 `help` 아이콘 → 각 역할의 권한 요약 표시

---

## 17. 반응형 디자인 상세

### 브레이크포인트

| Breakpoint | Width | 레이아웃 변경 |
|-----------|-------|-------------|
| `sm` | 640px | 모바일: SideNav 숨김 → 햄버거 메뉴 |
| `md` | 768px | 태블릿: Summary 카드 2열, TopNav 탭 표시 |
| `lg` | 1024px | 데스크톱: 2컬럼 레이아웃 (ASH 좌/우 분할) |
| `xl` | 1280px | 와이드: 전체 디자인 적용 |
| `2xl` | 1536px | 초와이드: 콘텐츠 max-width 제한 |

### SideNav 반응형

| 화면 | 동작 |
|------|------|
| `lg+` | SideNav 항상 표시 (w-64) |
| `md` | SideNav 접힘 (아이콘만, w-16) + hover 시 확장 |
| `sm` | SideNav 숨김 → TopNav 좌측 햄버거 아이콘 → 오버레이 SideNav |

### 콘텐츠 적응

| 컴포넌트 | `sm` | `md` | `lg+` |
|---------|------|------|-------|
| Summary Cards | 1열 스택 | 2×2 그리드 | 4열 그리드 |
| Instance Grid | 1열 리스트 | 2열 그리드 | 3~4열 그리드 |
| ASH 히트맵+사이드바 | 스택 (히트맵 → 사이드바) | 스택 | 좌우 분할 |
| Incidents | 카드 스택 | 카드 스택 | 카드 스택 |
| NL2SQL Chat | 전체 화면 (모바일 최적화) | 플로팅 w-80 | 플로팅 w-80 |

---

## 18. 접근성 (Accessibility) 기준

### WCAG 2.1 Level AA 준수

| 항목 | 기준 | 구현 |
|------|------|------|
| **색상 대비** | 4.5:1 이상 (텍스트) | 디자인 토큰이 이미 충족 (`on-surface` #dae2fd on `surface` #0b1326 = 12.8:1) |
| **키보드 내비** | 모든 인터랙션 키보드 접근 | `Tab` 순서, `Enter`/`Space` 활성화, `Esc` 닫기 |
| **포커스 표시** | 포커스 가시성 | `focus-visible:ring-2 ring-primary ring-offset-2 ring-offset-surface` |
| **스크린 리더** | 의미 있는 ARIA 라벨 | `aria-label`, `role`, `aria-live` (실시간 영역) |
| **동작 제어** | 깜빡임/자동재생 제어 | 차트 애니메이션 끄기 옵션 (`prefers-reduced-motion` 반영) |

### 실시간 영역 접근성
```html
<!-- 인시던트 실시간 피드 -->
<div role="log" aria-live="polite" aria-label="Active incidents feed">
  ...
</div>

<!-- 메트릭 실시간 값 -->
<span role="status" aria-live="off" aria-label="CPU usage: 45.2%">45.2%</span>
```

---

## 19. 키보드 단축키

| 단축키 | 동작 | 범위 |
|--------|------|------|
| `G` then `D` | Dashboard 이동 | 글로벌 |
| `G` then `A` | ASH Explorer 이동 | 글로벌 |
| `G` then `I` | Incidents 이동 | 글로벌 |
| `G` then `S` | Settings 이동 | 글로벌 |
| `/` | 글로벌 검색 포커스 | 글로벌 |
| `N` | NL2SQL 챗 토글 | 글로벌 |
| `Esc` | 모달/챗/드롭다운 닫기 | 컨텍스트 |
| `?` | 단축키 도움말 모달 | 글로벌 |

**구현**: 입력 필드 포커스 시 단축키 비활성화 (`event.target.tagName !== 'INPUT'`)

---

## 20. 다국어 (i18n) 전략

### MVP: 한국어 + 영어 (2개 언어)

| 항목 | 전략 |
|------|------|
| **라이브러리** | `react-i18next` (MIT) |
| **번역 파일** | `frontend/src/locales/{ko,en}/common.json` |
| **기본 언어** | 한국어 (ko) |
| **전환 방식** | Settings → Language 드롭다운 또는 TopNav 아이콘 |
| **번역 범위** | UI 라벨, 버튼, 에러 메시지. **메트릭명/SQL/기술 용어는 번역 안함** |

### 번역하지 않는 것
- 메트릭 이름: `cpu_usage`, `tps`, `replication_lag`
- SQL 키워드: `SELECT`, `WHERE`
- DB 객체명: 테이블/인덱스 이름
- 에이전트 ID: `agent-monitoring`
- 로그 내용: 서버에서 오는 원본 유지

---

## 21. 데이터 페칭 & 캐싱 전략

### TanStack Query 설정

| 데이터 | `staleTime` | `gcTime` | `refetchInterval` | 이유 |
|--------|------------|---------|-------------------|------|
| 인스턴스 목록 | 30초 | 5분 | - | 자주 변경되지 않음 |
| 메트릭 (REST) | 0 | 1분 | - | WebSocket이 실시간 담당 |
| 인시던트 목록 | 10초 | 5분 | 30초 | WebSocket + 폴링 병행 |
| ASH 히트맵 | 0 | 30초 | - | 시간 범위 변경 시 새 요청 |
| 베이스라인 | 5분 | 30분 | - | 6시간마다 갱신 |
| 사용자 목록 | 1분 | 10분 | - | 관리자만 접근 |
| System Health | 10초 | 1분 | 15초 | 주기적 폴링 |

### WebSocket vs REST 역할 분리

| 데이터 | 초기 로드 | 실시간 갱신 |
|--------|----------|-----------|
| 메트릭 차트 | REST (과거 데이터) | WebSocket (1초 스트리밍) |
| 인시던트 | REST (목록) | WebSocket (신규/변경) |
| ASH 히트맵 | REST (히트맵 데이터) | WebSocket (선택적) |
| Summary Cards | REST (집계) | WebSocket (값 업데이트) |

**패턴**: REST로 초기 데이터 로드 → WebSocket으로 증분 업데이트 → Zustand Store에서 병합

```typescript
// 초기 로드
const { data: metrics } = useQuery({ queryKey: ['metrics', id], ... });

// 실시간 업데이트
useMetricSocket(id, (update) => {
  queryClient.setQueryData(['metrics', id], (old) => mergeMetric(old, update));
});
```

---

## 22. 확인 다이얼로그 & 위험 작업 보호

### 확인이 필요한 액션

| 액션 | 확인 유형 | 메시지 |
|------|----------|--------|
| 인스턴스 삭제 | **이름 입력 확인** | "삭제하려면 인스턴스 이름 'pg-prod-01'을 입력하세요" |
| 사용자 삭제 | 확인 다이얼로그 | "이 사용자를 삭제하시겠습니까?" |
| 알림 채널 삭제 | 확인 다이얼로그 | "이 알림 채널을 삭제하시겠습니까?" |
| Autonomy Level 변경 | 확인 다이얼로그 | "자율 등급을 Level 3으로 변경하시겠습니까?" |
| 인시던트 일괄 닫기 | 확인 다이얼로그 | "선택한 5건의 인시던트를 닫으시겠습니까?" |

### 삭제 확인 모달 (위험)
```
┌──────────────────────────────────────┐
│  ⚠️ Delete Instance                  │
├──────────────────────────────────────┤
│                                      │
│  This will permanently remove        │
│  pg-prod-01 and all its monitoring   │
│  data. This action cannot be undone. │
│                                      │
│  Type "pg-prod-01" to confirm:       │
│  [__________________________]        │
│                                      │
│  [Cancel]  [Delete] (disabled until  │
│                      name matches)   │
└──────────────────────────────────────┘
```

**Delete 버튼 스타일**: `bg-error text-on-error` (이름 일치 전 `disabled opacity-40`)

---

---

## 23. 폼 검증 규칙

### 23.1 Add Database Wizard (Screen 6)

| Step | 필드 | 검증 규칙 | 에러 메시지 |
|------|------|----------|-----------|
| 1 | DB Type | 필수 선택 | "데이터베이스 유형을 선택하세요" |
| 2 | Host Address | 필수, IP 또는 FQDN 형식 | "유효한 호스트 주소를 입력하세요" |
| 2 | Port | 필수, 숫자, 1~65535 | "1~65535 범위의 포트를 입력하세요" |
| 2 | Database User | 필수, 1~63자, 특수문자 제한 | "데이터베이스 사용자명을 입력하세요" |
| 2 | Password | 필수, 1~255자 | "비밀번호를 입력하세요" |
| 2 | SSL Toggle | 선택 (기본 OFF) | - |
| 3 | ASH Explorer | 선택 체크박스 | - |
| 3 | Autonomous Tuning | 선택 체크박스 | - |

**Step 간 이동 규칙**:
- Step 1 완료 전 Step 2 진입 불가
- Step 2 필수 필드 미입력 시 Step 3 진입 불가
- Step 간 뒤로가기(Back)는 항상 허용

**Test Connection 버튼 상태**:
```
[비활성] Host/Port/User/Password 미입력 시 → disabled opacity-40
[로딩]   클릭 후 연결 시도 중 → spinner + "Connecting..." 텍스트
[성공]   연결 성공 → tertiary 체크 아이콘 + "Connection successful" (3초 후 리셋)
[실패]   연결 실패 → error 아이콘 + "Connection failed: {reason}" (인라인, 필드 하단)
```

### 23.2 Alert Channel Form

| 필드 | 검증 규칙 | 에러 메시지 |
|------|----------|-----------|
| Channel Type | 필수 선택 (Slack/Email/Webhook) | "채널 유형을 선택하세요" |
| Channel Name | 필수, 1~100자 | "채널 이름을 입력하세요" |
| Webhook URL | 필수 (Slack/Webhook), URL 형식 | "유효한 URL을 입력하세요" |
| SMTP Host | 필수 (Email), FQDN 형식 | "SMTP 서버 주소를 입력하세요" |
| Severity Filter | 최소 1개 선택 | "최소 1개 심각도를 선택하세요" |

### 23.3 User Management Form

| 필드 | 검증 규칙 | 에러 메시지 |
|------|----------|-----------|
| Name | 필수, 2~100자 | "이름을 입력하세요" |
| Email | 필수, 이메일 형식, 중복 불가 | "유효한 이메일을 입력하세요" / "이미 등록된 이메일입니다" |
| Password | 필수 (생성 시), 8자 이상, 영문+숫자+특수문자 | "8자 이상, 영문/숫자/특수문자를 포함하세요" |
| Role | 필수 선택 | "역할을 선택하세요" |

### 23.4 검증 표시 규칙

```
타이밍:     필드 blur 시 검증 (실시간 타이핑 중에는 비검증)
에러 위치:  필드 바로 아래 (인라인)
에러 스타일: text-error text-xs mt-1 + 필드 border → border-error
에러 아이콘: error_outline (필드 우측 내부)
복수 에러:  첫 번째 에러만 표시
비동기 검증: 이메일 중복 → 디바운스 500ms 후 서버 검증
```

**미저장 이탈 경고**:
```
사용자가 폼 수정 후 페이지 이동 시:
→ "저장하지 않은 변경사항이 있습니다. 이동하시겠습니까?" 확인 다이얼로그
→ [취소] / [이동]
```

---

## 24. 차트/시각화 상세 규격

### 24.1 메트릭 시계열 차트 (Dashboard ResourceChart)

| 항목 | 사양 |
|------|------|
| 라이브러리 | Apache ECharts |
| 차트 유형 | Line + Area (CPU), Line (TPS), Bar (Connections) |
| X축 | 시간 — 포맷: `HH:mm:ss` (1초 뷰), `HH:mm` (1시간 뷰), `MM/DD HH:mm` (1일 뷰) |
| Y축 | 메트릭값 — 동적 범위 (min~max * 1.1) |
| 업데이트 | WebSocket `metric:update` → 1초마다 새 포인트 추가, 좌측 포인트 제거 (슬라이딩 윈도우) |
| 애니메이션 | `animationDuration: 300`, `animationEasing: 'cubicOut'` |
| 툴팁 | hover 시 표시: `{ time: "14:32:05", cpu: "45.2%", tps: "1,240" }` |
| 범례 | 차트 상단 우측, 클릭 시 해당 시리즈 토글 |
| 기준선 | AI 베이스라인 — `#d0bcff` 점선 (stroke-dasharray: 4 4) |
| 임계값 | 수동 임계값 — `#ffb4ab` 수평선 (반투명 배경 영역) |
| 줌 | 마우스 드래그로 영역 선택 → X축 줌. 더블클릭으로 리셋 |
| 색상 | CPU: `#89ceff`, Memory: `#d0bcff`, TPS: `#4edea3`, Connections: `#f59e0b` |

### 24.2 ASH 히트맵 (Screen 3)

| 항목 | 사양 |
|------|------|
| 그리드 | 4행(Network, I/O, Lock, CPU) × 24열(시간 구간) |
| 셀 크기 | `flex-1` 너비, `h-48 / 4 = h-12` 높이 |
| 색상 스케일 | 강도 기반 (양자화 5단계) |
| 범주별 색상 | |
| - Idle | `surface-variant` (#2d3449) |
| - I/O (Low~High) | `sky-900` → `sky-700` → `sky-500` |
| - Lock (Low~High) | `orange-900` → `orange-500` → `error` (#ffb4ab) |
| - CPU (Low~High) | `secondary-container` (20%~100% opacity) |
| - Network | `sky-900` (드문 활동) |
| 셀 hover | `transform: scale(1.1)`, `z-index: 10`, 200ms ease-out |
| 셀 클릭 | 해당 시간 구간의 세션 테이블 필터링 |
| 툴팁 | `{ time: "14:32:05", category: "Lock", count: 14, top_event: "transactionid" }` |
| 시간 라벨 | 하단: `HH:mm:ss` 형식, 5개 등간격 표시 |

### 24.3 Wait Breakdown 바 차트 (Screen 3 우측)

| 항목 | 사양 |
|------|------|
| 바 높이 | `h-2`, `rounded-full` |
| Lock | `bg-orange-500`, glow: `shadow-[0_0_8px_rgba(249,115,22,0.4)]` |
| Disk I/O | `bg-sky-500`, glow: `shadow-[0_0_8px_rgba(14,165,233,0.4)]` |
| CPU | `bg-secondary` (#d0bcff), glow: `shadow-[0_0_8px_rgba(208,188,255,0.4)]` |
| 퍼센트 라벨 | 바 우측, `text-xs font-bold text-slate-100` |
| 애니메이션 | 바 너비 0% → N% 전환, 500ms ease-out |

### 24.4 숫자 포맷 규칙

| 메트릭 | 포맷 | 예시 |
|--------|------|------|
| CPU/Memory (%) | 소수점 1자리 | `45.2%` |
| TPS | 천 단위 콤마, 정수 | `1,240` |
| 응답시간 (ms) | 정수 (≤999ms), 소수 1자리+s (≥1s) | `12ms`, `1.2s` |
| 커넥션 수 | 정수 | `42` |
| Replication Lag | 소수 1자리+s | `4.2s` |
| 디스크 용량 | 자동 단위 (KB/MB/GB/TB) | `12.8 GB` |
| 시간 경과 | 상대 시간 | `2m ago`, `14m ago`, `2h ago` |
| 타임스탬프 | `YYYY-MM-DD HH:mm:ss` (절대) | `2026-03-21 14:32:05` |

---

## 25. 트랜지션 & 애니메이션 규격

### 25.1 기본 규칙

| 항목 | 값 |
|------|-----|
| Easing | `ease-out` 전용 (탄성/바운스 금지) |
| Short (hover, 포커스) | `150ms` |
| Medium (토글, 확장) | `200ms` |
| Long (모달, 페이지) | `300ms` |
| `prefers-reduced-motion` | `@media (prefers-reduced-motion: reduce)` → 모든 애니메이션 `duration: 0ms` |

### 25.2 컴포넌트별 애니메이션

| 컴포넌트 | 트리거 | 애니메이션 | 시간 |
|---------|--------|----------|------|
| **Button** hover | mouseenter | `brightness-110` | 150ms |
| **Button** click | mousedown | `scale-95` | 100ms |
| **Card** hover | mouseenter | `bg-surface-container-high → bg-surface-bright` | 200ms |
| **Modal** open | state change | `opacity 0→1` + `scale 0.95→1` | 300ms |
| **Modal** close | state change | `opacity 1→0` + `scale 1→0.95` | 200ms |
| **Toast** enter | 생성 시 | `translateX(100%) → 0` | 300ms |
| **Toast** exit | 5초 후 | `opacity 1→0` | 200ms |
| **Dropdown** open | click | `opacity 0→1` + `translateY(-4px) → 0` | 200ms |
| **SideNav** collapse | breakpoint md | `width 256px → 64px` | 300ms |
| **SideNav** overlay | breakpoint sm | `translateX(-100%) → 0` + backdrop fade | 300ms |
| **Skeleton** pulse | 반복 | `opacity 0.4 → 1 → 0.4` | 1500ms infinite |
| **히트맵 셀** hover | mouseenter | `scale(1.1)` | 200ms |
| **테이블 행** 삽입 | WebSocket | `opacity 0→1` + `bg-primary/10 → transparent` | 500ms |
| **테이블 행** "Explain" 버튼 | row hover | `opacity 0→1` | 150ms |
| **차트 데이터** 업데이트 | WebSocket | 포인트 이동 `cubicOut` | 300ms |
| **프로그레스 바** fill | 값 변경 | `width 0% → N%` | 500ms |
| **알림 뱃지** 카운트 변경 | WebSocket | `scale(1.2) → 1` (펄스 1회) | 300ms |

### 25.3 페이지 전환

```
Route Change: 콘텐츠 영역만 전환 (TopNav/SideNav 유지)
  → 기존 페이지: opacity 1 → 0 (150ms)
  → 새 페이지:   opacity 0 → 1 (150ms)
  → 총 전환 시간: 300ms
  → SideNav 활성 항목: 즉시 변경 (애니메이션 없음)
```

---

## 26. 인터랙션 상태 매트릭스

### 26.1 Button 상태

| State | Visual | Cursor | 접근성 |
|-------|--------|--------|--------|
| **Default** | 해당 variant 색상 | `pointer` | - |
| **Hover** | `brightness-110` | `pointer` | - |
| **Active** (mousedown) | `scale-95` | `pointer` | - |
| **Focus** (keyboard) | `ring-2 ring-primary ring-offset-2 ring-offset-surface` | - | `focus-visible` |
| **Disabled** | `opacity-40` | `not-allowed` | `aria-disabled="true"` |
| **Loading** | spinner + 텍스트 교체 | `wait` | `aria-busy="true"` |

### 26.2 Input 상태

| State | Visual | 접근성 |
|-------|--------|--------|
| **Default** | `bg-surface-container-lowest border-outline-variant/15` | - |
| **Hover** | `border-outline` | - |
| **Focus** | `border-primary ring-2 ring-primary/20` | - |
| **Error** | `border-error` + 하단 에러 메시지 | `aria-invalid="true" aria-describedby="error-{id}"` |
| **Disabled** | `opacity-40 bg-surface-container` | `aria-disabled="true"` |
| **Readonly** | `bg-surface-container cursor-default` | `aria-readonly="true"` |

### 26.3 SideNav Item 상태

| State | Visual | 접근성 |
|-------|--------|--------|
| **Default** | `text-slate-400` | - |
| **Hover** | `bg-[#222a3d] text-slate-100` | - |
| **Active** (현재 페이지) | `bg-[#222a3d] text-sky-400 border-r-4 border-sky-500 translate-x-1` | `aria-current="page"` |
| **Disabled** (Phase 2+) | `opacity-40 cursor-not-allowed` | `aria-disabled="true"`, title="Coming Soon" |
| **Focus** (keyboard) | `ring-2 ring-primary ring-inset` | `focus-visible` |

### 26.4 Card 상태

| State | Visual |
|-------|--------|
| **Default** | 해당 variant 배경 |
| **Hover** | `bg-surface-container-high → bg-surface-bright` (200ms ease-out) |
| **Selected** (인스턴스 선택) | `ring-2 ring-primary` |
| **Error** (수집 실패) | `border-error/30 opacity-60` + 에러 아이콘 오버레이 |

### 26.5 Table Row 상태

| State | Visual |
|-------|--------|
| **Default** | 투명 배경 |
| **Hover** | `bg-white/5` |
| **Selected** | `bg-primary/5` |
| **New** (WebSocket 삽입) | `bg-primary/10` → 500ms → 투명 (하이라이트 페이드) |

---

## 27. Stitch 화면 미반영 요소 보완

### 27.1 Dashboard (Screen 1)에서 미반영된 요소

| Stitch 요소 | UI_UX_PLAN 반영 | 보완 |
|------------|-----------------|------|
| Cluster 필터 버튼 ("PROD-SEOUL") | 미반영 | MVP: 단일 환경이므로 제외. Phase 2에서 멀티 클러스터 시 추가 |
| View 필터 버튼 ("Logical") | 미반영 | Phase 3 (토폴로지 뷰 모드) |
| "View 12 More Insights" 링크 | 미반영 | MVP: AI Insights Feed 하단에 "View All" 링크 → `/incidents?source=ai_baseline` 이동 |
| Topology SVG 연결선 스타일 | 미반영 | Phase 3 (MVP는 카드 그리드) |
| 하단 그라디언트 페이드 | 미반영 | CSS 효과. 구현 시 `bg-gradient-to-t from-surface-container to-transparent h-24` 적용 |

### 27.2 ASH Explorer (Screen 3)에서 미반영된 요소

| Stitch 요소 | UI_UX_PLAN 반영 | 보완 |
|------------|-----------------|------|
| 미니 바 차트 (Temporal Zoom 내부) | 부분 반영 | 바 높이로 해당 구간의 활동량 표현. 색상: `slate-800`(저) → `sky-500`(중) → `primary-container`(고) |
| Zoom 슬라이더 핸들 | 미반영 | `bg-primary/10 border-x-2 border-primary` 드래그 가능 영역 |
| "RECOMMENDED SQL" 코드 블록 | 부분 반영 | AI Interpretation 카드 내 `bg-surface-container-lowest p-3 rounded-lg`, 코드는 `font-mono text-secondary-fixed-dim` |
| "Execute Fix" / "Ignore" 버튼 분기 | 미반영 | MVP: "Execute Fix" → SQL을 클립보드에 복사 + 토스트 "SQL copied". Phase 2에서 실제 실행 연동 |

### 27.3 Diagnosis (Screen 4)에서 미반영된 요소

| Stitch 요소 | UI_UX_PLAN 반영 | 보완 |
|------------|-----------------|------|
| 인시던트 카드 좌측 1px 색상 라인 | 미반영 | `absolute left-0 top-0 w-1 h-full bg-{severity-color}` — Critical: `bg-error`, Warning: `bg-amber-500` |
| NL2SQL 챗 user 말풍선 `rounded-tr-none` | 미반영 | 사용자: `rounded-xl rounded-tr-none`, AI: `rounded-xl rounded-tl-none` |
| NL2SQL 코드 내 `<code>` 강조 | 미반영 | SQL 키워드: `text-secondary`, 테이블명: `text-primary`, 기본: `text-on-surface` |

### 27.4 Add DB Wizard (Screen 6)에서 미반영된 요소

| Stitch 요소 | UI_UX_PLAN 반영 | 보완 |
|------------|-----------------|------|
| DB 타입 카드 선택 시 `border-primary` | 미반영 | 선택됨: `border-2 border-primary`, 미선택: `border border-white/5` |
| 비밀번호 필드 eye 토글 아이콘 | 미반영 | 필드 우측 `visibility` / `visibility_off` Material Symbol 토글 |
| SSL 토글 색상 | 미반영 | ON: `bg-tertiary-container`, OFF: `bg-surface-variant` |
| "Enable 1s ASH Explorer" 옆 WARNING 뱃지 | 미반영 | `bg-amber-500/20 text-amber-400 text-[10px] px-2 py-0.5 rounded` |
| "Enable Autonomous Tuning" 옆 ADVANCED 뱃지 | 미반영 | `bg-secondary/20 text-secondary text-[10px] px-2 py-0.5 rounded` |

### 27.5 Topology Explorer (Screen 5)에서 미반영된 요소 (Phase 3 참고)

| Stitch 요소 | 비고 |
|------------|------|
| "LIVE" 뱃지 | `bg-tertiary/20 text-tertiary text-[10px] px-2 rounded animate-pulse` |
| Node Inspector 패널 | 우측 고정 패널 (w-80), 선택 노드 상세 + OTel 트레이드 + Blast Radius |
| "Simulate Outage" 버튼 | `bg-error/10 text-error border border-error/20` |
| Drift 알림 바 | 하단 `bg-amber-500/10 border border-amber-500/30 rounded-xl p-4` |

---

## 28. 수집 상태 표시 (2-Tier Hybrid Adapter)

MVP에서 Remote Adapter 사용 시, 사용자에게 수집 상태를 표시합니다.

### 인스턴스 카드에 표시

```
┌─────────────────────────┐
│ pg-prod-01        ✅ 1s │ ← 1초 수집 정상
│ CPU 45.2%  TPS 1,240    │
└─────────────────────────┘

┌─────────────────────────┐
│ pg-staging       ⚠️ 10s │ ← RTT 높아 10초로 폴백
│ CPU 30.1%  TPS 450      │
└─────────────────────────┘

┌─────────────────────────┐
│ pg-remote         ❌ N/A│ ← 수집 실패
│ Last seen: 5m ago       │
└─────────────────────────┘
```

**수집 상태 뱃지**:
| 상태 | 뱃지 | 색상 |
|------|------|------|
| 1s 정상 수집 | `1s` | `bg-tertiary/20 text-tertiary` |
| 폴백 (5s/10s) | `10s` | `bg-amber-500/20 text-amber-400` |
| 수집 실패 | `N/A` | `bg-error/20 text-error` |
| 베이스라인 학습 중 | `Learning` | `bg-secondary/20 text-secondary animate-pulse` |

---

---

## 29. 사용자 프로필 & 계정

### 29.1 TopNav 사용자 드롭다운

```
[👤 Kim Admin ▼]

클릭 시:
┌──────────────────────────┐
│ Kim Admin                │
│ admin@company.com        │
│ Role: Super Admin        │
├──────────────────────────┤
│ 🔑 Change Password       │
│ 🌐 Language: 한국어 ▼     │
│ ⌨️  Keyboard Shortcuts   │
├──────────────────────────┤
│ 🚪 Sign Out              │
└──────────────────────────┘
```

**스타일**: `glass-panel rounded-xl border border-white/5 w-64 shadow-2xl z-[60]`
**위치**: TopNav 우측 아이콘 아래 (`absolute right-0 top-16`)
**닫기**: 외부 클릭, `Esc` 키

### 29.2 비밀번호 변경 모달

```
┌──────────────────────────────────┐
│  Change Password                 │
├──────────────────────────────────┤
│  Current Password                │
│  [________________________]  👁  │
│                                  │
│  New Password                    │
│  [________________________]  👁  │
│  ░░░░░░░░░░ (강도 표시 바)        │
│  8자 이상, 영문+숫자+특수문자      │
│                                  │
│  Confirm New Password            │
│  [________________________]  👁  │
│                                  │
│  [Cancel]  [Change Password]     │
└──────────────────────────────────┘
```

**검증**:
| 필드 | 규칙 | 에러 |
|------|------|------|
| Current Password | 필수, 서버 검증 | "현재 비밀번호가 일치하지 않습니다" |
| New Password | 8자+, 영문+숫자+특수문자 | "8자 이상, 영문/숫자/특수문자 포함" |
| Confirm | New Password와 일치 | "비밀번호가 일치하지 않습니다" |

**비밀번호 강도 바**:
| 강도 | 색상 | 조건 |
|------|------|------|
| Weak | `bg-error` (25%) | 8자 미만 또는 1종류만 |
| Fair | `bg-amber-500` (50%) | 8자+, 2종류 |
| Good | `bg-primary` (75%) | 10자+, 3종류 |
| Strong | `bg-tertiary` (100%) | 12자+, 3종류+ |

---

## 30. 글로벌 검색

### 30.1 검색 동작

**트리거**: TopNav 검색바 클릭 또는 `/` 키보드 단축키

```
┌─────────────────────────────────────────────────────────┐
│  🔍 Search instances, incidents...              [Esc]   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  INSTANCES                                              │
│  ┌───────────────────────────────────────────────┐      │
│  │ 🗄 pg-prod-01  PostgreSQL  10.0.1.100  ✅     │      │
│  │ 🗄 pg-prod-02  PostgreSQL  10.0.1.101  ⚠️     │      │
│  └───────────────────────────────────────────────┘      │
│                                                         │
│  INCIDENTS                                              │
│  ┌───────────────────────────────────────────────┐      │
│  │ 🔴 CPU Spike on pg-prod-01          2m ago    │      │
│  │ 🟠 Replication Lag Exceeded         14m ago   │      │
│  └───────────────────────────────────────────────┘      │
│                                                         │
│  Tip: Type "/" to search from anywhere                  │
└─────────────────────────────────────────────────────────┘
```

### 30.2 검색 규격

| 항목 | 사양 |
|------|------|
| **표시 방식** | 모달 오버레이 (backdrop blur) |
| **위치** | 화면 상단 중앙, `max-w-2xl` |
| **디바운스** | 300ms (타이핑 멈춘 후 검색) |
| **최소 입력** | 2자 이상 시 결과 표시 |
| **검색 대상** | 인스턴스 name/host, 인시던트 title |
| **결과 분류** | "INSTANCES" / "INCIDENTS" 그룹 분리 |
| **결과 제한** | 그룹당 최대 5건 |
| **키보드** | `↑↓` 결과 이동, `Enter` 선택, `Esc` 닫기 |
| **빈 결과** | "No results for '{query}'" |
| **닫기** | `Esc`, 외부 클릭, 결과 선택 시 자동 닫기 |

### 30.3 검색 결과 클릭 동작

| 결과 유형 | 이동 경로 |
|----------|----------|
| 인스턴스 | `/ash/{instanceId}` (ASH Explorer) |
| 인시던트 | `/incidents?selected={incidentId}` (인시던트 하이라이트) |

### 30.4 API

```
GET /api/v1/search?q={query}&limit=5
```

> 이 엔드포인트는 API_SPEC.md에 추가 필요. MVP에서는 프론트엔드에서 인스턴스 목록 + 인시던트 목록을 로컬 필터링으로 대체 가능.

---

## 31. 테이블 공통 규격

### 31.1 페이지네이션

```
┌──────────────────────────────────────────────────────────────┐
│  Showing 1-20 of 156                    [< Prev] [Next >]   │
│                                         Page 1 of 8          │
└──────────────────────────────────────────────────────────────┘
```

| 항목 | 사양 |
|------|------|
| 기본 페이지 크기 | 20행 |
| 페이지 크기 옵션 | 10 / 20 / 50 (드롭다운) |
| 페이지 이동 | Prev / Next 버튼, 현재 페이지 / 총 페이지 표시 |
| 구현 방식 | 커서 기반 (API는 `cursor` + `limit`, UI는 Prev/Next) |
| 위치 | 테이블 하단 우측 |
| 스타일 | `text-xs text-on-surface-variant` |

**적용 대상**:
- `/settings/instances` — 인스턴스 목록
- `/incidents` — 인시던트 목록
- `/settings/users` — 사용자 목록
- `/settings/alerts` — 알림 채널 목록
- ASH Session Table — 세션 목록

### 31.2 정렬 헤더

```
│ Name ▲ | Type | Host | Status ▽ |
```

| 항목 | 사양 |
|------|------|
| 정렬 표시 | 컬럼명 우측에 `▲` (오름차순) / `▽` (내림차순) |
| 기본 정렬 | 테이블별 지정 (인시던트: `detected_at DESC`, 인스턴스: `name ASC`) |
| 클릭 동작 | 1차 클릭: ASC, 2차: DESC, 3차: 정렬 해제 |
| 정렬 가능 컬럼 | 테이블 헤더에 `cursor-pointer hover:text-primary` |
| 정렬 불가 컬럼 | `cursor-default` (Actions 컬럼 등) |
| 서버 정렬 | API `?sort_by=name&sort_order=asc` |

### 31.3 데이터 내보내기 (CSV)

```
┌──────────────────────────────────────────────────────────┐
│  Incidents                           [↓ Export CSV]      │
├──────────────────────────────────────────────────────────┤
```

| 항목 | 사양 |
|------|------|
| 버튼 위치 | 테이블 헤더 우측, 필터 옆 |
| 버튼 스타일 | `text-xs text-primary hover:underline` + `download` Material Symbol |
| 내보내기 범위 | 현재 필터 적용된 전체 데이터 (현재 페이지 아님) |
| 파일명 | `neuraldb_{resource}_{YYYYMMDD_HHmmss}.csv` |
| 인코딩 | UTF-8 with BOM (Excel 한글 호환) |
| 최대 행 | 10,000행 (초과 시 "Too many rows" 경고) |

**적용 대상** (MVP):
- 인시던트 목록 (`/incidents`)
- ASH 세션 테이블 (`/ash/:id`)
- 감사 로그 (`/settings → audit logs`)

---

## 32. 브레드크럼 네비게이션

### Settings 하위 페이지에 적용

```
Settings  >  Instances  >  pg-prod-01
Settings  >  Instances  >  New Database
Settings  >  Alert Channels
Settings  >  Users
```

| 항목 | 사양 |
|------|------|
| 위치 | 페이지 콘텐츠 상단, PageHeader 위 |
| 구분자 | `>` (`text-outline text-xs`) |
| 현재 페이지 | `text-on-surface font-medium` (링크 아님) |
| 상위 경로 | `text-primary hover:underline cursor-pointer` |
| 스타일 | `text-xs text-on-surface-variant flex items-center gap-1 mb-2` |

**적용 범위** (MVP):
- `/settings/*` 하위 모든 페이지
- `/incidents/:id` (Phase 2, 인시던트 상세)

**미적용**:
- `/dashboard`, `/ash/:id`, `/incidents` — 1단계 경로이므로 불필요

---

## 33. 도움말 & 온보딩

### 33.1 컨텍스트 도움말

각 주요 섹션 제목 옆에 `help_outline` 아이콘 → hover 시 툴팁 표시.

```
Active Sessions (ASH)  ℹ️
                       ┌──────────────────────────────┐
                       │ 1초 간격으로 pg_stat_activity │
                       │ 에서 활성 세션을 샘플링합니다.│
                       │ Wait Event 카테고리별로       │
                       │ 분류하여 병목을 파악합니다.    │
                       └──────────────────────────────┘
```

| 항목 | 사양 |
|------|------|
| 아이콘 | `help_outline` Material Symbol, `text-outline text-sm` |
| 트리거 | Hover (데스크톱), Tap (모바일) |
| 위치 | 섹션 제목 우측 |
| 툴팁 스타일 | `glass-panel rounded-lg p-3 max-w-xs text-xs z-[70]` |
| 닫기 | mouseout, 외부 tap |

**적용 대상** (MVP):
| 위치 | 도움말 내용 |
|------|-----------|
| Dashboard Summary Cards | 각 메트릭의 의미와 계산 방법 |
| ASH Heatmap | Wait Event 카테고리 설명 |
| Incidents 필터 | 각 severity 등급의 의미 |
| Add DB Wizard Step 3 | ASH Explorer, Autonomous Tuning 기능 설명 |
| Autonomy Level (SideNav) | 현재 자율 등급의 의미와 행동 범위 |

### 33.2 첫 사용 온보딩 (MVP 간소화)

최초 로그인 후 인스턴스가 0개일 때:

```
┌──────────────────────────────────────────────────────┐
│                                                      │
│         Welcome to NeuralDB                          │
│                                                      │
│   🗄 Monitor your databases with AI intelligence     │
│                                                      │
│   Step 1: Add your first database                    │
│   Step 2: Wait 2 weeks for AI baseline learning      │
│   Step 3: Get intelligent anomaly detection          │
│                                                      │
│   [+ Add Your First Database]                        │
│                                                      │
│   Or explore with demo data → [Load Demo]            │
│                                                      │
└──────────────────────────────────────────────────────┘
```

> 복잡한 가이드 투어(Step-by-step overlay)는 Phase 2 이후. MVP는 EmptyState + CTA로 충분.

---

## 34. 에러 페이지

### 34.1 404 Not Found

```
┌──────────────────────────────────────────────────────┐
│                                                      │
│                    404                                │
│           Page Not Found                             │
│                                                      │
│   The page you're looking for doesn't exist          │
│   or has been moved.                                 │
│                                                      │
│   [Go to Dashboard]                                  │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### 34.2 403 Forbidden

```
┌──────────────────────────────────────────────────────┐
│                                                      │
│                    🔒                                 │
│           Access Denied                              │
│                                                      │
│   You don't have permission to access this page.     │
│   Contact your administrator for access.             │
│                                                      │
│   Your role: Viewer                                  │
│   Required: DB Admin or higher                       │
│                                                      │
│   [Go to Dashboard]                                  │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### 34.3 500 Server Error (ErrorBoundary)

```
┌──────────────────────────────────────────────────────┐
│                                                      │
│                    ⚠️                                │
│           Something went wrong                       │
│                                                      │
│   An unexpected error occurred.                      │
│   Our team has been notified.                        │
│                                                      │
│   [Reload Page]  [Go to Dashboard]                   │
│                                                      │
└──────────────────────────────────────────────────────┘
```

**공통 스타일**:
- 전체 페이지 중앙 정렬 (`flex items-center justify-center min-h-screen`)
- 배경: `surface` + `neural-grid`
- 코드/아이콘: `text-6xl font-headline text-on-surface-variant`
- 설명: `text-sm text-on-surface-variant mt-4`
- 버튼: `Button variant="primary"` (하단)

---

## Changelog

| 날짜 | 변경 |
|------|------|
| 2026-03-21 | v1.0 초기 작성 (섹션 1~10) |
| 2026-03-21 | v1.1 보완 — 로그인, RBAC, 로딩/에러/빈 상태, 토스트, 알림 설정, 사용자 관리, 반응형, 접근성, 키보드, i18n, 캐싱, 확인 다이얼로그 (섹션 11~22) |
| 2026-03-21 | v1.2 심층 보완 — 폼 검증, 차트/시각화, 트랜지션/애니메이션, 인터랙션 상태 매트릭스, Stitch 미반영 요소, 수집 상태 표시 (섹션 23~28) |
| 2026-03-21 | v1.3 최종 보완 — 사용자 프로필/비밀번호 변경, 글로벌 검색, 테이블 페이지네이션/정렬/CSV 내보내기, 브레드크럼, 도움말/온보딩, 에러 페이지 404/403/500 (섹션 29~34) |
