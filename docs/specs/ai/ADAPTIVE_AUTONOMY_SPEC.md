# Feature Spec: Adaptive Autonomy (5단계 자율 등급)

## 메타데이터
- **Spec ID**: FS-AUTO-002
- **PRD 참조**: FR-AUTO-002, FR-AUTO-005
- **우선순위**: P0 (MVP — L0~L1) / P1 (Phase 2 — L2) / Phase 3 (L3~L4)
- **상태**: Approved
- **선행 Spec**: AG-001 (Agent Architecture)
- **사용 Spec**: FS-AI-011 (Confidence Score), FS-AI-012 (DB Copilot), FS-AUTO-003 (Playbook Lite)
- **구현 파일**:
  - Backend: `backend/app/models/db_instance.py` (`autonomy_level` 컬럼)
  - API: `backend/app/api/v1/instances.py` (인스턴스 설정에 포함)
  - Agents: `backend/app/agents/` (Autonomy Gate 로직)

---

## 1. 개요

모든 AI 자동화 액션에 대해 **인스턴스별 자율 등급(0~4)**을 설정하여, AI가 수행할 수 있는 행동 범위를 동적으로 제어하는 시스템. 위험도가 높은 작업일수록 높은 등급이 필요하며, 낮은 등급에서는 사람의 승인이 필수입니다.

> **ADR-008 반영**: Phase 2에서는 L0~L2만 지원. L3/L4는 프로덕션 검증 후 Phase 3에서 개방.

---

## 2. Autonomy Level 정의

| Level | 이름 | 행동 | 사람 개입 | Phase |
|-------|------|------|----------|-------|
| **L0** | Monitor Only | 알림만 발송 | 모든 대응을 사람이 수행 | MVP |
| **L1** | Recommend | Playbook/액션 추천 표시 | 사람이 검토 후 승인/거부 | MVP |
| **L2** | Approve & Execute | 사람 승인 후 자동 실행 | 승인 워크플로우 필수 | Phase 2 |
| **L3** | Auto Execute | 자동 실행 → 결과 보고 | 실패 시에만 개입 | Phase 3 |
| **L4** | Full Autonomous | 완전 자율 + 에스컬레이션 | 에스컬레이션 시에만 | Phase 3 |

### 인스턴스별 설정

```python
# Spec: FR-AUTO-002
# db_instances.autonomy_level 컬럼 (DM-001 참조)
# 기본값: 0 (Monitor Only)
# 범위: 0~4 (Phase 2까지 0~2만 허용)

class DBInstance(Base):
    autonomy_level: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0
    )
```

---

## 3. Autonomy Gate (핵심 메커니즘)

모든 자동화 코드는 실행 전에 반드시 Autonomy Gate를 통과해야 합니다.

### 3.1 Gate 로직

```python
# Spec: FR-AUTO-002
async def check_autonomy(
    instance_id: UUID,
    action_risk: str,          # low / medium / high / critical
    confidence_score: float,   # FS-AI-011
) -> AutonomyDecision:
    """Autonomy Gate — 모든 쓰기 액션 전 필수 호출"""

    instance = await get_instance(instance_id)
    level = instance.autonomy_level

    # Phase 2: L3/L4 차단
    if level > 2:
        raise AutonomyError("L3/L4 not available until Phase 3")

    # Confidence Score 연동 (FS-AI-011)
    if confidence_score < 0.5:
        return AutonomyDecision(
            allowed=False,
            reason="confidence_too_low",
            required_action="manual_review",
        )

    # Risk-Level 매핑
    min_level_for_risk = {
        "low": 1,       # L1 이상이면 추천 가능
        "medium": 2,    # L2 이상이면 승인 후 실행
        "high": 2,      # L2 이상 + 승인 필수
        "critical": 3,  # L3 이상 (Phase 3까지 수동만)
    }

    required = min_level_for_risk[action_risk]

    if level < required:
        return AutonomyDecision(
            allowed=False,
            reason="insufficient_autonomy",
            current_level=level,
            required_level=required,
            required_action="approval" if level >= 1 else "manual",
        )

    if level == 2 and action_risk in ("medium", "high"):
        return AutonomyDecision(
            allowed=True,
            requires_approval=True,
            reason="approval_required",
        )

    return AutonomyDecision(allowed=True, requires_approval=False)
```

### 3.2 Decision 스키마

```python
# Spec: FR-AUTO-002
class AutonomyDecision(BaseModel):
    allowed: bool
    requires_approval: bool = False
    reason: str
    current_level: int | None = None
    required_level: int | None = None
    required_action: str | None = None  # manual / approval / auto
```

---

## 4. Level별 행동 매트릭스

### Phase 2 (L0~L2)

| 액션 유형 | Risk | L0 | L1 | L2 |
|----------|------|-----|-----|-----|
| 알림 발송 | - | ✅ 자동 | ✅ 자동 | ✅ 자동 |
| 인시던트 생성 | - | ✅ 자동 | ✅ 자동 | ✅ 자동 |
| Playbook 추천 표시 | low | ❌ | ✅ UI 표시 | ✅ UI 표시 |
| pg_cancel_backend | low | ❌ | ✅ 추천만 | ✅ 승인후 실행 |
| VACUUM ANALYZE | low | ❌ | ✅ 추천만 | ✅ 승인후 실행 |
| pg_terminate_backend | medium | ❌ | ✅ 추천만 | ✅ 승인후 실행 |
| CREATE INDEX CONCURRENTLY | medium | ❌ | ❌ | ✅ 승인후 실행 |
| ALTER SYSTEM SET | high | ❌ | ❌ | ✅ 승인후 실행 |
| DROP INDEX / REINDEX | high | ❌ | ❌ | ✅ 승인후 실행 |
| Failover / PROMOTE | critical | ❌ | ❌ | ❌ (Phase 3 L3+) |

### Phase 3 추가 (L3~L4)

| 액션 유형 | Risk | L3 | L4 |
|----------|------|-----|-----|
| pg_terminate_backend | medium | ✅ 자동 | ✅ 자동 |
| CREATE INDEX | medium | ✅ 자동 → 보고 | ✅ 자동 |
| ALTER SYSTEM SET | high | ✅ 자동 → 보고 | ✅ 자동 |
| Failover | critical | ✅ 자동 → 즉시 보고 | ✅ 자동 |

---

## 5. Autonomy 변경 규칙

### 5.1 수동 변경 (Phase 2)

```
관리자가 인스턴스 설정에서 Autonomy Level 변경
    → audit_logs에 기록 (WHO/WHAT/WHEN)
    → 변경 즉시 적용
```

- **권한**: Super Admin / DB Admin만 변경 가능
- **범위**: Phase 2에서 0~2만 설정 가능

### 5.2 동적 격하 (Phase 3 — FR-AUTO-005)

> Phase 2에서는 미구현. Phase 3에서 운영 데이터 축적 후 도입.

```
Playbook 실행 실패
    → 해당 Playbook의 Autonomy Level 1단계 자동 격하
    → 연속 실패 (3회) 시 L0으로 강제 격하
    → 관리자에게 알림
```

---

## 6. API

### 인스턴스 Autonomy Level 조회/변경

인스턴스 CRUD API에 포함 (별도 엔드포인트 불필요):

```python
# PUT /api/v1/instances/{id}
# Request Body에 autonomy_level 포함
class InstanceUpdate(BaseModel):
    autonomy_level: int | None = Field(None, ge=0, le=2)  # Phase 2: 0~2
```

### Autonomy Decision 조회 (디버깅/감사용)

| Method | Path | Description | Phase |
|--------|------|-------------|-------|
| GET | `/api/v1/instances/{id}/autonomy` | 현재 Autonomy 설정 + 최근 결정 이력 | Phase 2 |

---

## 7. 인수 기준 (Acceptance Criteria)

### Phase 2 (MVP + Phase 2)
- [ ] **AC-1**: 인스턴스 생성 시 `autonomy_level` 기본값 0으로 설정
- [ ] **AC-2**: 관리자가 인스턴스 설정에서 Autonomy Level 0~2 변경 가능
- [ ] **AC-3**: L0 인스턴스에서 Playbook 실행 시도 시 차단 + 알림만 발송
- [ ] **AC-4**: L1 인스턴스에서 인시던트 발생 시 매칭 Playbook이 UI에 추천으로 표시
- [ ] **AC-5**: L2 인스턴스에서 Playbook 승인 후 자동 실행 + 결과 보고
- [ ] **AC-6**: Confidence < 0.5 시 모든 Level에서 자동 대응 차단
- [ ] **AC-7**: Autonomy Level 변경이 audit_logs에 기록됨
- [ ] **AC-8**: Phase 2에서 L3/L4 설정 시도 시 거부 (ValidationError)

### Phase 3
- [ ] **AC-9**: L3/L4 설정 허용
- [ ] **AC-10**: L3에서 자동 실행 → 결과 보고 동작
- [ ] **AC-11**: 실패 시 동적 Autonomy 격하 동작

---

## 8. 의존성

- **선행 Spec**: AG-001 (Agent Architecture — Remediation Agent가 Gate 호출)
- **사용 Spec**:
  - FS-AI-011 (Confidence Score — Gate에서 Confidence 체크)
  - FS-AI-012 (DB Copilot — Autonomy Level에 따라 실행/추천 분기)
  - FS-AUTO-003 (Playbook Lite — Playbook 실행 시 Gate 필수)
- **데이터 모델**: DM-001 (`db_instances.autonomy_level` 컬럼)
- **ADR**: ADR-008 (Phase 2에서 L0~L2만 지원)
