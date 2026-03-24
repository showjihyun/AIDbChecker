# Design System — NeuralDB

## Product Context
- **What this is:** AI 기반 지능형 DB 모니터링 시스템. 1초 해상도 메트릭 수집 + ASH 히트맵 + AI 이상 탐지
- **Who it's for:** 사내 인프라 담당자 (DBA/SRE). 주 1회 장애 대응, 원인 특정이 핵심 니즈
- **Space/industry:** DevOps/DB 모니터링 (Datadog DBM, pganalyze, Percona PMM 계열)
- **Project type:** Data-dense dashboard (App UI) — 실시간 메트릭, ASH 히트맵, 인시던트

## Aesthetic Direction
- **Direction:** Industrial/Utilitarian + Retro-Futuristic hybrid ("The Digital Synapse")
- **Decoration level:** Intentional — Neural Grid, Glassmorphism, AI Shimmer는 "살아있음" 신호로만
- **Mood:** 관제실 안에서 신경망을 들여다보는 느낌. 고밀도 데이터를 고대비 타이포와 대기적 깊이로 표현
- **Reference style:** 의도적 비대칭, 겹치는 글래스 레이어, 색상은 의미 기반만 사용

## Typography
- **Display/Hero:** Space Grotesk 700 — 시네마틱 에디토리얼 느낌. 카테고리 차별화 포인트
- **Body/Data:** Inter 400-500 — 정밀한 데이터 표현, 가독성 최적
- **UI/Labels:** Inter 600-700 — 본문과 동일 패밀리, 웨이트로 구분
- **Data/Tables:** Inter (tabular-nums) — 숫자 정렬
- **Code:** JetBrains Mono 400 — SQL/YAML 구문 강조 시 secondary-fixed-dim (#d0bcff)
- **Loading:** Google Fonts CDN
- **Scale:**
  - display-lg: 3.5rem (56px) / Space Grotesk 700 / -0.02em
  - headline-md: 1.75rem (28px) / Space Grotesk 700 / -0.02em
  - headline-sm: 1.25rem (20px) / Space Grotesk 700 / tight
  - body: 0.875rem (14px) / Inter 400 / normal
  - label: 0.75rem (12px) / Inter 600 / wider
  - code: 0.75-0.875rem / JetBrains Mono 400 / normal

## Color
- **Approach:** Balanced (dark only)
- **Surfaces:**
  - `--surface`: #0b1326 (Infinite Void — 최하단 배경)
  - `--surface-container-lowest`: #060e20
  - `--surface-container-low`: #131b2e (내비게이션)
  - `--surface-container`: #171f33 (카드 기본)
  - `--surface-container-high`: #222a3d (활성 카드)
  - `--surface-container-highest`: #2d3449 (최상위)
  - `--surface-bright`: #31394d (Hover)
- **Primary:** #0ea5e9 (Cyber Blue) — 주요 인터랙션, 버튼, 링크
  - on-primary: #00344d
  - primary-light: #89ceff (텍스트 강조)
- **Secondary:** #d0bcff (AI Violet) — AI/ML 관련 UI 전용
  - secondary-container: #571bc1
  - 일반 UI에 보라색 확산 금지
- **Tertiary:** #4edea3 (Emerald) — 건강/성공 상태
  - tertiary-container: #00b17b
- **Error:** #ffb4ab (Rose) — DB 장애, Critical
  - error-container: #93000a
- **Warning:** #f59e0b (Amber)
- **Text:**
  - on-surface: #dae2fd (기본)
  - on-surface-variant: #bec8d2 (보조)
  - outline: #88929b (경계)
  - outline-variant: rgba(62,72,80,0.15) (Ghost Border)
- **Dark mode:** 전용. 라이트 모드는 Phase 2

## Spacing
- **Base unit:** 8px
- **Density:** Comfortable
- **Scale:** 2xs(2px) xs(4px) sm(8px) md(16px) lg(24px) xl(32px) 2xl(48px) 3xl(56px/3.5rem)
- **Module gap:** 3.5rem (56px) — Dashboard Fatigue 방지
- **Card padding:** p-5(20px) ~ p-8(32px)

## Layout
- **Approach:** Grid-disciplined (App UI)
- **Structure:**
  - TopNav: h-16 (64px), fixed, z-50
  - SideNav: w-64 (256px), fixed, z-40
  - Main: ml-64, pt-24, px-8
- **Grid:** 12-column (1280px+), 8-column (1024-1279px)
- **Max content width:** 1600px
- **Border radius:**
  - xs: 2px (DEFAULT)
  - sm: 4px (lg)
  - md: 8px (xl) — Card default
  - lg: 12px (full)
  - xl: 16px (2xl) — Highlighted card
- **Responsive (Demo v1):**
  - 1280px+: 풀 레이아웃
  - 1024-1279px: SideNav 접힘 (w-16, 아이콘 전용)
  - <1024px: "데스크톱 환경 권장" 배너

## Motion
- **Approach:** Minimal-functional
- **Easing:** enter(ease-out) exit(ease-in) move(ease-in-out)
- **Duration:** micro(50-100ms) short(150-250ms) medium(250-400ms)
- **Rules:**
  - 탄성/바운스 애니메이션 금지
  - ease-out 전환만 사용
  - AI Shimmer (rgba(208,188,255,0.1) gradient) = AI 카드 유일한 장식 모션
  - Neural Glow (box-shadow 0 0 40px rgba(14,165,233,0.08)) = 미세한 ambient

## Effects
- **Glassmorphism:** rgba(45,52,73,0.6) + backdrop-filter: blur(24px) — 모달/팝오버
- **Glass Card:** rgba(34,42,61,0.4) + backdrop-filter: blur(24px) — 토폴로지 노드
- **Neural Grid:** radial-gradient(circle at 1px 1px, rgba(14,165,233,0.05) 1px, transparent 0) 40px 40px — 배경 패턴
- **Neural Glow:** box-shadow: 0 0 40px rgba(14,165,233,0.08) — Ambient shadow
- **AI Shimmer:** linear-gradient(90deg, transparent, rgba(208,188,255,0.1), transparent) — AI 카드
- **Ghost Border:** 1px solid rgba(62,72,80,0.15) — 15% opacity 경계

## Design Rules
- **No-Line Rule:** 1px solid border 금지 (섹션 구분 용도). Surface Hierarchy로 영역 구분
- **No pure black:** #000000 금지. 최소 #0b1326
- **Color = meaning only:** 장식용 색상 금지. 모든 색상은 상태/기능을 나타냄
- **bg-decoration:** 대시보드에서 최대 1개만. 2개 이상 = 장식 과잉
- **비대칭 배치:** 카드 높이 비율 — 인스턴스 ~30%, 차트 ~45%, 히트맵 ~25%

## Component Tokens

| Component | Variant | BG | Text | Radius | Height |
|-----------|---------|-----|------|--------|--------|
| Button | primary/filled | --primary-container (#0ea5e9) | --on-primary (#00344d) | xl (8px) | 40px |
| Button | ghost/outline | transparent | --primary (#89ceff) | xl (8px) | 40px |
| Badge | healthy | tertiary/15% | --tertiary (#4edea3) | full (12px) | 24px |
| Badge | critical | error/15% | --error (#ffb4ab) | full | 24px |
| Badge | warning | amber/15% | amber-500 (#f59e0b) | full | 24px |
| Badge | ai/predictive | secondary/15% | --secondary (#d0bcff) | full | 24px |
| Input | default | --surface-container (#171f33) | --on-surface (#dae2fd) | sm (4px) | 40px |
| Toast | success | --tertiary-container (#00b17b) | --on-surface | xl (8px) | auto |
| Toast | error | --error-container (#93000a) | --on-surface | xl | auto |
| Card | default | --surface-container (#171f33) | --on-surface | xl (16px) | auto |
| Card | active | --surface-container-high (#222a3d) | --on-surface | xl (16px) | auto |

## Interaction States

| Feature | Loading | Empty | Error | Success |
|---------|---------|-------|-------|---------|
| Instance cards | Skeleton 3개 (pulse) | "인스턴스를 등록하세요" + [등록] | "서버 연결 실패" + [재시도] | 카드 표시 |
| Instance status | — | — | 빨간 dot + "수집 중단" | 초록 dot |
| Metric chart | Skeleton 300px | "수집 대기 중..." 점선 윤곽 | "데이터 로드 실패" + [재시도] | 차트 렌더 |
| ASH heatmap | Skeleton 그리드 | "세션 데이터 없음" 회색 윤곽 | "ASH 조회 실패" + [재시도] | 히트맵 렌더 |
| WebSocket | "연결 중..." 배지 | — | "연결 끊김" 주황 배지 | 배지 숨김 |
| Instance form | [등록 중...] disabled | — | 필드 하이라이트 + 메시지 | "등록 완료" 토스트 |
| Alert banner | — | 숨김 (정상) | — | — |

## Information Hierarchy (장애 시)
```
시선 흐름: ① 알림 배너 → ② 인스턴스 카드 (어디?) → ③ 메트릭 차트 (언제부터?) → ④ ASH 히트맵 (무엇이?)
장애 없을 때: ①숨김, ②부터 시작
```

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-24 | DESIGN.md 생성 | /design-consultation — FRONTEND_DESIGN.md를 gstack 표준으로 통합 |
| 2026-03-24 | 다크 전용 (라이트 Phase 2) | 모니터링 도구 표준 + 사용자 1명 데스크톱 환경 |
| 2026-03-24 | No-Line Rule 채택 | Surface Hierarchy가 border보다 고급스럽고 Glassmorphism과 일관 |
| 2026-03-24 | Space Grotesk 헤드라인 | 카테고리 차별점. 에디토리얼 느낌으로 "관제 영화" 분위기 |
| 2026-03-24 | secondary(#d0bcff) AI 전용 | AI Slop 방지. 보라색이 일반 UI에 확산되면 "AI가 만든 느낌" |
| 2026-03-24 | bg-decoration 최대 1개 | 장식 과잉 방지 |
| 2026-03-24 | 히트맵 기본 30분 | 장애 대응 시 최근 30분이 가장 유용 |
| 2026-03-24 | 카드 클릭 → 하단 차트 전환 | 별도 페이지 이동 시 맥락 손실 |
| 2026-03-24 | 알림 배너 닫기 가능 + SideNav dot | 배너 닫아도 장애 인지 유지 |
| 2026-03-24 | 시간 범위 프리셋 버튼 | 15분/1시간/6시간/24시간/7일. 드롭다운보다 직관적 |
