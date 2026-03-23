# NeuralDB - Frontend Design Specification

> **Source**: [Google Stitch Project](https://stitch.withgoogle.com/projects/11640044698331273458)
> **Project Title**: AI Diagnosis & RCA Panel
> **Device Target**: Desktop (2560 x 2176)
> **Design Theme**: Dark Mode / High-Fidelity

---

## 1. Creative Direction: "The Digital Synapse"

신경망(Neural Network)을 시각적 메타포로 사용하는 고밀도 데이터 모니터링 인터페이스.
- 의도적 비대칭(Intentional Asymmetry)과 대기적 깊이(Atmospheric Depth) 활용
- 데이터베이스 아키텍처 *안을* 들여다보는 느낌
- 고대비 타이포그래피 스케일과 겹치는 글래스 레이어

---

## 2. Design Tokens

### 2.1 Color Palette

#### Core Surfaces (Dark Theme Base)
| Token | Hex | 용도 |
|-------|-----|------|
| `surface` | `#0b1326` | 최하단 배경 (Infinite Void) |
| `surface-container-lowest` | `#060e20` | 가장 깊은 레이어 |
| `surface-container-low` | `#131b2e` | 내비게이션/레이아웃 블록 |
| `surface-container` | `#171f33` | 사이드바, 카드 기본 배경 |
| `surface-container-high` | `#222a3d` | 활성 카드/모듈 |
| `surface-container-highest` | `#2d3449` | 최상위 컨테이너 |
| `surface-variant` | `#2d3449` | 서브 영역 |
| `surface-bright` | `#31394d` | Hover 상태 |
| `background` | `#0b1326` | 전체 배경 |

#### Functional Colors
| Token | Hex | 용도 |
|-------|-----|------|
| `primary` | `#89ceff` | Cyber Blue - 주요 인터랙션/텍스트 강조 |
| `primary-container` | `#0ea5e9` | 주요 버튼/아이콘 배경 |
| `secondary` | `#d0bcff` | AI/ML Violet - 예측 인사이트 |
| `secondary-container` | `#571bc1` | AI 관련 버튼/칩 배경 |
| `tertiary` | `#4edea3` | Emerald - 건강/성공 상태 |
| `tertiary-container` | `#00b17b` | 성공 상태 배경 |
| `error` | `#ffb4ab` | Rose - DB 장애/보안 위반 |
| `error-container` | `#93000a` | Critical 알림 배경 |

#### Text Colors
| Token | Hex | 용도 |
|-------|-----|------|
| `on-surface` | `#dae2fd` | 기본 텍스트 |
| `on-surface-variant` | `#bec8d2` | 보조 텍스트 |
| `on-background` | `#dae2fd` | 배경 위 텍스트 |
| `on-primary` | `#00344d` | Primary 위 텍스트 |
| `on-primary-container` | `#003751` | Primary Container 위 텍스트 |
| `on-secondary` | `#3c0091` | Secondary 위 텍스트 |
| `on-error` | `#690005` | Error 위 텍스트 |
| `outline` | `#88929b` | 경계선 |
| `outline-variant` | `#3e4850` | Ghost Border (15% opacity) |

#### Warning / Status
| 상태 | 색상 | Hex |
|------|------|-----|
| Warning/Amber | `amber-500` | `#f59e0b` |
| Critical | `error` | `#ffb4ab` |
| Success/Health | `tertiary` | `#4edea3` |
| AI/Predictive | `secondary` | `#d0bcff` |

### 2.2 Typography

| 역할 | Font | Weight | Size | Letter Spacing |
|------|------|--------|------|----------------|
| Display/Headlines | **Space Grotesk** | 700 | 3.5rem (display-lg) | -0.02em |
| Headline Medium | Space Grotesk | 700 | 1.75rem | -0.02em |
| Headline Small | Space Grotesk | 700 | 1.25rem | tight |
| Body/Data | **Inter** | 400-500 | 0.875rem | normal |
| Label/Caption | Inter | 600-700 | 0.75rem | wider/widest |
| Code/Queries | **JetBrains Mono** | 400 | 0.75-0.875rem | normal |

#### 타이포그래피 규칙
- Headlines: Space Grotesk (시네마틱, 에디토리얼 느낌)
- System/Data: Inter (정밀한 데이터 표현)
- SQL/Code: JetBrains Mono + `secondary-fixed-dim (#d0bcff)` 구문 강조

### 2.3 Spacing & Border Radius

| Token | Value |
|-------|-------|
| `DEFAULT` border-radius | `0.125rem` (2px) |
| `lg` | `0.25rem` (4px) |
| `xl` | `0.5rem` (8px) |
| `full` | `0.75rem` (12px) |
| Card radius | `rounded-xl` (8px) / `rounded-2xl` (16px) |
| 모듈 간 간격 | `3.5rem` (spacing-16) |
| 카드 내부 패딩 | `1.25rem` ~ `2rem` (p-5 ~ p-8) |

### 2.4 Elevation & Effects

```css
/* Glassmorphism - Floating 모달/팝오버 */
.glass-panel {
  background: rgba(45, 52, 73, 0.6);
  backdrop-filter: blur(24px);
}

/* Neural Glow - Ambient Shadow */
.neural-glow {
  box-shadow: 0 0 40px rgba(14, 165, 233, 0.08);
}

/* Glass Card - 토폴로지 노드 등 */
.glass-card {
  background: rgba(34, 42, 61, 0.4);
  backdrop-filter: blur(24px);
}

/* Neural Grid - 백그라운드 패턴 */
.neural-grid {
  background-image: radial-gradient(
    circle at 1px 1px,
    rgba(14, 165, 233, 0.05) 1px,
    transparent 0
  );
  background-size: 40px 40px;
}

/* AI Shimmer - AI 카드 그라디언트 */
.ai-shimmer {
  background: linear-gradient(90deg, transparent, rgba(208, 188, 255, 0.1), transparent);
}

/* Ghost Border - 15% opacity 경계 */
border: 1px solid rgba(62, 72, 80, 0.15);

/* Background Decoration - 뉴럴 플로우 */
.bg-decoration {
  position: fixed;
  width: 400-600px;
  height: 400-600px;
  background: primary/5 또는 secondary/5;
  border-radius: 50%;
  filter: blur(100-120px);
}
```

### 2.5 Design Rules

#### "No-Line" Rule
- **1px solid border 사용 금지** (섹션 구분 용도)
- 배경색 차이(Surface Hierarchy)로 영역 구분
- `surface-container` → `surface-container-high` 등 톤 전환으로 시선 유도

#### Do's
- 의도적 비대칭 레이아웃 사용
- 모듈 간 `3.5rem` 간격으로 "Dashboard Fatigue" 방지
- 색상은 의미 기반으로만 사용 (장식 금지)

#### Don'ts
- 100% 불투명 Border 금지 (Glassmorphism 파괴)
- 순수 검정(#000000) 금지 → 최소 `#0b1326` 사용
- 과도한 애니메이션 금지 → `ease-out` 전환만 사용

---

## 3. Layout Structure

### 3.1 Global Layout

```
┌─────────────────────────────────────────────────────┐
│  TopNavBar (h-16, fixed, z-50)                      │
├──────────┬──────────────────────────────────────────┤
│          │                                          │
│ SideNav  │  Main Content Area                       │
│ (w-64,   │  (ml-64, pt-24, px-8)                   │
│  fixed,  │                                          │
│  z-40)   │                                          │
│          │                                          │
│          │                                          │
│          │                                          │
│          │                                          │
└──────────┴──────────────────────────────────────────┘
```

### 3.2 TopNavBar

| 요소 | 사양 |
|------|------|
| 높이 | `h-16` (64px) |
| 배경 | `#0b1326` |
| 그림자 | `shadow-[0_0_40px_rgba(14,165,233,0.08)]` |
| 로고 | "NeuralDB" - `text-xl font-black text-sky-500 tracking-tighter font-headline` |
| 상태 탭 | "Health: 98%" - `text-sky-400 border-b-2 border-sky-400` (활성) |
| 환경 탭 | "On-Premise" - `text-slate-400` |
| 검색바 | `bg-surface-container-lowest rounded-xl pl-10 pr-4 py-1.5 w-64` |
| 아이콘 | `notifications`, `account_circle` (Material Symbols) |

### 3.3 SideNavBar

| 요소 | 사양 |
|------|------|
| 너비 | `w-64` (256px) |
| 배경 | `#171f33` (`surface-container`) |
| 우측 경계 | `border-r border-white/5` |
| 상단 영역 | Autonomy 상태 표시 (`Autonomy Lvl 4`, `Latency: 12ms`) |
| **아이콘** | w-10 h-10 `rounded-xl bg-primary-container` |

#### Navigation Items
```
Dashboard     - icon: dashboard
Topology      - icon: hub
Diagnosis     - icon: troubleshoot
ASH Explorer  - icon: analytics
Playbook      - icon: menu_book
Settings      - icon: settings
```

**활성 상태**: `bg-[#222a3d] text-sky-400 border-r-4 border-sky-500 translate-x-1`
**기본 상태**: `text-slate-400 hover:bg-[#222a3d] hover:text-slate-100`
**스타일**: `px-3 py-2.5 rounded-lg font-medium text-sm gap-3`

#### 하단 영역
- **NL2SQL Assistant 버튼**: `bg-secondary-container text-white rounded-xl shadow-[0_0_20px_rgba(87,27,193,0.3)]` 또는 `bg-primary-container`
- Documentation / Support 링크

---

## 4. Screen Specifications

### 4.1 Screen 1: Full-Stack Topology Dashboard

**파일**: `screen1_topology.html`
**스크린샷**: `screenshots/screen1_topology.png`

#### Summary Cards (상단 4열 그리드)
```
grid-cols-4 gap-6
```

| 카드 | 값 | Border 색상 | 아이콘 |
|------|---|-------------|--------|
| Total Instances | 52 | `primary` | dns |
| Active Sessions | 1,240 | `primary-container` | group |
| Anomalies | 2 | `error` | warning |
| Avg Response Time | 12ms | `tertiary` | timer |

**카드 스타일**:
- `bg-surface-container p-5 rounded-xl border-l-4 shadow-sm`
- 값: `text-3xl font-headline font-bold`
- 라벨: `text-xs font-semibold tracking-wider uppercase text-slate-400`
- Hover: `hover:bg-surface-container-high transition-colors`

#### Topology Map (중앙)
- 컨테이너: `bg-surface-container rounded-2xl p-8 h-[500px]`
- SVG 커넥팅 라인으로 노드 연결
- 노드: `bg-surface-container-high p-4 rounded-xl border border-white/10`
- 경고 노드: `border-2 border-amber-500/50 ring-4 ring-amber-500/10`
- 로드밸런서: `rounded-full border-2 border-primary/30 w-24 h-24`
- 하단 그라디언트 페이드: `bg-gradient-to-t from-surface-container to-transparent`

#### Resource Orchestration (좌하단)
- Bar Chart: `flex items-end gap-1`
- Bar 색상: `bg-primary/20` (일반), `bg-primary` (스파이크)
- AI Baseline: `stroke-dasharray="4 4"` 점선 패스

#### AI Insights Feed (우하단)
| 유형 | 배지 색상 | Border |
|------|----------|--------|
| Predictive | `bg-secondary/20 text-secondary` | `border-l-4 border-secondary` |
| Anomaly | `bg-amber-500/20 text-amber-500` | - |
| Optimization | `bg-tertiary/20 text-tertiary` | - |

---

### 4.2 Screen 2: Self-Healing & Playbook Management

**파일**: `screen2_selfhealing.html`
**스크린샷**: `screenshots/screen2_selfhealing.png`

#### 헤더 영역
- 제목: `font-headline text-4xl font-bold tracking-tight`
  - "Adaptive Autonomy Dashboard"
- 상태 뱃지: `text-lg font-headline font-bold text-tertiary`
  - "Level 3: Approved Execution"
- 원형 게이지 인디케이터: `w-12 h-12 rounded-full border-4 border-tertiary/20`

#### Active Remediation Queue
- 컨테이너: `glass-panel p-6 rounded-xl border border-white/5`
- 작업 아이콘: `w-14 h-14 rounded-xl bg-[#0ea5e9]/10 border border-primary/20`
- 프로그레스 바: `h-2 bg-surface-variant rounded-full` + `bg-primary shadow-[0_0_12px_rgba(14,165,233,0.5)]`
- 버튼 그룹:
  - HALT: `bg-error/10 text-error border border-error/20`
  - INSPECT: `bg-surface-variant text-slate-200 border border-white/5`

#### Playbook-as-Code Library (좌하단 7:5 비율)
- 코드 에디터 스타일 레이아웃
- 라인 넘버: `bg-surface-dim w-12 font-mono text-[10px] text-slate-600`
- 코드 영역: `bg-surface-container-lowest font-mono text-sm`
- 구문 강조:
  - 키: `text-primary`
  - 값: `text-tertiary`
  - 주석: `text-secondary`
  - 에러: `text-error`
  - 기타: `text-slate-500`

#### Remediation Audit Log (우하단)
- 타임라인 형태 (세로 연결선)
- 각 스텝: `flex gap-4`
- 완료 아이콘: `w-8 h-8 rounded-full bg-tertiary/10 border border-tertiary/20`
- 진행 중: `bg-primary/20 border border-primary/40 animate-pulse`
- 단계 라벨: `font-mono text-tertiary` (Detect, Diagnose, Test SQL, Apply Index)

---

### 4.3 Screen 3: 1s ASH & Wait Event Explorer

**파일**: `screen3_ash.html`
**스크린샷**: `screenshots/screen3_ash.png`

#### Temporal Zoom (시간 범위 선택)
- 해상도 버튼 그룹: `bg-surface-container-high rounded-lg p-1`
  - 활성: `bg-primary-container text-on-primary-container rounded`
  - 비활성: `text-slate-400`
- 미니 바 차트: 높이별 `bg-slate-800`, `bg-sky-900`, `bg-sky-500`, `bg-primary-container`
- Zoom 슬라이더: `bg-primary/10 border-x-2 border-primary`

#### ASH Heatmap
- 4행 x 24열 그리드: `grid-cols-24 grid-rows-4 gap-1 h-48`
- 행 라벨: Network, I/O, Lock, CPU
- 범례: Idle, I/O, CPU, Lock, Critical
- 셀 색상 매핑:
  - Idle: `bg-surface-variant`
  - I/O: `bg-sky-900` ~ `bg-sky-500`
  - Lock: `bg-orange-900` ~ `bg-orange-400` ~ `bg-error`
  - CPU: `bg-secondary-container` (opacity 20-100%)
- Hover 효과: `transform: scale(1.1); z-index: 10;` (`ease-out`)

#### Session Detail Table
- 헤더: `bg-surface-container-high/50 text-slate-400 text-[10px] uppercase tracking-widest`
- 컬럼: PID, Query Snippet, State, Wait Event, Duration, Action
- 상태 뱃지:
  - Locked: `bg-orange-900/40 text-orange-400 rounded-full`
  - Active: `bg-sky-900/40 text-sky-400 rounded-full`
  - Running: `bg-secondary-container/40 text-secondary rounded-full`
- 선택된 행: `bg-primary/5`
- Explain 버튼: `opacity-0 group-hover:opacity-100` 트랜지션

#### 우측 사이드바: Wait Breakdown
- 프로그레스 바 3개: Lock(45%), Disk I/O(30%), CPU(25%)
- 각 바: `h-2 rounded-full` + glow shadow
- AI Insights 카드: `bg-secondary-container/20 border border-secondary/20`

#### AI Interpretation 플로팅 카드
- `fixed bottom-10 right-96 w-96`
- `glass-panel rounded-xl shadow-2xl border border-primary/20`
- SQL 추천: `bg-surface-container-lowest p-3 rounded-lg`
- 버튼: Execute Fix / Ignore

---

### 4.4 Screen 4: AI Diagnosis & RCA Panel

**파일**: `screen4_diagnosis.html`
**스크린샷**: `screenshots/screen4_diagnosis.png`

#### Active Incidents (좌측 col-span-4)
- 제목: `font-headline text-xl font-bold`
- "Live Feed" 라벨: `text-xs font-mono text-outline uppercase`

| 심각도 | 뱃지 | 카드 스타일 |
|--------|------|-------------|
| Critical | `bg-error text-on-error` | `bg-error-container/10 border border-error/20 ring-1 ring-error/10` + 좌측 `w-1 bg-error` 라인 |
| Warning | `bg-amber-500/20 text-amber-400 border border-amber-500/30` | `bg-surface-container-high` |
| Resolved | `bg-tertiary/20 text-tertiary border border-tertiary/30` | `bg-surface-container-high opacity-60` |

#### AI Root Cause Analysis (우측 col-span-8)
- 컨테이너: `glass-panel p-8 rounded-2xl border border-secondary/10`
- AI 아이콘: `w-12 h-12 rounded-full bg-secondary-container shadow-[0_0_20px_rgba(208,188,255,0.2)]`
- 제목: `font-headline text-2xl font-bold`
- 엔진 정보: `text-sm text-secondary/70` ("Neural-Insight-v4.2 | Confidence: 94%")
- 진단 카드: `bg-surface-container-lowest rounded-xl border-l-4 border-secondary p-6`

#### 참조/제안 그리드 (2열)
```
grid-cols-2 gap-4
```
- RAG Reference 카드: `bg-surface-container rounded-lg border border-white/5`
- Optimization Suggestion 카드: 동일 스타일

#### Causal Inference Chain (인과 관계 시각화)
- 수평 연결선: `bg-gradient-to-r from-transparent via-outline-variant to-transparent`
- 4개 노드: Schema Change → Sequential Scan → Lock Wait → Latency Spike
- 노드 크기: `w-14 h-14 rounded-full`
- 노드 색상: primary → amber → secondary → error

#### Action Buttons
```
┌──────────────────┐ ┌──────────────────┐ ┌────────────────────────┐
│ Generate Playbook│ │ Auto-Tune Index  │ │ View SQL Recommendation│
│ (primary-cont.)  │ │ (secondary-cont.)│ │ (surface-variant)      │
└──────────────────┘ └──────────────────┘ └────────────────────────┘
```

#### NL2SQL Floating Chat
- 위치: `fixed bottom-8 right-8 w-80`
- 헤더: `bg-secondary-container text-on-secondary-container`
- 채팅 영역: `bg-surface-container-lowest/50 h-64`
- 사용자 메시지: `bg-surface-variant rounded-xl rounded-tr-none`
- AI 응답: `bg-secondary-container/10 border border-secondary/20 rounded-xl rounded-tl-none`
- 입력: `bg-surface-container rounded-lg border border-outline-variant/30`

---

## 5. Component Library Summary

### 5.1 Buttons

| 유형 | 스타일 |
|------|--------|
| Primary | `bg-primary-container text-on-primary-container font-bold rounded-lg` |
| Secondary (AI) | `bg-secondary-container text-on-secondary-container font-bold rounded-lg` |
| Tertiary/Ghost | `bg-surface-variant text-on-surface-variant border border-outline-variant rounded-lg` |
| Danger | `bg-error/10 text-error border border-error/20 rounded` |
| Text Only | `text-primary hover:underline` |

**인터랙션**: `hover:brightness-110 active:scale-95 transition-all` 또는 `hover:opacity-90`

### 5.2 Cards

| 유형 | 스타일 |
|------|--------|
| Summary Card | `bg-surface-container p-5 rounded-xl border-l-4 shadow-sm` |
| Glass Card | `glass-panel rounded-xl border border-white/5` |
| Alert Card | `bg-error-container/10 border border-error/20 ring-1 ring-error/10` |
| AI Insight Card | `bg-secondary-container/10 border-l-4 border-secondary rounded-xl` |
| Data Card | `bg-surface-container-high p-4 rounded-xl border border-white/5` |

### 5.3 Status Badges

```html
<!-- Critical -->
<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-error text-on-error uppercase">Critical</span>

<!-- Warning -->
<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30 uppercase">Warning</span>

<!-- Success/Resolved -->
<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-tertiary/20 text-tertiary border border-tertiary/30 uppercase">Resolved</span>

<!-- AI/Predictive -->
<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-secondary/20 text-secondary uppercase tracking-widest">Predictive</span>

<!-- Info/Active -->
<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-sky-900/40 text-sky-400 uppercase">Active</span>
```

### 5.4 Progress Bars

```html
<!-- Standard -->
<div class="h-2 bg-surface-variant rounded-full overflow-hidden">
  <div class="h-full bg-primary rounded-full shadow-[0_0_12px_rgba(14,165,233,0.5)]" style="width: 75%"></div>
</div>

<!-- Metric Bar with Glow -->
<div class="h-2 w-full bg-surface-variant rounded-full overflow-hidden">
  <div class="h-full bg-orange-500 shadow-[0_0_8px_rgba(249,115,22,0.4)]" style="width: 45%"></div>
</div>
```

### 5.5 Input Fields

```html
<!-- Search Input -->
<div class="bg-surface-container-highest px-4 py-1.5 rounded-full flex items-center gap-2">
  <span class="material-symbols-outlined text-outline text-sm">search</span>
  <input class="bg-transparent border-none focus:ring-0 text-sm w-48 text-on-surface-variant" placeholder="Search..." />
</div>

<!-- Chat Input -->
<div class="flex items-center gap-2 bg-surface-container rounded-lg px-3 py-2 border border-outline-variant/30">
  <input class="bg-transparent border-none focus:ring-0 text-xs flex-1 text-on-surface" placeholder="Ask..." />
  <span class="material-symbols-outlined text-primary text-sm cursor-pointer">send</span>
</div>
```

### 5.6 Timeline (Audit Log)

```html
<div class="flex gap-4 relative">
  <!-- Vertical Line -->
  <div class="absolute left-4 top-8 bottom-[-24px] w-px bg-white/5"></div>
  <!-- Status Icon -->
  <div class="z-10 w-8 h-8 rounded-full bg-tertiary/10 border border-tertiary/20 flex items-center justify-center shrink-0">
    <span class="material-symbols-outlined text-tertiary text-sm">check</span>
  </div>
  <!-- Content -->
  <div class="pb-6">
    <p class="text-xs font-mono text-tertiary mb-1">[Step Name]</p>
    <p class="text-sm text-slate-200">Description</p>
    <p class="text-[10px] text-slate-500 mt-1">Timestamp</p>
  </div>
</div>
```

### 5.7 Tooltip
| 스타일 | 값 |
|--------|---|
| 배경 | `bg-surface-container-highest rounded-lg px-3 py-2 shadow-lg` |
| 텍스트 | `text-xs text-on-surface` |
| 화살표 | CSS triangle `border-4 border-transparent border-t-surface-container-highest` |
| 지연 | Hover 후 300ms |
| 위치 | top (기본), bottom, left, right |

### 5.8 Toast / Notification
| Variant | 좌측 아이콘 | 배경 | Border |
|---------|-----------|------|--------|
| success | check_circle (tertiary) | `bg-surface-container-high` | `border-l-4 border-tertiary` |
| error | error (error) | `bg-surface-container-high` | `border-l-4 border-error` |
| warning | warning (amber-500) | `bg-surface-container-high` | `border-l-4 border-amber-500` |
| info | info (primary) | `bg-surface-container-high` | `border-l-4 border-primary` |

- 위치: `fixed top-4 right-4 z-50`
- 애니메이션: fade-in 200ms, auto-dismiss 5초, fade-out 300ms
- 최대 3개 스택

### 5.9 Modal / Dialog
| 요소 | 스타일 |
|------|--------|
| Backdrop | `fixed inset-0 bg-black/50 backdrop-blur-sm z-50` |
| 컨테이너 | `glass-panel rounded-2xl shadow-2xl max-w-lg mx-auto` |
| 헤더 | `px-6 py-4 border-b border-white/5 font-headline text-lg font-bold` |
| 바디 | `px-6 py-4` |
| 푸터 | `px-6 py-4 border-t border-white/5 flex justify-end gap-3` |
| 닫기 | `absolute top-4 right-4` 아이콘 버튼 |
| 크기 | sm: `max-w-sm`, md: `max-w-lg`, lg: `max-w-2xl`, full: `max-w-5xl` |

### 5.10 Tabs
| 상태 | 스타일 |
|------|--------|
| 활성 탭 | `text-primary border-b-2 border-primary font-semibold` |
| 비활성 탭 | `text-on-surface-variant hover:text-on-surface` |
| 컨테이너 | `flex gap-6 border-b border-white/5 mb-6` |
| 탭 패딩 | `pb-3 px-1 text-sm cursor-pointer transition-colors` |

### 5.11 Spinner / Loader
| 크기 | 스타일 |
|------|--------|
| sm | `w-4 h-4 border-2 border-primary/30 border-t-primary rounded-full animate-spin` |
| md | `w-8 h-8 border-3 border-primary/30 border-t-primary rounded-full animate-spin` |
| lg | `w-12 h-12 border-4 border-primary/30 border-t-primary rounded-full animate-spin` |

### 5.12 Skeleton (Loading Placeholder)
| 요소 | 스타일 |
|------|--------|
| 기본 | `bg-surface-container-high rounded animate-pulse` |
| 텍스트 | `h-4 rounded` |
| 원형 | `rounded-full` |
| 시머 | `@keyframes shimmer { from { transform: translateX(-100%) } to { transform: translateX(100%) } }` 1.5s ease-in-out infinite |
| 오버레이 | `bg-gradient-to-r from-transparent via-white/5 to-transparent` |

### 5.13 Dropdown / Select
| 요소 | 스타일 |
|------|--------|
| 트리거 | `bg-surface-container-high px-3 py-2 rounded-lg border border-outline-variant/30 text-sm` |
| 메뉴 | `bg-surface-container-highest rounded-lg shadow-lg border border-white/5 py-1 z-50` |
| 옵션 | `px-3 py-2 text-sm hover:bg-surface-bright cursor-pointer` |
| 선택됨 | `text-primary font-medium` |
| 비활성 | `text-outline opacity-50 cursor-not-allowed` |

### 5.14 DataTable 헤더
| 요소 | 스타일 |
|------|--------|
| 헤더 행 | `bg-surface-container-high/50` |
| 헤더 셀 | `text-[10px] font-bold uppercase tracking-widest text-slate-400 px-4 py-3` |
| 정렬 화살표 | `material-symbols-outlined text-xs ml-1` (arrow_upward / arrow_downward) |
| 바디 행 | `border-b border-white/5 hover:bg-surface-bright/50 transition-colors` |
| 바디 셀 | `px-4 py-3 text-sm text-on-surface` |
| 선택된 행 | `bg-primary/5` |

---

## 6. Icon System

**Library**: Google Material Symbols Outlined
**CDN**: `https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1`

### 주요 아이콘 매핑

| 기능 | 아이콘 | Fill |
|------|--------|------|
| Dashboard | `dashboard` | 0 |
| Topology | `hub` | 0 |
| Diagnosis | `troubleshoot` | 0 |
| ASH Explorer | `analytics` | 0 |
| Playbook | `menu_book` | 0 |
| Settings | `settings` | 0 |
| AI/ML | `auto_awesome` | 1 |
| Search | `search` | 0 |
| Notifications | `notifications` | 0 |
| Database | `database` | 0/1 |
| Chart | `show_chart` | 0 |
| Psychology/AI | `psychology` | 0 |
| Terminal | `terminal` | 0 |
| Lock | `lock` | 0/1 |
| Warning | `warning` | 0 |
| Timer | `timer` | 0 |
| NL2SQL | `bolt` / `smart_toy` | 0 |

---

## 7. Responsive Breakpoints

| Breakpoint | 적용 |
|-----------|------|
| `md` (768px) | TopNav 탭 표시, Summary 카드 4열 |
| `lg` (1024px) | Playbook/Audit 분할 (7:5) |
| 기본 | 단일 컬럼 스택 |

---

## 8. Tech Stack (Reference)

| 기술 | 용도 |
|------|------|
| Tailwind CSS | 유틸리티 기반 스타일링 |
| Material Symbols | 아이콘 시스템 |
| Space Grotesk (Google Fonts) | 헤드라인 폰트 |
| Inter (Google Fonts) | 본문/데이터 폰트 |
| JetBrains Mono | 코드/쿼리 폰트 |

---

---

## 9. Screen 5: Full-Stack Topology Explorer (NEW)

**파일**: `screen5_topology_explorer.html`
**스크린샷**: `screenshots/screen5_topology_explorer.png`
**Stitch ID**: `c1d6510c7b8e47f5a1be5f1de5dd0f63`

Screen 1(Dashboard 토폴로지)의 **전용 확장 뷰**. 토폴로지 탐색에 특화.

#### 주요 컴포넌트
- **탭 바**: Cluster / Region / Environment 필터
- **토폴로지 그래프**: App(Auth-Service, Billing-API) → Core Gateway → Primary DB → Read-Replica 연결
  - 노드에 `LIVE` 뱃지, 메트릭(TPS, CPU Usage, Connections) 표시
  - Drift 감지: "Read-Replica-S2 was added manually via CLI" 알림 바
- **Node Inspector (우측 패널)**:
  - 선택 노드 상세 (Primary DB: Throughput 12.8 GB/s, Error Rate 0.00%)
  - OTel Trade Summary: 쿼리별 지연 시간 테이블
  - Blast Radius Analysis: 영향 범위 + 예상 다운타임 비용
  - "Simulate Outage" 버튼
- **하단 타임라인**: Normal Operations 구간 + Drift 이벤트 마커
- **Detailed Logs**: 노드별 활동 로그

---

## 10. Screen 6: Add New Database Wizard (NEW)

**파일**: `screen6_add_database.html`
**스크린샷**: `screenshots/screen6_add_database.png`
**Stitch ID**: `2298731d0ed243ffae18fb7a371b2ebc`

새 DB 인스턴스 등록 마법사. Settings 메뉴에서 진입.

#### 레이아웃
- 제목: "Connect New Intelligence" (font-headline text-4xl)
- 부제: "Initialize a new neural node in your database cluster."
- 좌측: 3단계 스텝 인디케이터 (TYPE → CONNECTION → OPTIONS)

#### Step 1: Database Architecture
- DB 타입 선택 카드 3개: **PostgreSQL** (선택됨, primary 강조) / MySQL / MS-SQL
- 카드 스타일: `bg-surface-container-high` 선택 시 `border-primary`

#### Step 2: Network & Authentication
| 필드 | 컴포넌트 |
|------|---------|
| Host Address | Input (`bg-surface-container-lowest`, Ghost Border) |
| Port | Input (default: 5432) |
| Database User | Input |
| Password | Input (마스킹 + 토글 아이콘) |
| SSL Connection Required | Toggle 스위치 (tertiary 색상) |

#### Step 3: Intelligence Configuration
- **Enable 1s ASH Explorer** — 체크박스 + `WARNING` 뱃지 (amber)
  - "Capture active session history every second for millisecond-level diagnosis"
- **Enable Autonomous Tuning** — 체크박스 + `ADVANCED` 뱃지 (secondary)
  - "Allow NeuralDB to automatically adjust buffer pools and index recommendations"

#### 하단 액션
- "Test Connection" 버튼 (tertiary, 좌측)
- "Cancel" 텍스트 버튼
- "Save & Start Monitoring" 버튼 (primary-container, 우측)

---

## 11. Screen 7: AI Diagnosis Use Case & User Flow (NEW)

**파일**: `screen7_diagnosis_flow.html`
**Stitch ID**: `6a406d7a43b84fb381a73dc7a45dc69b`
**스크린샷**: 없음 (문서형 화면)

AI 진단 사용 시나리오와 사용자 플로우를 정의한 UX 문서형 화면.

---

## 12. File Structure

```
docs/
├── FRONTEND_DESIGN.md              ← 이 문서
├── screen1_topology.html           ← Full-Stack Topology Dashboard
├── screen2_selfhealing.html        ← Self-Healing & Playbook Management
├── screen3_ash.html                ← 1s ASH & Wait Event Explorer
├── screen4_diagnosis.html          ← AI Diagnosis & RCA Panel
├── screen5_topology_explorer.html  ← Full-Stack Topology Explorer (NEW)
├── screen6_add_database.html       ← Add New Database Wizard (NEW)
├── screen7_diagnosis_flow.html     ← AI Diagnosis User Flow (NEW)
└── screenshots/
    ├── screen1_topology.png
    ├── screen2_selfhealing.png
    ├── screen3_ash.png
    ├── screen4_diagnosis.png
    ├── screen5_topology_explorer.png  (NEW)
    └── screen6_add_database.png       (NEW)
```

---

## Changelog

| 날짜 | 변경 |
|------|------|
| 2026-03-21 | 초기 작성 (Screen 1~4, Stitch 프로젝트 동기화) |
| 2026-03-21 | **Stitch Sync**: Screen 5(Topology Explorer), Screen 6(Add DB Wizard), Screen 7(Diagnosis Flow) 추가. 디자인 토큰 변경 없음 |

---

## v3.3 신규 컴포넌트 (Explainable AI / LLM Observability)

### Confidence Badge 컴포넌트

신뢰도 수준별 색상 배지. 모든 AI 판단 결과 옆에 표시.

| Confidence 범위 | 등급 | 배경색 | 텍스트색 | 아이콘 |
|----------------|------|--------|---------|-------|
| 0.8 ~ 1.0 | HIGH | `tertiary-container` (#00b17b) | `on-tertiary-container` | check_circle |
| 0.5 ~ 0.79 | MEDIUM | `warning-container` (#665500) | `on-warning-container` | help |
| 0.3 ~ 0.49 | LOW | `error-container` (#93000a) 20% | `error` (#ffb4ab) | warning |
| 0.0 ~ 0.29 | VERY_LOW | `error-container` (#93000a) | `on-error-container` | error |

### Reasoning Chain 펼침 패널

인시던트 상세 페이지에서 Confidence Badge 클릭 시 확장되는 패널.

- **배경**: `surface-container-high` (#222a3d)
- **스텝 번호**: `primary` (#89ceff) + 원형 배지
- **스텝 텍스트**: `on-surface` (#e2e2e9)
- **근거 태그**: `secondary` (#d0bcff) 칩 (metric / ash / query / rag)
- **데이터 포인트**: `on-surface-variant` (#c5c6d0) monospace (JetBrains Mono)
- **피드백 버튼**: 👍 `tertiary` / 👎 `error` 아이콘 버튼

### AI Health 위젯 (System Health 탭 내)

LLM Observability 대시보드 위젯 4개 세트.

| 위젯 | 차트 유형 | 색상 |
|------|----------|------|
| 토큰 사용량 | Progress bar + 일별 ECharts line | `primary` (#89ceff) |
| 응답 지연 | P50/P95/P99 ECharts line | `secondary` (#d0bcff) |
| 정확도 트렌드 | 주간 ECharts area | `tertiary` (#4edea3) |
| 할루시네이션 비율 | ECharts gauge | `error` (#ffb4ab) |
