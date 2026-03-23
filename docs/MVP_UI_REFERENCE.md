# MVP UI 구현 참조 가이드

> 이 문서는 MVP 프론트엔드 개발 시 **어떤 화면을 만들 때 어떤 문서를 참조해야 하는지** 한눈에 찾기 위한 인덱스입니다.
> 기획/디자인/API/테스트 문서가 여러 곳에 분산되어 있으므로, 화면 단위로 참조 경로를 정리합니다.

---

## 1. 문서 맵 (전체 참조 구조)

```
구현할 화면
  ↓ 기획은 어디?
  docs/UI_UX_PLAN.md (섹션 4: 화면별 상세)
  ↓ 디자인은 어디?
  docs/FRONTEND_DESIGN.md (디자인 토큰 + 컴포넌트 패턴)
  docs/screen{N}_{name}.html (Stitch HTML 원본)
  docs/screenshots/screen{N}_{name}.png (스크린샷)
  ↓ API는 어디?
  docs/specs/api/API_SPEC.md (REST 엔드포인트 + 페이로드)
  ↓ 데이터 모델은?
  docs/specs/data-model/ERD.md (테이블 구조)
  ↓ 테스트는?
  docs/specs/tests/FRONTEND_TEST_SPEC.md (FE 단위 테스트)
  docs/specs/tests/TEST_SPEC.md (E2E 테스트)
```

---

## 2. 화면별 참조 문서

### 2.1 공통 (모든 화면에 적용)

| 항목 | 참조 문서 | 위치 |
|------|----------|------|
| 디자인 토큰 (색상, 폰트, 간격, 효과) | `FRONTEND_DESIGN.md` 섹션 2 | docs/ |
| 컴포넌트 라이브러리 (버튼, 뱃지, 카드 등) | `FRONTEND_DESIGN.md` 섹션 5 | docs/ |
| 글로벌 레이아웃 (TopNav, SideNav) | `UI_UX_PLAN.md` 섹션 3 | docs/ |
| 라우팅 구조 | `UI_UX_PLAN.md` 섹션 2 | docs/ |
| RBAC 접근 제어 | `UI_UX_PLAN.md` 섹션 12 | docs/ |
| 로딩/에러/빈 상태 | `UI_UX_PLAN.md` 섹션 13 | docs/ |
| 토스트 알림 | `UI_UX_PLAN.md` 섹션 14 | docs/ |
| 반응형 브레이크포인트 | `UI_UX_PLAN.md` 섹션 17 | docs/ |
| 접근성 기준 | `UI_UX_PLAN.md` 섹션 18 | docs/ |
| 키보드 단축키 | `UI_UX_PLAN.md` 섹션 19 | docs/ |
| i18n 전략 | `UI_UX_PLAN.md` 섹션 20 | docs/ |
| 데이터 캐싱/페칭 | `UI_UX_PLAN.md` 섹션 21 | docs/ |
| 상태 관리 (Zustand/TanStack Query) | `UI_UX_PLAN.md` 섹션 8 | docs/ |
| FE 테스트 전략 | `FRONTEND_TEST_SPEC.md` | docs/specs/tests/ |
| 컴포넌트 트리 | `UI_UX_PLAN.md` 섹션 5 | docs/ |
| 기술 스택 (FE) | `TECH_STACK.md` 섹션 2 | docs/ |
| 디자인 규칙 (No-Line, No-Black 등) | `FRONTEND_DESIGN.md` 섹션 2.5 | docs/ |

---

### 2.2 Login (`/login`)

| 항목 | 문서 | 섹션/경로 |
|------|------|----------|
| **기획** | `UI_UX_PLAN.md` | 섹션 11 (레이아웃, 에러 상태) |
| **디자인** | `FRONTEND_DESIGN.md` | 섹션 2.4 (glass-panel, neural-grid) |
| **API** | `API_SPEC.md` | 섹션 1 (POST /auth/login, /auth/refresh) |
| **스키마** | `ERD.md` | 섹션 2.12 (users 테이블) |
| **테스트** | `FRONTEND_TEST_SPEC.md` | (auth flow 테스트 추가 필요) |
| **Stitch** | 없음 | 디자인 토큰 기반 신규 구현 |

---

### 2.3 Dashboard (`/dashboard`)

| 항목 | 문서 | 섹션/경로 |
|------|------|----------|
| **기획** | `UI_UX_PLAN.md` | 섹션 4.1 (레이아웃, 컴포넌트, 인터랙션) |
| **디자인** | `FRONTEND_DESIGN.md` | 섹션 4.1 (Screen 1 스펙) |
| **Stitch HTML** | `screen1_topology.html` | docs/ |
| **스크린샷** | `screen1_topology.png` | docs/screenshots/ |
| **API - 인스턴스** | `API_SPEC.md` | 섹션 2 (GET /instances) |
| **API - 메트릭** | `API_SPEC.md` | 섹션 3 (GET /instances/{id}/metrics) |
| **API - 인시던트** | `API_SPEC.md` | 섹션 5 (GET /incidents) |
| **WebSocket** | `API_SPEC.md` | 섹션 15 (/ws/metrics, /ws/incidents) |
| **실시간 흐름** | `UI_UX_PLAN.md` | 섹션 6 |
| **스키마** | `ERD.md` | 섹션 2.1 (db_instances), 2.2 (metric_samples), 2.4 (incidents) |
| **사용자 플로우** | `UI_UX_PLAN.md` | 섹션 7 Flow 1 (온보딩), Flow 2 (이상 탐지) |
| **테스트** | `FRONTEND_TEST_SPEC.md` | 섹션 4.2 (MetricCard, IncidentList) |
| **E2E** | `TEST_SPEC.md` | AC-7 (로딩 <3초, WebSocket <1초) |

**MVP 변경사항**: Screen 1의 토폴로지 맵 → 인스턴스 카드 그리드로 대체

---

### 2.4 ASH Explorer (`/ash/:instanceId`)

| 항목 | 문서 | 섹션/경로 |
|------|------|----------|
| **기획** | `UI_UX_PLAN.md` | 섹션 4.2 (레이아웃, 컴포넌트, 인터랙션) |
| **디자인** | `FRONTEND_DESIGN.md` | 섹션 4.3 (Screen 3 전체 스펙) |
| **Stitch HTML** | `screen3_ash.html` | docs/ |
| **스크린샷** | `screen3_ash.png` | docs/screenshots/ |
| **API - ASH** | `API_SPEC.md` | 섹션 4 (GET /ash, /ash/heatmap, /ash/wait-breakdown) |
| **API - NL2SQL** | `API_SPEC.md` | 섹션 8 (POST /nl2sql/explain) |
| **WebSocket** | `API_SPEC.md` | 섹션 15 (/ws/ash) |
| **스키마** | `ERD.md` | 섹션 2.3 (active_sessions) |
| **사용자 플로우** | `UI_UX_PLAN.md` | 섹션 7 Flow 2 (이상 탐지 → 조사) |
| **테스트** | `FRONTEND_TEST_SPEC.md` | 섹션 4.3 (ASHHeatmap, SessionTable) |
| **E2E** | `TEST_SPEC.md` | AC-2 (ASH 히트맵 표시) |

**핵심 컴포넌트**: TemporalZoom, ASHHeatmap (ECharts), SessionTable, WaitBreakdown, AIInterpretation

---

### 2.5 Incidents (`/incidents`)

| 항목 | 문서 | 섹션/경로 |
|------|------|----------|
| **기획** | `UI_UX_PLAN.md` | 섹션 4.3 (MVP 범위, 레이아웃, 카드 스타일) |
| **디자인** | `FRONTEND_DESIGN.md` | 섹션 4.4 (Screen 4 스펙 — 좌측 인시던트 목록만) |
| **Stitch HTML** | `screen4_diagnosis.html` | docs/ |
| **스크린샷** | `screen4_diagnosis.png` | docs/screenshots/ |
| **API** | `API_SPEC.md` | 섹션 5 (GET /incidents, PUT /incidents/{id}/status) |
| **WebSocket** | `API_SPEC.md` | 섹션 15 (/ws/incidents) |
| **스키마** | `ERD.md` | 섹션 2.4 (incidents) |
| **사용자 플로우** | `UI_UX_PLAN.md` | 섹션 7 Flow 3 (Slack → 대시보드) |
| **테스트** | `FRONTEND_TEST_SPEC.md` | 섹션 4.2 (IncidentList) |

**MVP 제외**: AI RCA 패널 (우측), 인과 관계 체인 시각화, Generate Playbook 버튼 → Phase 2

---

### 2.6 Settings - Instance Management (`/settings/instances`)

| 항목 | 문서 | 섹션/경로 |
|------|------|----------|
| **기획** | `UI_UX_PLAN.md` | 섹션 4.4 (인스턴스 목록 + 서브 구조) |
| **API** | `API_SPEC.md` | 섹션 2 (CRUD + test-connection) |
| **스키마** | `ERD.md` | 섹션 2.1 (db_instances) |
| **RBAC** | `UI_UX_PLAN.md` | 섹션 12 (DB Admin 이상만 CUD) |
| **확인 다이얼로그** | `UI_UX_PLAN.md` | 섹션 22 (삭제 시 이름 입력 확인) |
| **암호화** | `ADR-007` | docs/ADR/ (connection_config 암호화) |
| **테스트** | `FRONTEND_TEST_SPEC.md` | 섹션 4.5 (AddDatabaseWizard) |

---

### 2.7 Settings - Add Database Wizard (`/settings/instances/new`)

| 항목 | 문서 | 섹션/경로 |
|------|------|----------|
| **기획** | `UI_UX_PLAN.md` | 섹션 4.4 (3단계 마법사) |
| **디자인** | `FRONTEND_DESIGN.md` | 섹션 10 (Screen 6 전체 스펙) |
| **Stitch HTML** | `screen6_add_database.html` | docs/ |
| **스크린샷** | `screen6_add_database.png` | docs/screenshots/ |
| **API** | `API_SPEC.md` | 섹션 2 (POST /instances, POST /instances/{id}/test-connection) |
| **스키마** | `ERD.md` | 섹션 2.1 (db_instances — connection_config JSONB) |
| **사용자 플로우** | `UI_UX_PLAN.md` | 섹션 7 Flow 1 (온보딩) |
| **테스트** | `FRONTEND_TEST_SPEC.md` | 섹션 4.5 (step 검증, 필수 필드, test connection) |

---

### 2.8 Settings - Alert Channels (`/settings/alerts`)

| 항목 | 문서 | 섹션/경로 |
|------|------|----------|
| **기획** | `UI_UX_PLAN.md` | 섹션 15 (채널 목록, Add/Edit 모달) |
| **API** | `API_SPEC.md` | 섹션 14 (GET/POST /alerts/channels, POST /alerts/test) |
| **RBAC** | `UI_UX_PLAN.md` | 섹션 12 (DB Admin 이상) |

---

### 2.9 Settings - User Management (`/settings/users`)

| 항목 | 문서 | 섹션/경로 |
|------|------|----------|
| **기획** | `UI_UX_PLAN.md` | 섹션 16 (사용자 테이블, Add/Edit 모달, 역할 드롭다운) |
| **API** | `API_SPEC.md` | 섹션 12 (CRUD /users, GET /audit-logs) |
| **RBAC** | `UI_UX_PLAN.md` | 섹션 12 (Super Admin only) |
| **스키마** | `ERD.md` | 섹션 2.12 (users) |

---

### 2.10 NL2SQL Chat (플로팅 위젯)

| 항목 | 문서 | 섹션/경로 |
|------|------|----------|
| **기획** | `UI_UX_PLAN.md` | 섹션 4.5 (구성, 인터랙션) |
| **디자인** | `FRONTEND_DESIGN.md` | 섹션 4.4 (Screen 4 하단 채팅 위젯 스펙) |
| **Stitch HTML** | `screen4_diagnosis.html` | docs/ (하단 플로팅 챗 영역) |
| **API** | `API_SPEC.md` | 섹션 8 (POST /nl2sql/query, /nl2sql/explain) |
| **Agent Spec** | `AGENT_SPEC.md` | 섹션 2.4 (Reporting Agent — NL2SQL 도구) |
| **사용자 플로우** | `UI_UX_PLAN.md` | 섹션 7 Flow 4 (NL2SQL 질의) |
| **테스트** | `FRONTEND_TEST_SPEC.md` | 섹션 4.4 (NL2SQLChat) |
| **E2E** | `TEST_SPEC.md` | AC-5 (NL2SQL 성공률 >80%) |

---

### 2.11 System Health (`/system`)

| 항목 | 문서 | 섹션/경로 |
|------|------|----------|
| **기획** | `UI_UX_PLAN.md` | 섹션 4.6 (4개 컴포넌트 상태 카드) |
| **API** | `API_SPEC.md` | 섹션 13 (GET /system/health, /system/health/details) |
| **Self-Monitoring** | `TECH_STACK.md` | 섹션 5.1 (Self-Monitoring Stack) |
| **PRD** | `PRD v3.2` | 섹션 4.7 FR-SELF-001~005 |

---

## 3. 구현 순서 (Week별 참조 문서)

| Week | 구현 대상 | 핵심 참조 문서 |
|------|----------|-------------|
| **W1** | 프로젝트 초기화, 디자인 토큰 | `TECH_STACK.md` §2, `FRONTEND_DESIGN.md` §2 |
| **W2** | MainLayout, TopNav, SideNav, Router, Login | `UI_UX_PLAN.md` §3 §11 §2, `FRONTEND_DESIGN.md` §3 |
| **W3** | Dashboard: SummaryCard, InstanceGrid | `UI_UX_PLAN.md` §4.1, `FRONTEND_DESIGN.md` §4.1, `screen1_topology.html` |
| **W4** | Dashboard: ResourceChart + WebSocket | `UI_UX_PLAN.md` §6, `API_SPEC.md` §3 §15, `KAFKA_SPEC.md` |
| **W5** | ASH: TemporalZoom, ASHHeatmap | `UI_UX_PLAN.md` §4.2, `FRONTEND_DESIGN.md` §4.3, `screen3_ash.html` |
| **W6** | ASH: SessionTable, WaitBreakdown, AI카드 | `screen3_ash.html` (전체), `API_SPEC.md` §4 |
| **W7** | Incidents: IncidentList, SeverityBadge | `UI_UX_PLAN.md` §4.3, `FRONTEND_DESIGN.md` §4.4, `screen4_diagnosis.html` |
| **W8** | Settings: InstanceList, AddDatabaseWizard | `UI_UX_PLAN.md` §4.4, `screen6_add_database.html`, `API_SPEC.md` §2 |
| **W9** | Settings: AlertChannelForm, UserManagement | `UI_UX_PLAN.md` §15 §16, `API_SPEC.md` §12 §14 |
| **W10** | NL2SQL Chat, System Health | `UI_UX_PLAN.md` §4.5 §4.6, `API_SPEC.md` §8 §13 |
| **W11** | 통합 테스트, 반응형, 접근성 | `FRONTEND_TEST_SPEC.md`, `UI_UX_PLAN.md` §17 §18 |
| **W12** | 버그 수정, QA | `TEST_SPEC.md` AC-1~10 |

---

## 4. Stitch 디자인 파일 Quick Reference

| 화면 | HTML | 스크린샷 | MVP 용도 |
|------|------|---------|---------|
| Dashboard 원본 | `screen1_topology.html` | `screen1_topology.png` | Summary Cards + 차트 참조 (토폴로지는 카드로 대체) |
| Self-Healing | `screen2_selfhealing.html` | `screen2_selfhealing.png` | Phase 2 참고만 |
| **ASH Explorer** | `screen3_ash.html` | `screen3_ash.png` | **전체 구현** |
| Diagnosis | `screen4_diagnosis.html` | `screen4_diagnosis.png` | 좌측 인시던트 목록 + NL2SQL 챗만 |
| Topology Explorer | `screen5_topology_explorer.html` | `screen5_topology_explorer.png` | Phase 3 참고만 |
| **Add DB Wizard** | `screen6_add_database.html` | `screen6_add_database.png` | **전체 구현** |
| Diagnosis Flow | `screen7_diagnosis_flow.html` | (없음) | UX 참고 문서 |

---

## 5. 자주 참조하는 디자인 토큰 (발췌)

> 전체는 `FRONTEND_DESIGN.md` 섹션 2 참조.

### 색상 (가장 많이 쓰는 10개)

| 토큰 | Hex | 용도 |
|------|-----|------|
| `surface` | `#0b1326` | 페이지 배경 |
| `surface-container` | `#171f33` | 카드/사이드바 배경 |
| `surface-container-high` | `#222a3d` | 활성 카드, hover |
| `on-surface` | `#dae2fd` | 기본 텍스트 |
| `primary` | `#89ceff` | 인터랙션 요소, 링크 |
| `primary-container` | `#0ea5e9` | 주요 버튼 배경 |
| `error` | `#ffb4ab` | Critical 텍스트 |
| `tertiary` | `#4edea3` | 성공/건강 상태 |
| `secondary` | `#d0bcff` | AI/예측 관련 |
| `outline-variant` | `#3e4850` | Ghost Border (15% opacity) |

### 폰트

| 용도 | 클래스 | 폰트 |
|------|--------|------|
| 제목 | `font-headline` | Space Grotesk 700 |
| 본문 | `font-body` | Inter 400-500 |
| 코드 | `font-mono` | JetBrains Mono 400 |

### 효과

```css
.glass-panel   { background: rgba(45,52,73,0.6); backdrop-filter: blur(24px); }
.neural-glow   { box-shadow: 0 0 40px rgba(14,165,233,0.08); }
```
