# AI-Powered Intelligent DB Monitoring System

## Project Requirements Document (PRD) v3.3

**프로젝트 요구사항 문서**

| 항목 | 내용 |
|------|------|
| 문서명 | AI-Powered Intelligent DB Monitoring System PRD |
| 버전 | v3.3 |
| 작성일 | 2026-03-23 |
| 보안 등급 | CONFIDENTIAL |
| 대상 DB | PostgreSQL (Default), MySQL, MS-SQL (확장) |
| 배포 환경 | 온프레미스 / 클라우드 / 하이브리드 |
| 개발 방법론 | **Spec-Driven Harness Engineering** |
| 기술 스택 | React (FE) + Python/FastAPI (BE) + PostgreSQL 16 (DB) |

---

## 목차

1. [문서 개요](#1-문서-개요)
2. [개발 방법론: Spec-Driven Harness Engineering](#2-개발-방법론-spec-driven-harness-engineering)
3. [프로젝트 범위](#3-프로젝트-범위)
4. [차별화 전략](#4-차별화-전략)
5. [기능 요구사항](#5-기능-요구사항)
6. [모니터링 카테고리 상세](#6-모니터링-카테고리-상세)
7. [비기능 요구사항](#7-비기능-요구사항)
8. [기술 스택](#8-기술-스택)
9. [프로젝트 일정](#9-프로젝트-일정)
10. [제약 조건 및 위험 요소](#10-제약-조건-및-위험-요소)
11. [인수 기준](#11-인수-기준)
12. [부록](#12-부록)

---

## 1. 문서 개요

### 1.1 문서 목적

본 문서는 AI/LLM 기반 지능형 데이터베이스 모니터링 시스템 구축을 위한 프로젝트 요구사항 문서(PRD)입니다. 시스템의 범위, 기능 요구사항, 비기능 요구사항, 기술 스택, 프로젝트 일정, 제약 조건 등을 정의하여 개발팀, 기획팀, 이해관계자 간의 공통된 이해를 보장합니다.

> **핵심 원칙**: 본 프로젝트는 **Spec-Driven Harness Engineering** 방법론으로 진행합니다. 모든 구현은 반드시 사전에 정의된 Spec 문서를 기반으로 하며, Spec에 명시되지 않은 기능은 구현하지 않습니다. AI 하네스(Claude Code)가 Spec을 해석하고 코드를 생성하되, Spec이 곧 진실의 원천(Single Source of Truth)입니다.

---

## 2. 개발 방법론: Spec-Driven Harness Engineering

### 2.1 방법론 선언

> **본 프로젝트는 Spec-Driven Harness Engineering 방법론을 채택하며, 모든 참여자(인간 개발자, AI 하네스)는 이를 준수해야 한다.**

**Spec-Driven Harness Engineering**이란, AI 코드 생성 도구(하네스)를 활용하되 **Specification(사양서)이 모든 개발 활동의 유일한 출발점이자 검증 기준**이 되는 개발 방법론입니다.

```
┌─────────────────────────────────────────────────────────────────┐
│                  Spec-Driven Harness Engineering                 │
│                                                                  │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│   │  1.SPEC  │───▶│ 2.SKILL  │───▶│ 3.HARNESS│───▶│ 4.VERIFY │  │
│   │  정의     │    │  준비     │    │  생성     │    │  검증     │  │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│        │                                               │         │
│        └───────────── Spec 준수 피드백 루프 ──────────────┘         │
│                                                                  │
│   Spec ≠ 코드에서 추출  │  Spec = 코드보다 먼저 존재                │
│   코드 ≠ 자유 구현      │  코드 = Spec의 구현체                    │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 핵심 원칙 (MUST FOLLOW)

| 원칙 | 설명 | 위반 시 |
|------|------|---------|
| **Spec-First** | 코드 작성 전에 반드시 해당 기능의 Spec이 존재해야 한다. Spec이 없으면 구현하지 않는다. | 구현 중단, Spec 작성 후 재개 |
| **Spec-as-Contract** | Spec은 인간 개발자와 AI 하네스 간의 계약이다. 양측 모두 Spec에 명시된 인터페이스, 데이터 모델, 동작 규격을 준수해야 한다. | 코드 리뷰에서 거부 |
| **Spec-Verified** | 구현 완료 후 반드시 Spec 대비 검증을 수행한다. Spec에 정의된 인수 기준(Acceptance Criteria)을 만족해야 완료로 인정한다. | 완료 판정 불가 |
| **Spec-Evolved** | Spec은 불변이 아니다. 요구사항 변경 시 Spec을 먼저 수정하고, 변경된 Spec에 따라 코드를 수정한다. 코드를 먼저 바꾸고 Spec을 나중에 맞추는 것은 금지한다. | 롤백 후 Spec 수정 선행 |
| **No Spec-Free Code** | Spec에 명시되지 않은 기능, 최적화, 리팩토링은 AI 하네스가 임의로 수행하지 않는다. | 해당 코드 삭제 |

### 2.3 Spec 문서 체계

본 프로젝트의 Spec은 다음 계층으로 구성되며, 상위 문서가 하위 문서보다 우선합니다.

```
Level 0: PRD (이 문서)
  └── Level 1: Architecture Spec (아키텍처 설계 사양서)
        └── Level 2: Feature Specs (기능별 상세 사양)
              ├── API Spec (OpenAPI/GraphQL Schema)
              ├── Data Model Spec (ERD, SQLAlchemy Models)
              ├── UI/UX Spec (디자인 토큰, 컴포넌트 사양)
              └── Agent Spec (에이전트 행동 규격)
                    └── Level 3: Test Spec (테스트 시나리오)
```

| Spec 문서 | 위치 | 역할 |
|-----------|------|------|
| **PRD** | `AI_DB_Monitoring_System_PRD_v3.3.md` | 프로젝트 범위, 요구사항, 인수 기준 정의 |
| **Architecture Spec** | `ai-db-monitor-architecture-spec-v3.md` | 시스템 아키텍처, 레이어 구조, 모듈 경계, 데이터 흐름 |
| **Tech Stack Spec** | `docs/TECH_STACK.md` | 기술 스택, 버전, 라이선스, 디렉토리 구조 |
| **Frontend Design Spec** | `docs/FRONTEND_DESIGN.md` | 디자인 토큰, 컴포넌트 사양, 화면별 레이아웃 |
| **API Spec** | `docs/specs/api/` | OpenAPI 3.1 YAML, Strawberry GraphQL Schema |
| **Data Model Spec** | `docs/specs/data-model/` | ERD, 테이블 정의, 인덱스 전략, 파티셔닝 정책 |
| **Agent Spec** | `docs/specs/agents/` | 에이전트별 역할, 입출력, 상태 머신, 자율 등급 |
| **Playbook Spec** | `docs/specs/playbooks/` | Playbook YAML 스키마, 트리거 조건, 실행 규격 |
| **Test Spec** | `docs/specs/tests/` | 테스트 시나리오, 커버리지 목표, E2E 플로우 |

### 2.4 하네스 엔지니어링 워크플로우

#### Phase 1: Spec 정의 (인간 주도)

```
인간 개발자 → Spec 문서 작성/수정
  ├── 기능 요구사항 정의 (WHAT)
  ├── 인터페이스 계약 정의 (HOW - API, Schema, Protocol)
  ├── 인수 기준 정의 (DONE - 테스트 시나리오)
  └── 제약 조건 명시 (CONSTRAINT - 라이선스, 성능, 보안)
```

#### Phase 2: Skill 준비 (인간 + AI 협업)

```
Claude Code Skills (21종) → Spec 해석 및 코드 생성 템플릿
  ├── /init-project      → Tech Stack Spec 기반 프로젝트 스캐폴딩
  ├── /gen-fastapi-route  → API Spec 기반 FastAPI 라우트 생성
  ├── /gen-sqlalchemy-model → Data Model Spec 기반 ORM 모델 생성
  ├── /gen-component      → Frontend Design Spec 기반 컴포넌트 생성
  ├── /gen-agent          → Agent Spec 기반 AI 에이전트 생성
  ├── /gen-test           → Test Spec 기반 테스트 스위트 생성
  └── /review-arch        → Architecture Spec 기반 준수 여부 검증
```

#### Phase 3: 하네스 실행 (AI 주도, 인간 감독)

```
AI 하네스 (Claude Code) → Spec 참조 → 코드 생성
  ├── Spec 문서를 자동으로 읽고 컨텍스트로 활용
  ├── Skill 템플릿에 따라 코드 생성
  ├── Spec에 없는 기능은 생성하지 않음 (No Spec-Free Code)
  └── 생성된 코드에 Spec 참조 주석 포함 (e.g., # Spec: FR-DASH-001)
```

#### Phase 4: Spec 기반 검증 (자동 + 인간)

```
검증 파이프라인:
  ├── /review-arch   → Architecture Spec 준수 여부 자동 검증
  ├── /gen-test      → Test Spec 기반 테스트 자동 생성 및 실행
  ├── 라이선스 감사   → Tech Stack Spec 라이선스 규격 준수 확인
  ├── 디자인 검증     → Frontend Design Spec 디자인 토큰 일치 확인
  └── 인간 리뷰      → Spec 대비 구현 완전성 최종 판단
```

### 2.5 하네스 엔지니어링 규칙 (AI 하네스 필독)

AI 하네스(Claude Code)는 본 프로젝트에서 코드를 생성할 때 **반드시** 다음 규칙을 따라야 합니다:

#### MUST (필수)
1. **코드 생성 전 관련 Spec 문서를 반드시 읽는다** — PRD, Architecture Spec, Tech Stack, Design Spec 중 관련 문서를 먼저 확인
2. **Spec에 정의된 인터페이스/모델/프로토콜을 정확히 구현한다** — 필드명, 타입, 엔드포인트 경로 등 Spec에 명시된 그대로
3. **생성된 코드에 Spec 참조를 명시한다** — `# Spec: FR-AI-002` 형태로 해당 기능의 요구사항 ID 표기
4. **Spec에 명시된 기술 스택만 사용한다** — `docs/TECH_STACK.md`에 없는 라이브러리 임의 추가 금지
5. **Spec에 명시된 라이선스 정책을 준수한다** — Apache 2.0/MIT/BSD만 허용, GPL/AGPL/SSPL 금지

#### MUST NOT (금지)
1. **Spec에 없는 기능을 임의로 추가하지 않는다** — "이것도 있으면 좋겠다"는 구현 금지
2. **Spec의 인터페이스를 임의로 변경하지 않는다** — 필드 추가/삭제/이름 변경 시 Spec 수정 먼저
3. **Spec 없이 리팩토링하지 않는다** — 코드 품질 개선도 Spec(또는 Tech Debt Ticket)이 필요
4. **Spec 범위를 넘는 최적화를 하지 않는다** — 성능 요구사항은 비기능 요구사항 Spec에 정의된 범위 내에서만
5. **Spec 문서를 코드에서 역추출하지 않는다** — Spec은 코드보다 먼저 존재해야 하며, 코드가 Spec을 결정하지 않음

#### SHOULD (권장)
1. Spec에 모호한 부분이 있으면 구현 전 인간 개발자에게 확인을 요청한다
2. Spec 준수 여부를 자체 점검하고, 의심스러운 부분을 보고한다
3. 기존 Spec과 충돌하는 요구를 받으면, 충돌 사항을 명시적으로 알린다

### 2.6 Spec 문서 작성 기준

모든 Feature Spec은 다음 구조를 따릅니다:

```markdown
# Feature Spec: [기능명]

## 메타데이터
- Spec ID: FS-{MODULE}-{NUMBER}
- PRD 참조: FR-{CATEGORY}-{NUMBER}
- 우선순위: P0 / P1 / P2
- 상태: Draft → Review → Approved → Implemented → Verified

## 개요
[기능의 목적과 범위를 1~2문장으로 기술]

## 인터페이스 계약
### API 엔드포인트 (해당 시)
- Method: GET/POST/PUT/DELETE
- Path: /api/v1/...
- Request Schema: (Pydantic model 참조)
- Response Schema: (Pydantic model 참조)
- Error Codes: 400, 401, 403, 404, 500

### 데이터 모델 (해당 시)
- Table: ...
- Columns: ...
- Indexes: ...
- Relationships: ...

### UI 컴포넌트 (해당 시)
- Component: ...
- Props: ...
- Design Token 참조: FRONTEND_DESIGN.md Section X.X

## 동작 규격
1. [정상 시나리오]
2. [예외 시나리오]
3. [경계 조건]

## 인수 기준 (Acceptance Criteria)
- [ ] AC-1: ...
- [ ] AC-2: ...
- [ ] AC-3: ...

## 의존성
- 선행 Spec: FS-xxx-xxx
- 사용 Spec: FS-yyy-yyy
```

### 2.7 Spec-Driven 개발 사이클

```
1. Spec 작성    → 인간이 Feature Spec 작성 (위 템플릿 기반)
2. Spec 리뷰    → 팀 리뷰, 인터페이스 충돌 검토
3. Spec 승인    → 상태: Approved
4. 하네스 실행  → AI가 Skill을 통해 코드 생성 (Spec 참조 필수)
5. 자동 검증    → /review-arch + /gen-test 실행
6. 인간 리뷰    → Spec 대비 구현 완전성 확인
7. Spec 완료    → 상태: Verified, 인수 기준 모두 체크
```

> **위반 시 처리**: Spec을 따르지 않는 코드가 발견되면, 해당 코드는 리뷰에서 거부(Reject)됩니다. AI 하네스가 생성한 코드도 예외 없이 동일한 기준이 적용됩니다. "동작하는 코드"보다 "Spec에 부합하는 코드"가 우선합니다.

---

### 1.2 용어 정의

| 용어 | 정의 |
|------|------|
| MCP | Model Context Protocol. AI 도구와 외부 시스템 간 표준 연동 프로토콜 (Anthropic/Linux Foundation) |
| A2A | Agent-to-Agent Protocol. AI 에이전트 간 협업 프로토콜 (Google/Linux Foundation) |
| Self-Healing | 감지→진단→대응→검증→롤백의 자동 복구 파이프라인 |
| Playbook | 장애 대응 절차를 YAML로 코드화한 실행 레시피 |
| ASH | Active Session History. 1초 단위 활성 세션 샘플링 |
| RCA | Root Cause Analysis. 근본 원인 분석 |
| RAG | Retrieval-Augmented Generation. 검색 증강 생성 |
| NL2SQL | Natural Language to SQL. 자연어→SQL 변환 |
| AIGC | AI Generated Content. AI 생성 콘텐츠 |
| Autonomy Level | AI 자율 실행 등급 (0~4단계) |
| SLO | Service Level Objective. 서비스 수준 목표 |
| OTel | OpenTelemetry. 분산 트레이싱/메트릭/로그 수집 표준 |

---

## 3. 프로젝트 범위

### 3.1 시스템 비전

AI/LLM을 활용하여 데이터베이스의 이상 징후를 사전에 탐지하고, 자동/수동/스케줄 기반으로 대응하는 지능형 DB 모니터링 플랫폼. 온프레미스와 클라우드 환경 모두를 지원하며, PostgreSQL을 시작으로 MySQL, MS-SQL 등으로 확장 가능한 플러그인 아키텍처를 제공합니다. 향후 독립 솔루션으로 발전할 수 있도록 설계합니다.

### 3.2 핵심 설계 원칙

1. **Plugin-First Architecture**: DB 어댑터를 플러그인으로 분리하여 코어 수정 없이 새 DB 추가
2. **On/Offline AI**: 클라우드 LLM API와 로컬 LLM(Ollama/vLLM) 모두 지원
3. **Event-Driven**: 메트릭 수집 → 분석 → 알림 → 대응의 전 과정을 비동기 이벤트 기반으로 처리
4. **Multi-Agent**: A2A 프로토콜 기반 전문 에이전트 협업 (탐지/진단/대응/보고)
5. **Permissive License Only**: 전체 기술 스택 Apache 2.0/MIT/BSD 등 허용적 라이선스로 통일
6. **Solution-Ready**: 멀티테넌시, SaaS 전환, 에이전트 마켓플레이스를 고려한 확장 가능 아키텍처

### 3.3 범위 정의 (In Scope)

- 데이터베이스 성능 모니터링 및 실시간 대시보드
- AI 기반 이상 탐지, 예측 분석, 근본 원인 분석 (RCA)
- **MTL(Multi-Task Learning) 기반 통합 RCA** — 이상 분류/원인 식별/심각도 평가/액션 추천 동시 수행
- AI 자동 베이스라인 학습 (수동 임계값 불필요)
- 풀스택 옵저버빌리티 (App→DB→Infra 토폴로지 자동 발견)
- 1초 단위 고해상도 메트릭 수집 + ASH(Active Session History)
- 스키마 변경 추적 및 영향도 분석
- AI 자동 쿼리 튜닝 (인덱스/쿼리/파라미터)
- AIGC 인터페이스 (NL2SQL, SQL 최적화, 실행계획 해석, 리포트 생성)
- **DB Copilot 모드** — Tree-of-Thought 추론 기반 자율 DB 유지보수 (GaussMaster 참조)
- Self-Healing DB (Closed-Loop 자가 치유 파이프라인)
- Playbook-as-Code (YAML + Git + LLM 자동 생성)
- Adaptive Autonomy 5단계 자율 등급
- **Explainable AI (XAI)** — 모든 AI 판단에 Confidence Score + 추론 체인 투명 공개
- **LLM Observability** — AI 시스템 자체의 성능/비용/정확도 모니터링
- MCP Server (외부 AI 도구 연동)
- A2A Protocol (멀티 에이전트 협업)
- Slack/Email/Webhook 알림 (등급별 에스컬레이션)
- RBAC 사용자 관리 + SSO/LDAP 연동
- 상세 감사 로깅 (AI Reasoning 포함)
- 멀티 DB 플러그인 아키텍처 (PostgreSQL/MySQL/MS-SQL)

### 3.4 범위 외 (Out of Scope)

- 데이터베이스 자체의 설치/구성/백업 관리 (DBA 업무 영역)
- 비즈니스 데이터 분석 (BI/분석 영역)
- 애플리케이션 코드 레벨 성능 최적화
- 네트워크/방화벽 모니터링

---

## 4. 차별화 전략

> **v3.3 신규 섹션**. 2026년 AIOps 시장 분석, GaussMaster(LLM-based DB Copilot) 논문, 주요 경쟁 솔루션 대비 분석을 토대로 NeuralDB만의 고유 차별화 전략을 정의합니다.

### 4.1 시장 갭 분석 (2026 AIOps Market Gaps)

| 시장 갭 | 설명 | NeuralDB 대응 |
|---------|------|-------------|
| **Data Starvation** | 대부분의 AIOps 플랫폼이 비용 절감을 위해 샘플링 적용 → AI 모델에 필요한 컨텍스트 부족 | **Zero-Sampling 전략**: 1초 고해상도 전량 수집 + 계층형 다운샘플링. AI에는 항상 원본 데이터 제공 |
| **Black-Box AI** | AI 판단 근거가 불투명하여 운영자 신뢰 부족. 추천만 제공하고 왜(Why)를 설명하지 못함 | **Explainable AI**: 모든 AI 출력에 Confidence Score + 추론 체인(Reasoning Chain) + 근거 데이터 명시 |
| **Hybrid IT 미지원** | 온프레미스 + 클라우드 혼합 환경에서 통합 모니터링 어려움 | **On/Offline AI + 2-Tier Hybrid 수집**: 어떤 환경에서도 동일 기능 제공 |
| **LLM Observability 부재** | AI 시스템 자체를 모니터링하는 기능이 거의 없음 | **LLM Observability 내장**: 토큰 사용량, 응답 지연, 정확도, 할루시네이션 비율 추적 |
| **벤더 락인** | 독점 계측(Instrumentation)으로 이탈 비용 높음 | **완전 개방형 표준**: OTel + MCP + A2A, 전체 스택 Permissive License |
| **비용 불투명** | 사용량 기반 과금 모델로 예산 예측 불가 | **셀프호스팅 $0** + 오프라인 LLM으로 API 비용 제거 가능 |

### 4.2 5대 핵심 차별화 전략

#### DS-1. DB Copilot 모드 (GaussMaster 참조)

**참조**: GaussMaster (Huawei, arXiv:2506.23322) — LLM 기반 DB Copilot으로 34개 이상의 DB 유지보수 시나리오를 무인 자동화

**개요**: 단순 모니터링/알림을 넘어, LLM이 **Tree-of-Thought(ToT) 추론**으로 수백 개 메트릭과 로그를 체계적으로 분석하여 근본 원인을 식별하고, 적절한 도구를 호출하여 문제를 해결하는 자율 DB 유지보수 모드.

```
DB Copilot Flow:
  트리거 이벤트 → 메트릭/로그 수집 → Tree-of-Thought 추론
    ├── Branch 1: 쿼리 성능 문제 → EXPLAIN 분석 → 인덱스 추천
    ├── Branch 2: 리소스 병목 → 파라미터 튜닝 → Config 변경
    ├── Branch 3: Lock Contention → Deadlock 분석 → 세션 킬
    └── 최적 경로 선택 → Confidence Score 평가 → 액션 실행/추천
```

**GaussMaster와의 차별점**:
- GaussMaster: 단일 DB(openGauss) 전용, 클로즈드 소스
- NeuralDB: **멀티 DB 플러그인** + **개방형 표준(MCP/A2A)** + **Adaptive Autonomy로 단계적 자율화**

#### DS-2. MTL(Multi-Task Learning) 기반 통합 RCA

**개요**: 기존 RCA는 단일 목적(원인 추정)만 수행하나, NeuralDB는 MTL 아키텍처로 하나의 공유 인코더가 다중 태스크를 **동시에** 수행하여 더 풍부한 컨텍스트와 정확도를 제공합니다.

```
Input: [metrics, ASH, query_stats, wait_events, topology, schema_changes]
    ↓
┌─────────────────────────────────────────┐
│       Shared Encoder (Transformer)       │
│  메트릭+로그+쿼리 통합 표현 학습          │
└────┬────────┬────────┬────────┬─────────┘
     ↓        ↓        ↓        ↓
┌────────┐┌────────┐┌────────┐┌──────────┐
│ Head 1 ││ Head 2 ││ Head 3 ││ Head 4   │
│ 이상   ││ 근본   ││ 심각도 ││ 액션     │
│ 분류   ││ 원인   ││ 평가   ││ 추천     │
│        ││ 식별   ││        ││          │
│Anomaly ││ Root   ││Severity││ Action   │
│ Type   ││ Cause  ││ Score  ││ Recommend│
└────────┘└────────┘└────────┘└──────────┘
```

**MTL의 이점**:
1. **크로스 태스크 지식 전이**: 이상 분류 정보가 원인 식별에 도움, 심각도가 액션 우선순위에 영향
2. **정규화 효과**: 과적합 방지로 소규모 데이터에서도 견고한 성능
3. **단일 추론**: 4개 별도 모델 대비 **추론 시간 75% 절감**, 리소스 효율적
4. **Confidence Score 자연 산출**: 각 Head의 softmax 출력이 곧 신뢰도 점수

**MTL 모델 학습 전략**:
- Phase 1(MVP): 사전학습 LLM(GPT-4o/Mistral) + Few-shot Prompting으로 4개 태스크 수행 (MTL Lite)
- Phase 2: 축적된 인시던트 데이터로 경량 Transformer 파인튜닝 (PyTorch)
- Phase 3: 풀 MTL 모델 학습 + 온라인 학습(Continual Learning)으로 새 장애 유형 자동 적응

#### DS-3. Explainable AI (XAI) — 투명한 AI 의사결정

**참조**: BigPanda Open Box AI, OpenObserve Agentic Automation (human-verifiable reasoning chains)

**개요**: 모든 AI 판단에 **Confidence Score(0.0~1.0)** + **추론 체인(Reasoning Chain)** + **근거 데이터 링크**를 필수 포함하여, 운영자가 AI 판단을 검증하고 신뢰할 수 있도록 합니다.

```json
{
  "anomaly_type": "query_performance_degradation",
  "confidence": 0.87,
  "root_cause": "Missing index on orders.created_at",
  "severity": "WARNING",
  "reasoning_chain": [
    "1. CPU 사용률 85% (베이스라인 대비 +40%) → 쿼리 부하 증가 의심",
    "2. pg_stat_statements Top 1 쿼리: SELECT * FROM orders WHERE created_at > ... (avg_time: 3.2s → 12.8s)",
    "3. EXPLAIN 분석: Seq Scan on orders (cost=0..45000) → 인덱스 미사용 확인",
    "4. 과거 유사 사례 3건 검색 (RAG, similarity: 0.92) → 인덱스 생성으로 해결"
  ],
  "evidence_links": [
    "/api/v1/instances/pg-prod-01/metrics?range=1h",
    "/api/v1/instances/pg-prod-01/ash?pid=12345"
  ],
  "suggested_actions": [
    {"action": "CREATE INDEX CONCURRENTLY idx_orders_created_at ON orders(created_at)", "confidence": 0.91, "risk": "LOW"}
  ]
}
```

**Confidence Score 활용**:
- Score ≥ 0.8: Autonomy Level에 따라 자동 실행 허용
- 0.5 ≤ Score < 0.8: 관리자 확인 필수 (Level 강제 상향)
- Score < 0.5: 추천만 표시, 실행 불가

#### DS-4. LLM Observability — AI 시스템 자체 모니터링

**참조**: OpenObserve + OpenLIT 파트너십 (LLM observability), 2026 AIOps 시장 신흥 갭

**개요**: 대상 DB만 모니터링하는 것이 아니라, NeuralDB 내부의 LLM/AI 파이프라인 자체를 모니터링합니다. AI가 AI를 감시하는 메타 옵저버빌리티.

| 메트릭 | 설명 | 알림 기준 |
|--------|------|----------|
| **토큰 사용량** | 에이전트별/작업별 input/output 토큰 | 일 예산 초과 시 경고 |
| **LLM 응답 지연** | P50/P95/P99 응답 시간 | P95 > 10초 시 경고 |
| **RCA 정확도** | 운영자 피드백 기반 정답률 추적 | 주간 정확도 < 70% 시 재학습 트리거 |
| **할루시네이션 비율** | RAG 근거 없이 생성된 답변 비율 | > 15% 시 경고 + RAG 파이프라인 점검 |
| **모델 드리프트** | MTL 모델 예측 분포 변화 감지 | KL-divergence 임계값 초과 시 재학습 |
| **비용 추적** | Cloud LLM API 호출당 비용 누적 | 월 예산 80% 도달 시 Offline LLM 전환 권고 |

#### DS-5. Zero-Sampling 전략 — 데이터 스타베이션 해결

**참조**: IBM Instana (1-second granularity), OpenObserve (140x lower storage costs)

**개요**: 경쟁 솔루션이 비용 절감을 위해 10초~1분 샘플링하는 것과 달리, NeuralDB는 **1초 전량 수집**을 기본으로 하되 **계층형 보관**으로 비용을 최적화합니다. AI 모델에는 항상 충분한 컨텍스트를 제공하여 진단 정확도를 극대화합니다.

```
Zero-Sampling Pipeline:
  1초 원본 (7일) → 10초 집계 (90일) → 1분 집계 (1년) → 1일 집계 (영구)
       ↑
  AI 분석 시: 이상 탐지 시점의 1초 원본 데이터 자동 보존 연장
  → 경쟁사 대비 10~60배 높은 데이터 밀도로 AI 정확도 향상
```

### 4.3 경쟁 솔루션 대비 차별화 요약

| 차별화 | Datadog | Dynatrace | pganalyze | Percona PMM | Xata Agent | GaussMaster | **NeuralDB** |
|--------|---------|-----------|-----------|-------------|------------|-------------|-------------|
| DB Copilot (ToT) | ❌ | ❌ | ❌ | ❌ | ⚠️ 단일경로 | ✅ | **✅ + 멀티DB** |
| MTL 기반 통합 RCA | ❌ | ⚠️ Davis AI | ❌ | ❌ | ❌ | ❌ | **✅** |
| Explainable AI | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | **✅ Confidence+Chain** |
| LLM Observability | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | **✅** |
| Zero-Sampling (1초) | ⚠️ 10초 | ❌ 1분 | ⚠️ 10초~1분 | ⚠️ 1초(low-res) | ❌ | ❌ | **✅ 1초 전량** |
| MCP + A2A | ❌ | ❌ | ⚠️ MCP only | ❌ | ❌ | ❌ | **✅ 양쪽** |
| 오프라인 LLM | ❌ | ❌ | ❌ | ❌ | ✅ | ⚠️ 제한적 | **✅ 완전** |
| Permissive License | ❌ SaaS | ❌ SaaS | ⚠️ | ❌ AGPL종속 | ✅ | ❌ 클로즈드 | **✅ 전체** |

---

## 5. 기능 요구사항

### 5.1 모니터링 대시보드 [FR-DASH]

| ID | 요구사항 | 우선순위 | 상세 설명 |
|----|---------|---------|----------|
| FR-DASH-001 | 실시간 DB 상태 대시보드 | P0 | CPU, 메모리, 디스크, 커넥션, TPS 등 핵심 메트릭 실시간 시각화 |
| FR-DASH-002 | 풀스택 토폴로지 맵 | P1 | App→DB→Infra 의존성 자동 발견 및 시각화. OTel 트레이스 기반 |
| FR-DASH-003 | ASH Timeline 뷰 | P1 | 1초 단위 활성 세션 샘플링, Wait Event 카테고리별 히트맵 시각화 |
| FR-DASH-004 | 스키마 변경 타임라인 | P1 | DDL 변경 이벤트와 성능 메트릭 오버레이 비교 뷰 (Before/After) |
| FR-DASH-005 | 커스텀 대시보드 레이아웃 | P2 | 사용자별 대시보드 레이아웃 저장/복원, 위젯 드래그앤드롭 |

### 5.2 AI/LLM 지능형 기능 [FR-AI]

| ID | 요구사항 | 우선순위 | 상세 설명 |
|----|---------|---------|----------|
| FR-AI-001 | AI 자동 베이스라인 학습 | P0 | 수동 임계값 없이 정상 패턴 자동 학습. 시간대/요일별 동적 이상 탐지. STL 분해 + Isolation Forest 기반 |
| FR-AI-002 | RAG 기반 근본원인 분석 | P0 | DB 문서/매뉴얼/장애 이력을 pgvector에 임베딩. 유사 과거 사례를 검색하여 LLM이 맥락적 RCA 수행. **MVP에서 경량 RAG 활성화** |
| FR-AI-003 | NL2SQL 자연어 질의 | P0 | 자연어로 모니터링 데이터 조회. 스키마 인식 SQL 변환 + 결과 자동 시각화. 읽기 전용 쿼리만 실행 |
| FR-AI-004 | AI 자동 쿼리 튜닝 | P1 | EXPLAIN ANALYZE 결과를 LLM으로 분석하여 인덱스 생성, 쿼리 리라이트, 파라미터 튜닝 자동 추천 및 적용 |
| FR-AI-005 | AIGC 리포트 생성 | P1 | "이번 주 DB 건강 리포트 만들어줘" → AI가 차트 + 분석 + 추천사항 포함 리포트 자동 생성 |
| FR-AI-006 | 실행계획 자연어 해석 | P1 | EXPLAIN 결과를 비기술자도 이해할 수 있는 자연어로 번역. 병목 지점 및 개선 방안 포함 |
| FR-AI-007 | LLM Playbook 자동 생성 | P1 | 기존 Playbook에 매칭되지 않는 새 장애 유형에 대해 LLM이 Playbook 초안 자동 작성. 관리자 리뷰 후 Git 머지 |
| FR-AI-008 | 온/오프라인 AI 모드 전환 | P0 | Cloud LLM(OpenAI, Claude)과 로컬 LLM(Ollama+Mistral/Qwen, vLLM) 간 환경변수로 전환 |
| FR-AI-009 | 스키마 변경 인과관계 추론 | P2 | DDL 변경과 성능 저하 사이의 인과관계를 Causal Inference로 자동 분석. 롤백 추천 |
| FR-AI-010 | MTL 기반 통합 RCA | P0 | **Multi-Task Learning** 아키텍처로 이상 분류/근본 원인 식별/심각도 평가/액션 추천을 단일 추론에서 동시 수행. Shared Encoder + 4개 Task Head. MVP에서는 LLM Few-shot으로 MTL Lite 구현, Phase 2에서 Transformer 파인튜닝 |
| FR-AI-011 | Explainable AI (Confidence Score) | P0 | 모든 AI 출력에 Confidence Score(0.0~1.0) + Reasoning Chain + Evidence Links 필수 포함. Score < 0.5이면 자동 실행 불가, 0.5~0.8이면 관리자 확인 필수 |
| FR-AI-012 | DB Copilot 모드 | P1 | Tree-of-Thought 추론으로 복합 장애를 다중 경로로 분석. 최적 해결 경로를 자동 선택하여 실행. GaussMaster 참조. Autonomy Level 연동 |
| FR-AI-013 | LLM Observability | P1 | AI 파이프라인 자체 모니터링. 토큰 사용량, 응답 지연(P50/P95/P99), RCA 정확도, 할루시네이션 비율, 모델 드리프트, API 비용 추적. 정확도 < 70% 시 자동 재학습 트리거 |
| FR-AI-014 | 경량 RCA 요약 | P0 | 인시던트 발생 시 LLM이 **1줄 Root Cause Summary + 추천 액션 1~3개 + Confidence Score**를 즉시 생성. MVP에서 기본 활성화 |

### 5.3 자동화 및 대응 [FR-AUTO]

| ID | 요구사항 | 우선순위 | 상세 설명 |
|----|---------|---------|----------|
| FR-AUTO-001 | Self-Healing Closed-Loop | P0 | 감지→진단→대응→검증→롤백 자동화 파이프라인. SLO 기반 검증, 실패 시 자동 롤백 + 에스컬레이션 |
| FR-AUTO-002 | Adaptive Autonomy 5단계 | P0 | L0(알림만)→L1(추천)→L2(승인 후 실행)→L3(실행 후 보고)→L4(완전 자율). 작업 위험도/시간대/성공률 기반 자동 분류 |
| FR-AUTO-003 | Playbook-as-Code | P0 | YAML Playbook Git 버전관리. 단계별 승인/실행/롤백. LLM 자동 생성. 실행 결과 피드백으로 Playbook 점수 자동 갱신 |
| FR-AUTO-004 | Task Queue 관리 | P0 | 자동(Auto)/수동(Manual)/스케줄(Queue) 3가지 실행 모드. 승인 워크플로우. 유지보수 윈도우 내 배치 실행 |
| FR-AUTO-005 | 동적 Autonomy 격하 | P1 | 자동 대응 실패 시 해당 Playbook의 Autonomy Level 자동 1단계 하향. 연속 실패 시 L0으로 격하하여 사람 개입 전환 |

### 5.4 알림 및 연동 [FR-ALERT]

| ID | 요구사항 | 우선순위 | 상세 설명 |
|----|---------|---------|----------|
| FR-ALERT-001 | Slack 알림 | P0 | 🔴CRITICAL / 🟠WARNING / 🟡NOTICE / 🟢INFO 4단계. 메트릭 값, AI 분석 요약, 액션 버튼([상세보기][즉시대응][무시]) 포함 |
| FR-ALERT-002 | Email/Webhook 알림 | P0 | 다중 채널 알림 및 에스컬레이션 정책. 1차(Slack)→2차(Email+Phone)→3차(PagerDuty) 단계적 상승 |
| FR-ALERT-003 | AI 동적 베이스라인 알림 | P0 | AI 학습 기반 미세 이상 탐지 + 수동 임계값은 안전 상한선으로 병행. 알림 노이즈 90% 이상 자동 제거 |
| FR-ALERT-004 | MCP Server | P1 | 외부 AI 도구(Claude Code, VS Code Copilot, ChatGPT)가 MCP 프로토콜로 메트릭/쿼리/알림 조회 가능. Resources/Tools/Prompts 제공 |
| FR-ALERT-005 | A2A Gateway | P1 | 내부 에이전트(Monitoring/Diagnosis/Remediation/Reporting) 간 Agent Card 발견 및 Task 라우팅. 외부 파트너 에이전트 연동 지원 |

### 5.5 사용자 관리 및 로깅 [FR-ADMIN]

| ID | 요구사항 | 우선순위 | 상세 설명 |
|----|---------|---------|----------|
| FR-ADMIN-001 | RBAC 사용자 관리 | P0 | Super Admin / DB Admin / Operator / Viewer / API User 5개 역할. 역할별 기능 접근 제한 |
| FR-ADMIN-002 | SSO/LDAP 연동 | P1 | SAML 2.0, OIDC, LDAP/AD 인증 지원. API Key 기반 외부 시스템 인증 |
| FR-ADMIN-003 | 상세 감사 로깅 | P0 | 모든 시스템 이벤트 WHO/WHAT/WHEN/WHERE/WHY 기록. 변경 사항 Before/After 비교 저장 |
| FR-ADMIN-004 | AI Decision Log | P0 | LLM 입력 프롬프트, 출력 결과, 토큰 사용량, 추론 근거(Reasoning) 상세 기록. Self-Healing 전 과정 로깅 |
| FR-ADMIN-005 | 로그 보관 정책 | P1 | Hot(7일 원본)/Warm(90일 압축)/Cold(1년 아카이브)/Glacier(영구 규정준수) 계층형 보관 |

### 5.6 멀티 DB 지원 [FR-DB]

| ID | 요구사항 | 우선순위 | 상세 설명 |
|----|---------|---------|----------|
| FR-DB-001 | PostgreSQL Adapter | P0 | pg_stat_statements, pg_stat_activity, pg_stat_bgwriter, pg_stat_replication + 1초 ASH 샘플링 + DDL Event Trigger + pgBouncer |
| FR-DB-002 | MySQL Adapter | P2 | performance_schema, slow_query_log, InnoDB 메트릭, Wait Events |
| FR-DB-003 | MS-SQL Adapter | P2 | DMV, Extended Events, Query Store, Wait Stats |
| FR-DB-004 | Plugin Interface (SPI) | P0 | 새 DB 타입 추가를 위한 표준화된 어댑터 인터페이스. collect_metrics(), get_slow_queries(), get_active_sessions(), execute_action() 등. Remote Adapter와 Local Collector 양쪽 구현을 지원하는 단일 인터페이스 |
| FR-DB-005 | 2-Tier Hybrid 수집 전략 | P1 | **Tier 1(Remote Adapter)**: NeuralDB에서 원격 조회, 설치 불필요, 소규모/PoC용. **Tier 2(Lightweight Collector)**: 대상 DB 서버에 설치, 로컬 수집 후 Push, 50대 이상/1초 보장용. Collector 미설치 시 Remote로 자동 폴백 (해상도 다운그레이드) |
| FR-DB-006 | 해상도 폴백 정책 | P1 | Remote Adapter 사용 시 네트워크 지연에 따라 자동 해상도 조정: RTT <5ms→1초, RTT 5~20ms→5초, RTT >20ms→10초. Collector 사용 시 항상 1초 보장 |

### 5.7 시스템 자체 모니터링 [FR-SELF]

| ID | 요구사항 | 우선순위 | 상세 설명 |
|----|---------|---------|----------|
| FR-SELF-001 | NeuralDB 자체 헬스 모니터링 | P0 | FastAPI 요청 지연/에러율, Celery Worker 큐 깊이/처리량, Agent 실행 시간/성공률, Valkey 히트율, Kafka consumer lag 등 시스템 자체 메트릭 수집 |
| FR-SELF-002 | Prometheus 메트릭 노출 | P0 | FastAPI `/metrics` 엔드포인트로 Prometheus 형식 메트릭 자동 노출. Celery/Kafka/PostgreSQL(시스템DB)/Valkey exporter 연동 |
| FR-SELF-003 | OpenTelemetry 자체 계측 | P0 | 모든 API 엔드포인트, Agent 실행, DB 쿼리에 분산 트레이싱 자동 적용. 자체 성능 병목 추적 가능 |
| FR-SELF-004 | System Health 대시보드 | P1 | 대시보드 내 "System Health" 탭으로 자체 시스템 상태 시각화. Grafana 대신 자체 React + ECharts 구현 (AGPL 회피) |
| FR-SELF-005 | 자체 이상 탐지 알림 | P1 | NeuralDB 시스템 자체의 이상 (API 지연 급증, Worker 중단, DB 커넥션 고갈 등) 시 관리자에게 알림 발송 |

> **주의: 대상 DB 메트릭 vs 자체 시스템 메트릭 구분**
> - **대상 DB 메트릭**: 자체 Adapter가 `pg_stat_*` 직접 조회 → PostgreSQL 16 저장 (Prometheus 불필요)
> - **자체 시스템 메트릭**: OpenTelemetry SDK → Prometheus → System Health 대시보드

---

## 6. 모니터링 카테고리 상세

다음 5개 카테고리의 메트릭을 기본 제공합니다. 각 카테고리는 대시보드에서 독립 탭으로 표시되며, 사용자가 항목을 커스텀할 수 있습니다.

### 6.1 ⚡ 성능 모니터링

- Slow Query 탐지 (설정 임계값 초과 쿼리 자동 수집)
- 쿼리 실행 빈도 Top N (가장 많이 호출되는 쿼리)
- Lock 대기 시간 & Deadlock 감지
- 실행 계획 변경 감지 (Plan Regression)
- 인덱스 사용률 & Missing Index 추천
- 버퍼 캐시 히트율 (캐시 효율)
- Temp 파일 사용량 (work_mem 부족 지표)
- 쿼리 지연 시간 분포 (P50 / P95 / P99)

### 6.2 📊 리소스 사용량

- CPU / Memory / Disk I/O 사용률
- 디스크 여유 공간 & 증가 추세 예측
- 커넥션 풀 사용률 (max_connections 대비)
- 테이블스페이스별 사용량
- WAL 생성량 & 복제 지연
- Vacuum / Autovacuum 실행 상태
- 테이블 & 인덱스 Bloat 비율
- Shared Buffer 사용 효율

### 6.3 🔒 보안 & 접근 제어

- 비인가 접근 시도 탐지
- 권한 변경 이력 추적
- SSL/TLS 인증서 만료 예정 알림
- 장기 미사용 계정 감지
- 비정상 로그인 패턴 (AI 기반)
- 민감 데이터 접근 감사
- DDL 변경 이력 추적

### 6.4 🌐 가용성 & 복제

- Primary-Replica 동기화 상태
- Failover 준비 상태 확인
- 백업 성공/실패 이력
- 복제 지연 시간 (Replication Lag)
- 업타임 & SLA 달성률
- MTTR(평균 복구 시간) 추적
- 커넥션 가용성

### 6.5 🤖 AI 지능형 탐지

- 비정상 쿼리 패턴 탐지 (Anomaly Detection)
- 리소스 사용량 이상 예측 (Predictive Analytics)
- 워크로드 트렌드 분석 (Trend Analysis)
- 장애 사전 예측 (Failure Prediction)
- 자동 인덱스/파라미터 추천 (Auto-Tuning)
- 근본 원인 분석 (Root Cause Analysis)
- 자연어 진단 리포트 생성 (NL Report)

---

## 7. 비기능 요구사항

| 영역 | 요구사항 | 목표 수치 |
|------|---------|----------|
| 성능 | 메트릭 수집 주기 | Hot: 1초, Warm: 10초, Cold: 1분 |
| 성능 | 대시보드 로딩 시간 | < 3초 (초기 로드), < 1초 (갱신) |
| 성능 | NL2SQL 응답 시간 | < 5초 (Cloud LLM), < 10초 (Local LLM) |
| 성능 | Self-Healing 응답 시간 | < 30초 (감지→실행 시작) |
| 가용성 | 시스템 업타임 | 99.9% (8.76시간/년 이하 다운타임) |
| 확장성 | 동시 모니터링 DB 수 | Remote Adapter: ~30대 (1초 보장), Collector: 200대+ (수평 확장) |
| 확장성 | 수집 해상도 보장 | Collector: 항상 1초. Remote: RTT에 따라 1초~10초 자동 폴백 |
| 확장성 | 메트릭 보관 용량 | 1초 데이터: 7일, 집계: 1년 |
| 보안 | 인증 | JWT + OAuth2.0 + API Key |
| 보안 | 데이터 암호화 | 전송 중 TLS 1.3, 저장 시 AES-256 |
| 보안 | 권한 제어 | RBAC 5개 역할 + API 별도 권한 |
| 호환성 | 브라우저 | Chrome, Firefox, Safari, Edge (최신 2버전) |
| 호환성 | 배포 환경 | Docker, Kubernetes, Bare Metal |
| 라이선스 | 전체 기술 스택 | Apache 2.0 / MIT / BSD 등 허용적 라이선스만 허용 |

---

## 8. 기술 스택

모든 기술은 Apache 2.0, MIT, BSD 등 허용적(Permissive) 라이선스로 통일되어 있습니다. GPL/AGPL/SSPL 계열은 사용하지 않습니다.

| 영역 | 기술 | 라이선스 |
|------|------|---------|
| Frontend | React 18+ / Next.js 14+ / TailwindCSS / Apache ECharts | MIT / Apache 2.0 |
| API | NestJS / Apollo GraphQL / Socket.io | MIT |
| Protocol | MCP SDK / A2A SDK / OpenTelemetry | MIT / Apache 2.0 |
| Core Engine | Python 3.11+ / FastAPI / Celery | MIT / BSD |
| Agent Framework | LangChain / LangGraph / CrewAI | MIT |
| AI/LLM (온라인) | OpenAI API / Claude API | 상용 API |
| AI/LLM (오프라인) | Ollama + Mistral/Qwen / vLLM | MIT / Apache 2.0 |
| AI/ML | Prophet / scikit-learn | MIT / BSD |
| 시계열 DB | QuestDB | Apache 2.0 |
| 메타 DB | PostgreSQL 16+ | PostgreSQL License (MIT계열) |
| 벡터 DB | pgvector | PostgreSQL License |
| 캐시 | Valkey | BSD 3-Clause |
| 메시징 | Apache Kafka | Apache 2.0 |
| 모니터링 | Prometheus / VictoriaMetrics (단일노드) | Apache 2.0 |
| CI/CD | Gitea + Woodpecker CI | MIT / Apache 2.0 |
| 컨테이너 | Docker / Kubernetes | Apache 2.0 |

### 라이선스 변경 사항 (v3.0 → v3.1)

| 기존 기술 | 문제 라이선스 | 대체 기술 | 신규 라이선스 |
|-----------|-------------|----------|-------------|
| Grafana | AGPL v3 | 자체 React 대시보드 + Apache ECharts | MIT + Apache 2.0 |
| TimescaleDB Community | TSL (SaaS 제공 불가) | QuestDB | Apache 2.0 |
| Redis 7.4+ | RSALv2 + SSPL | Valkey (Linux Foundation) | BSD 3-Clause |

---

## 9. 프로젝트 일정

### 9.1 로드맵

| 페이즈 | 기간 | 핵심 산출물 |
|--------|------|-----------|
| Phase 1 — MVP | 3개월 | PostgreSQL Adapter(1초 ASH + DDL Trigger), PostgreSQL 16 메트릭 저장, 기본 대시보드, Slack 알림, AI 자동 베이스라인, NL2SQL 기본, **경량 RAG(pgvector)**, **MTL Lite(LLM Few-shot 4-Head)**, **경량 RCA 요약 + Confidence Score**, 사용자 인증/인가 |
| Phase 2 — AI 강화 | 3개월 | **풀 RAG Pipeline**, AIGC 확장(SQL 최적화/EXPLAIN 해석/리포트 생성), Playbook-as-Code + Git 연동, Auto Query Tuning, Schema Change Tracking, Adaptive Autonomy 5단계, **MTL Transformer 파인튜닝**, **DB Copilot(ToT) 기본**, **LLM Observability 대시보드** |
| Phase 3 — 멀티 에이전트 | 3개월 | 단일 Engine→Multi-Agent(A2A) 전환, **Lightweight Collector 추가 (2-Tier Hybrid 수집)**, OTel Collector + Topology Engine(풀스택 의존성 발견), MCP Server 노출, Self-Healing Closed-Loop, Wait Event 심층 분석 대시보드, **풀 MTL + Continual Learning** |
| Phase 4 — 솔루션화 | 3개월 | MySQL/MS-SQL Adapter 추가, **Collector 자동 업데이트/배포 관리**, A2A 기반 외부 에이전트 연동, 에이전트 마켓플레이스, 멀티테넌시 + SaaS 모드, 엔터프라이즈 라이선스/화이트라벨 |

### 9.2 우선순위 정의

| 등급 | 정의 | 목표 페이즈 |
|------|------|-----------|
| P0 (Must Have) | MVP 출시에 반드시 포함되어야 하는 핵심 기능 | Phase 1 |
| P1 (Should Have) | AI 강화 및 차별화를 위해 필요한 중요 기능 | Phase 2~3 |
| P2 (Nice to Have) | 솔루션 확장을 위한 부가 기능 | Phase 3~4 |

---

## 10. 제약 조건 및 위험 요소

### 10.1 제약 조건

1. **라이선스**: 전체 기술 스택 Apache 2.0/MIT/BSD 등 허용적 라이선스만 허용. GPL/AGPL/SSPL 사용 금지.
2. **온/오프라인**: 인터넷 차단 환경에서도 AI 기능이 작동해야 함 (Ollama/vLLM 로컬 모드 필수).
3. **PostgreSQL 우선**: PostgreSQL을 기본 대상 DB로 하되, 아키텍처는 멀티 DB 확장 가능해야 함.
4. **보안**: 모든 외부 통신 TLS 1.3, 저장 데이터 AES-256 암호화 필수.
5. **AI 안전장치**: 자동 실행 작업에 대한 자동 롤백, Least-Privilege, Blast Radius 제한 필수.

### 10.2 위험 요소

| 위험 | 영향 | 대응 방안 |
|------|------|----------|
| LLM 할루시네이션 | 잘못된 AI 진단/대응 실행 | RAG로 정확도 향상 + Autonomy Level로 위험 제어 + 사람 승인 체인 |
| AI 자동 실행 실패 | 서비스 장애 악화 | 자동 롤백 + SLO 검증 + 동적 Autonomy 격하 + 에스컬레이션 |
| QuestDB 성숙도 | TimescaleDB 대비 생태계 작음 | 초기 PoC로 성능 검증 + VictoriaMetrics 백업 옵션 유지 |
| 멀티 에이전트 복잡성 | 디버깅/모니터링 난이도 증가 | A2A 표준 프로토콜 + 에이전트별 독립 로깅 + 에이전트 헬스 대시보드 |
| LLM API 비용 | 대규모 운영 시 비용 급증 | 오프라인 LLM 기본 사용 + 복잡한 작업만 Cloud LLM + 토큰 사용량 모니터링 |
| Valkey 호환성 | Redis 클라이언트와의 미세 차이 | Valkey는 Redis API 100% 호환. Linux Foundation 관리로 장기 안정성 보장 |

---

## 11. 인수 기준

### 11.1 Phase 1 MVP 인수 기준

1. PostgreSQL 인스턴스 연결 및 1초 단위 메트릭 수집 정상 동작
2. AI 자동 베이스라인이 2주 학습 후 이상 탐지 정상 동작 (오탐률 < 10%)
3. 대시보드에서 실시간 메트릭 시각화 및 ASH Timeline 드릴다운 정상 동작
4. Slack 알림이 4단계(CRITICAL/WARNING/NOTICE/INFO)로 정상 발송
5. NL2SQL로 자연어 질의 시 정확한 SQL 변환 및 결과 시각화 (성공률 > 80%)
6. RBAC 5개 역할 기반 사용자 인증/인가 정상 동작
7. 모든 시스템 이벤트에 대한 감사 로그 정상 기록
8. **경량 RCA**: 인시던트 발생 시 1줄 Root Cause Summary + 추천 액션 + Confidence Score 자동 생성
9. **경량 RAG**: pgvector 기반 인시던트 이력 유사 검색이 RCA에 활용됨
10. **MTL Lite**: 이상분류/원인식별/심각도/액션추천 4개 태스크가 LLM Few-shot으로 동시 수행

### 11.2 전체 프로젝트 인수 기준

1. Self-Healing 파이프라인이 감지부터 실행까지 30초 이내 처리
2. Adaptive Autonomy 5단계가 작업 유형별로 정상 분류 및 실행
3. MCP Server를 통해 외부 AI 도구에서 메트릭 조회 정상 동작
4. A2A 프로토콜로 4개 에이전트 간 Task 위임/협업 정상 동작
5. MySQL, MS-SQL Adapter 추가 시 코어 엔진 수정 없이 플러그인으로 활성화
6. 전체 기술 스택 라이선스 감사 통과 (GPL/AGPL/SSPL 제로)

---

## 12. 부록

### 12.1 참조 솔루션 매핑

| 솔루션 | 참조한 핵심 기능 | 적용 모듈 |
|--------|-----------------|----------|
| Oracle Autonomous AI DB | Auto-Tuning, Self-Healing, AI Agent 내장 | Auto Query Tuning, Self-Healing, A2A Agent |
| Dynatrace Davis AI | Smartscape 토폴로지, 크로스 스택 RCA, OneAgent 자동 발견 | Full-Stack Observability, Topology Engine |
| IBM Instana | 1초 단위 메트릭, 자동 의존성 맵, 실시간 RCA | 1-Second Granularity, Auto-Baselining |
| Datadog DB Monitoring | Wait Event 분석, 실행 계획 뷰, 서비스 맵 | ASH & Wait Events, Full-Stack Observability |
| LogicMonitor Edwin AI | AI 이상 탐지, 트렌드 분석, 자연어 인시던트 요약 | Auto-Baselining, AIGC Reporting |
| DBmarlin | 스키마 변경 추적, Before/After 성능 비교 | Schema Change Tracking |
| Chat2DB | NL2SQL, AI SQL 최적화, BI 대시보드 자동 생성 | AIGC Interface, NL2SQL |
| Percona PMM 3.x | 오픈소스 멀티 DB, 오프라인 Advisor, Query Analytics | Plugin Architecture, Offline Mode |
| Xata Agent | LLM Playbook, PostgreSQL 전문 에이전트 | Playbook-as-Code, Multi-Agent |
| pganalyze + MCP | MCP 서버, EXPLAIN 추적, 쿼리 분석 | MCP Server, Query Analyzer |
| **GaussMaster** | **Tree-of-Thought 추론, 자율 DB 유지보수 (34+ 시나리오 무인 자동화)** | **DB Copilot, ToT RCA** |
| **BigPanda** | **Open Box AI (투명한 AI 의사결정), 알림 상관분석** | **Explainable AI, Confidence Score** |
| **OpenObserve** | **3-Layer AI (MCP+Assistant+SRE Agent), LLM Observability** | **LLM Observability, Agentic Automation** |

### 12.2 시스템 아키텍처 개요

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
                    │  REST │ WebSocket │ MCP Server │ A2A GW │OTel│
                    │                  Auth Service                 │
                    └──────────────────┬───────────────────────────┘
                                       │
     ┌─────────────────────────────────┼───────────────────────────┐
     │         Core Engine Layer (Multi-Agent System)               │
     │                                                              │
     │  Monitoring Agent ──A2A──▶ Diagnosis Agent ──A2A──▶         │
     │  (+AutoBaseline)          (+RAG, +Topology RCA)    │         │
     │       │                        │                   │         │
     │  Topology Engine    Playbook Engine     Remediation Agent    │
     │  (OTel→의존성)                          (+Auto Query Tuning) │
     │                                              │               │
     │  Alert Engine    Task Orchestrator    Reporting Agent        │
     │  (+Dynamic       (+5-Level            (+AIGC, +NL2SQL,      │
     │   Baseline)       Autonomy)            +EXPLAIN 해석)        │
     │                                                              │
     │  Query Analyzer (+ASH, +Wait Event, +Auto Tuning)           │
     │  Audit Logger (+Schema Change, +AI Reasoning)               │
     └─────────────────────────────┬────────────────────────────────┘
                                   │
     ┌─────────────────────────────┼────────────────────────────────┐
     │       Database Adapter Layer (Plugin Architecture)            │
     │  PostgreSQL (+1s ASH, +DDL Trigger) │ MySQL │ MS-SQL │Custom │
     │  Schema Change Tracker │ Plugin Interface (SPI)              │
     └─────────────────────────────┬────────────────────────────────┘
                                   │
     ┌─────────────────────────────┼────────────────────────────────┐
     │               Infrastructure Layer                            │
     │  QuestDB (1s metrics, ASH, Auto Downsample)                  │
     │  PostgreSQL (Meta) │ Valkey (Cache) │ Kafka (Messaging)      │
     │  pgvector + RAG │ Playbook Git Repository                    │
     └──────────────────────────────────────────────────────────────┘
```

### 12.3 문서 변경 이력

| 버전 | 일자 | 변경 사항 |
|------|------|----------|
| v1.0 | 2026-03-21 | 초기 아키텍처 설계 (5-Layer, Plugin, On/Offline AI, Slack 알림, RBAC, 로깅) |
| v2.0 | 2026-03-21 | +MCP Server, +A2A Multi-Agent, +Self-Healing, +Playbook-as-Code, +Adaptive Autonomy, +NL2SQL, +RAG |
| v3.0 | 2026-03-21 | +Auto-Baselining, +Full-Stack Observability, +1s Granularity, +ASH/Wait Events, +Schema Change Tracking, +Auto Query Tuning, +AIGC Interface |
| v3.1 | 2026-03-21 | 기술 스택 라이선스 감사 및 변경 (Grafana→ECharts, Redis→Valkey, TimescaleDB→QuestDB). PRD 문서 작성 |
| v3.2 | 2026-03-21 | **Spec-Driven Harness Engineering 방법론 채택**. 기술 스택 변경(NestJS→FastAPI, Next.js→React+Vite, TimescaleDB/QuestDB→PostgreSQL 16 네이티브). Spec 문서 체계, 하네스 규칙, 개발 사이클 정의. Claude Code Skills 21종 구축 |
| v3.3 | 2026-03-23 | **5대 차별화 전략 추가**: DS-1 DB Copilot(ToT, GaussMaster 참조), DS-2 MTL 기반 통합 RCA(4-Head), DS-3 Explainable AI(Confidence Score+Reasoning Chain), DS-4 LLM Observability, DS-5 Zero-Sampling. **신규 FR**: FR-AI-010~014. **MVP 보강**: 경량 RAG/RCA/Confidence Score/MTL Lite를 Phase 1에 포함. 2026 AIOps 시장 갭 분석 반영 |

---

*— 문서 끝 —*
