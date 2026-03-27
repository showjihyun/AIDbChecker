# ADR-008: 경량 Playbook + DB Copilot 하이브리드 전략

- **Status**: Accepted
- **Date**: 2026-03-26
- **Deciders**: Project Lead
- **관련 Spec**: FS-AUTO-003 (Playbook), FS-AI-012 (DB Copilot)

## Context

PRD v3.3은 Playbook-as-Code(FR-AUTO-003)를 P0 기능으로 정의하고, Phase 2에서 전체 구현을 계획했다. 그러나 구현 범위를 검토한 결과:

1. **구현 비용 과다**: YAML 파서, 템플릿 엔진, 단계별 실행기, 롤백 엔진, SLO 검증, 승인 워크플로우(UI+WebSocket), Git PR 연동, LLM Playbook 자동 생성 — 사실상 워크플로우 엔진 신규 개발 수준
2. **DB Copilot과 기능 중복**: Playbook은 "사전 정의된 절차"이고 DB Copilot(ToT)은 "실시간 LLM 판단". 고급 시나리오에서 DB Copilot이 Playbook을 대체 가능
3. **고객 사용 패턴 의문**: 타겟 고객(금융/공공)은 DB 자동 실행에 보수적. 대부분 Autonomy L0(알림)~L1(추천)에 머물 가능성 → Playbook 실행 기회 제한적
4. **경쟁 분석**: Xata Agent만 Playbook 기반 자동 대응 제공. 나머지 경쟁자는 Playbook 미지원. 시장 필수 기능은 아님

동시에 Playbook을 완전히 제거하면:
- Self-Healing Closed-Loop 구현 불가 (핵심 차별점 상실)
- Adaptive Autonomy가 L0(알림)에 영원히 머무름
- 표준화된 대응 절차/감사 추적 불가

## Decision

**대안 C: 경량 Playbook(Lite) + DB Copilot 하이브리드 전략을 채택한다.**

위험 수준에 따라 Playbook과 DB Copilot을 분리 적용:

```
┌─ 고위험 (DDL 변경, 파라미터 변경) ── Built-in Playbook (검증된 절차만)
│
├─ 중위험 (세션 kill, VACUUM) ──────── DB Copilot 판단 + Playbook 참조
│
└─ 저위험 (조회, 분석, 추천) ────────── DB Copilot 자유 실행
```

### Phase 2에서 구현 (Playbook Lite)

| 항목 | 포함 |
|------|------|
| 7개 Built-in Playbook 템플릿 | YAML, 시스템 내장 (읽기 전용) |
| 단계별 실행 + 롤백 | 기본 실행 엔진 (순차 실행, 실패 시 역순 롤백) |
| Autonomy Gate | L0~L2만 (L3/L4는 Phase 3) |
| 실행 이력 저장 | `remediation_logs` 테이블 |
| Confidence Score 연동 | Confidence < 0.5 시 자동 차단 |
| 수동 트리거 | 관리자가 UI에서 Playbook 선택 → 실행 |

### Phase 2에서 제외 → Phase 3으로 연기

| 항목 | 연기 사유 |
|------|----------|
| LLM Playbook 자동 생성 | DB Copilot이 실시간 판단으로 대체 |
| Git PR 연동 워크플로우 | Built-in Playbook은 코드 배포로 관리, 런타임 Git 연동 불필요 |
| 커스텀 Playbook YAML 편집기 (UI) | Phase 2는 Built-in만 제공 |
| SLO 자동 검증 (before/after) | Phase 2는 수동 확인, Phase 3에서 자동화 |
| 동적 Autonomy 격하 (FR-AUTO-005) | Phase 3에서 운영 데이터 축적 후 도입 |
| Autonomy L3/L4 | 프로덕션 검증 없이 완전 자율 실행은 위험 |
| 커스텀 Playbook 작성 | Phase 3에서 Built-in 검증 후 개방 |

### DB Copilot 역할 확장

DB Copilot(FS-AI-012)이 Playbook을 보완하는 역할:

| DB Copilot 역할 | 설명 |
|-----------------|------|
| 저위험 작업 자유 실행 | 조회, EXPLAIN 분석, 추천 생성 |
| Playbook 선택 보조 | ToT 분기 결과에 따라 적합한 Built-in Playbook 추천 |
| Playbook 없는 신규 장애 | LLM이 실시간 분석 → 추천 액션 제시 (실행은 사람 승인) |
| Phase 3 Playbook 생성 후보 | DB Copilot이 반복 추천한 패턴 → 운영자가 Playbook으로 승격 |

## Consequences

### Positive
- Phase 2 구현 비용 ~60% 절감 (워크플로우 엔진 → 기본 실행기)
- Self-Healing 핵심 가치 유지 (Built-in Playbook으로 표준 대응 + 감사 추적)
- DB Copilot과의 시너지 (정형 대응 + 비정형 판단)
- 점진적 신뢰 구축 (L0~L2 → 검증 후 L3/L4 개방)

### Negative
- 커스텀 Playbook 요구 고객은 Phase 3까지 대기
- Built-in 7개 외 시나리오는 DB Copilot 추천 → 수동 실행
- LLM Playbook 자동 생성 차별점이 Phase 3으로 연기

### Risk Mitigation
- Built-in 7개가 PostgreSQL 장애의 ~80%를 커버하도록 설계 (lock, index, vacuum, replication, connection, query, memory)
- DB Copilot이 나머지 ~20%를 추천 모드로 커버
- Phase 3 전환 시 Built-in → 커스텀 확장은 YAML 스키마 호환 유지
