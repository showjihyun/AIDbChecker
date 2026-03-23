# Spec-Driven Test Generation Strategy

> **Spec ID**: TEST-STRATEGY-001
> **PRD 참조**: §2 Spec-Driven Harness Engineering
> **상태**: Approved
> **원칙**: Spec이 변경되면 테스트가 자동 추적되어 변경된다

---

## 1. 핵심 원칙

### 1.1 Spec = Test의 Single Source of Truth

```
Feature Spec (WHAT to test)
    ↓ 매핑 테이블 (이 문서 §3)
Test Code (HOW to test)
    ↓ CI/CD
실행 결과 → Spec 인수 기준(AC) 충족 여부 판정
```

| 규칙 | 설명 |
|------|------|
| **Spec-First Testing** | 테스트는 반드시 Feature Spec의 AC(인수 기준)에서 파생된다 |
| **Spec Reference 필수** | 모든 테스트 함수/컴포넌트에 `# Spec: FS-AI-010 AC-1` 형태로 참조 명시 |
| **Spec 변경 → 테스트 변경** | Spec AC가 추가/수정/삭제되면 대응 테스트도 추가/수정/삭제 |
| **No Spec-Free Test** | Spec에 없는 기능의 테스트는 작성하지 않는다 (유틸리티/헬퍼 제외) |
| **AC 미충족 = 구현 미완료** | 테스트 실패 시 코드를 수정하지, 테스트를 수정하지 않는다 |

### 1.2 하네스 엔지니어링 워크플로우

```
1. 인간: Feature Spec 작성 (AC 정의)
2. 하네스: /gen-test → Spec AC에서 테스트 코드 자동 생성
3. 하네스: /gen-fastapi-route 또는 /gen-component → 구현 코드 생성
4. CI: 테스트 실행 → AC 충족 여부 자동 판정
5. 인간: Spec AC 변경 시 → 하네스가 테스트 자동 갱신
```

---

## 2. Spec → Test 매핑 규칙

### 2.1 Backend (Python / pytest)

#### 테스트 파일 네이밍

```
Spec 파일:     docs/specs/ai/MTL_RCA_SPEC.md
테스트 파일:   backend/tests/unit/test_mtl_rca.py      (단위)
              backend/tests/api/test_mtl_api.py        (API)
              backend/tests/integration/test_mtl_e2e.py (통합)
```

#### 테스트 함수 네이밍

```python
# 규칙: test_{spec_id}_{ac_number}_{description}
# Spec: FS-AI-010 AC-1

async def test_fs_ai_010_ac1_mtl_predict_returns_4_heads():
    """FS-AI-010 AC-1: POST /mtl/predict 호출 시 4개 Head 결과 반환"""
    # Spec: FS-AI-010 AC-1
    ...
```

#### Spec 참조 데코레이터

```python
# backend/tests/conftest.py

import pytest

def spec_ref(spec_id: str, ac: str):
    """테스트에 Spec 참조를 부착하는 마커"""
    return pytest.mark.spec(spec_id=spec_id, ac=ac)

# 사용:
@spec_ref("FS-AI-010", "AC-1")
async def test_mtl_predict_returns_4_heads():
    ...

@spec_ref("FS-AI-010", "AC-2")
async def test_mtl_confidence_score_range():
    ...
```

#### Spec AC → pytest 자동 수집

```python
# backend/tests/conftest.py

def pytest_collection_modifyitems(config, items):
    """Spec 참조가 없는 테스트에 경고 마커 부착"""
    for item in items:
        if not any(m.name == "spec" for m in item.iter_markers()):
            item.add_marker(pytest.mark.warn_no_spec)

def pytest_terminal_summary(terminalreporter):
    """테스트 결과를 Spec AC별로 그룹화하여 요약 출력"""
    spec_results = {}
    for report in terminalreporter.stats.get("passed", []):
        for marker in report.item.iter_markers("spec"):
            key = f"{marker.kwargs['spec_id']} {marker.kwargs['ac']}"
            spec_results.setdefault(key, []).append("PASS")
    for report in terminalreporter.stats.get("failed", []):
        for marker in report.item.iter_markers("spec"):
            key = f"{marker.kwargs['spec_id']} {marker.kwargs['ac']}"
            spec_results.setdefault(key, []).append("FAIL")

    terminalreporter.write_sep("=", "SPEC ACCEPTANCE CRITERIA SUMMARY")
    for spec_ac, results in sorted(spec_results.items()):
        status = "✅" if all(r == "PASS" for r in results) else "❌"
        terminalreporter.write_line(f"  {status} {spec_ac} ({len(results)} tests)")
```

### 2.2 Frontend (TypeScript / Vitest)

#### 테스트 파일 네이밍

```
Spec 파일:     docs/specs/ai/CONFIDENCE_SCORE_SPEC.md §2.5 UI
테스트 파일:   frontend/src/components/common/ConfidenceBadge/ConfidenceBadge.test.tsx
```

#### Spec 참조 패턴

```typescript
// frontend/src/components/common/ConfidenceBadge/ConfidenceBadge.test.tsx

/**
 * @spec FS-AI-011 AC-4
 * @description Confidence Badge가 4단계 색상 코딩으로 표시
 */
describe('ConfidenceBadge [Spec: FS-AI-011]', () => {
  // Spec: FS-AI-011 AC-4 — HIGH 등급 녹색 배지
  it('renders green badge for confidence >= 0.8', () => {
    render(<ConfidenceBadge confidence={0.87} />);
    const badge = screen.getByTestId('confidence-badge');
    expect(badge).toHaveClass('bg-tertiary-container');
    expect(badge).toHaveTextContent('0.87');
    expect(badge).toHaveTextContent('HIGH');
  });

  // Spec: FS-AI-011 AC-4 — VERY_LOW 등급 빨간 배지
  it('renders red badge for confidence < 0.3', () => {
    render(<ConfidenceBadge confidence={0.18} />);
    const badge = screen.getByTestId('confidence-badge');
    expect(badge).toHaveClass('bg-error-container');
    expect(badge).toHaveTextContent('VERY_LOW');
  });
});
```

#### Vitest Spec Reporter

```typescript
// frontend/tests/spec-reporter.ts
import type { Reporter } from 'vitest';

const specPattern = /@spec\s+(FS-[\w-]+)\s+(AC-\d+)/;

export default class SpecReporter implements Reporter {
  onFinished(files: any[]) {
    const specResults = new Map<string, { pass: number; fail: number }>();

    for (const file of files) {
      for (const task of file.tasks) {
        const match = task.name?.match(specPattern);
        if (match) {
          const key = `${match[1]} ${match[2]}`;
          const entry = specResults.get(key) || { pass: 0, fail: 0 };
          task.result?.state === 'pass' ? entry.pass++ : entry.fail++;
          specResults.set(key, entry);
        }
      }
    }

    console.log('\n=== SPEC AC COVERAGE ===');
    for (const [spec, { pass, fail }] of specResults) {
      const icon = fail === 0 ? '✅' : '❌';
      console.log(`  ${icon} ${spec} (${pass} pass, ${fail} fail)`);
    }
  }
}
```

---

## 3. Spec → Test 전체 매핑 테이블

### 3.1 MVP Feature Specs → 테스트

| Spec | AC | Backend Test | Frontend Test | Layer |
|------|-----|-------------|---------------|-------|
| **FS-AI-010 (MTL RCA)** | | | | |
| | AC-1 | `test_mtl_api.py::test_predict_returns_4_heads` | - | API |
| | AC-2 | `test_mtl_rca.py::test_confidence_weighted_average` | - | Unit |
| | AC-3 | `test_mtl_rca.py::test_reasoning_chain_min_3_steps` | - | Unit |
| | AC-4 | `test_mtl_rca.py::test_evidence_links_valid_paths` | - | Unit |
| | AC-5 | `test_mtl_rca.py::test_llm_failure_graceful_degradation` | - | Unit |
| | AC-6 | `test_mtl_rca.py::test_rag_results_in_prompt` | - | Unit |
| | AC-7 | `test_mtl_api.py::test_feedback_saves_correctly` | - | API |
| | AC-8 | `test_mtl_e2e.py::test_incident_to_prediction_under_30s` | - | Integration |
| | AC-9 | `test_mtl_rca.py::test_prediction_persisted_to_db` | - | Unit |
| **FS-AI-011 (Confidence)** | | | | |
| | AC-1 | `test_confidence.py::test_all_outputs_have_xai_fields` | - | Unit |
| | AC-2 | `test_confidence.py::test_low_confidence_blocks_execution` | - | Unit |
| | AC-3 | `test_confidence.py::test_medium_confidence_forces_l2` | - | Unit |
| | AC-4 | - | `ConfidenceBadge.test.tsx::renders_4_color_grades` | Component |
| | AC-5 | - | `ReasoningChain.test.tsx::expands_step_panel` | Component |
| | AC-6 | - | `EvidenceLink.test.tsx::navigates_to_data_page` | Component |
| | AC-7 | `test_confidence_api.py::test_feedback_aggregation` | - | API |
| | AC-8 | `test_confidence.py::test_weighted_average_formula` | - | Unit |
| **FS-AI-RAG-001 (경량 RAG)** | | | | |
| | AC-1 | `test_rag.py::test_embedding_created_on_incident` | - | Unit |
| | AC-2 | `test_rag_api.py::test_search_under_200ms` | - | API |
| | AC-3 | `test_rag.py::test_same_type_similarity_gte_085` | - | Unit |
| | AC-4 | `test_rag.py::test_different_type_similarity_lt_05` | - | Unit |
| | AC-5 | `test_rag.py::test_rag_results_inserted_in_mtl_prompt` | - | Unit |
| | AC-6 | `test_rag.py::test_reembedding_on_resolution` | - | Unit |
| | AC-7 | `test_rag.py::test_hnsw_index_used_in_explain` | - | Integration |
| | AC-8 | `test_rag_api.py::test_status_endpoint` | - | API |
| | AC-9 | `test_rag.py::test_valkey_cache_hit_under_10ms` | - | Integration |

### 3.2 MVP 인수 기준 → 통합/E2E 테스트

| AC | 테스트 파일 | Layer |
|----|-----------|-------|
| AC-1 | `test_metric_collection.py::test_concurrent_10_instances` | Integration |
| AC-2 | `test_ash.py::test_ash_heatmap_realtime` | Integration |
| AC-3 | `test_baseline.py::test_anomaly_detection_after_2weeks` | Integration |
| AC-4 | `test_alerts.py::test_slack_alert_under_30s` | Integration |
| AC-5 | `test_nl2sql.py::test_top5_slow_queries` | Integration |
| AC-6 | `test_auth.py::test_rbac_viewer_no_write` | API |
| AC-7 | `test_e2e_dashboard.py::test_initial_load_under_3s` | E2E |
| AC-8 | `test_schema_changes.py::test_ddl_detection` | Integration |
| AC-9 | `test_audit.py::test_all_changes_logged` | Integration |
| AC-10 | `test_e2e_docker.py::test_docker_compose_up` | E2E |
| AC-11 | `test_mtl_e2e.py::test_incident_to_rca_under_30s` | Integration |
| AC-12 | `test_mtl_e2e.py::test_mtl_lite_4_tasks_simultaneous` | Integration |
| AC-13 | `test_rag_e2e.py::test_pgvector_search_in_rca_context` | Integration |

### 3.3 Phase 2 Specs → 테스트 (사전 정의)

| Spec | 테스트 파일 | 상태 |
|------|-----------|------|
| FS-AI-012 (DB Copilot) | `test_copilot.py`, `test_copilot_api.py` | Phase 2 대기 |
| FS-AI-013 (LLM Observability) | `test_llm_obs.py`, `test_llm_obs_api.py`, `AIHealth.test.tsx` | Phase 2 대기 |

---

## 4. Spec 변경 시 테스트 추적 프로세스

### 4.1 변경 감지 흐름

```
1. Spec 문서 수정 (e.g., FS-AI-010에 AC-10 추가)
     ↓
2. /review-arch 실행 → 매핑 테이블(이 문서 §3)과 대조
     ↓
3. 누락된 테스트 식별 → 하네스에게 /gen-test 요청
     ↓
4. 테스트 코드 생성 (Spec 참조 포함)
     ↓
5. CI 실행 → Spec AC Summary 리포트
```

### 4.2 Spec 변경 유형별 테스트 대응

| Spec 변경 | 테스트 대응 | 예시 |
|-----------|-----------|------|
| **AC 추가** | 새 테스트 함수 추가 | AC-10 추가 → `test_fs_ai_010_ac10_xxx` 생성 |
| **AC 수정** (기준 변경) | 기존 테스트 assertion 수정 | "< 30초" → "< 20초" → timeout 값 변경 |
| **AC 삭제** | 테스트 함수 삭제 | AC-5 삭제 → `test_fs_ai_010_ac5_xxx` 삭제 |
| **API 경로 변경** | API 테스트 경로 수정 | `/mtl/predict` → `/rca/predict` |
| **스키마 변경** | Factory/Fixture 수정 | 필드 추가 → Factory에 필드 추가 |
| **Enum 변경** | 테스트 데이터 수정 | AnomalyType에 값 추가 → 테스트 케이스 추가 |

### 4.3 CI 리포트 형식

```
=== SPEC ACCEPTANCE CRITERIA SUMMARY ===
  ✅ FS-AI-010 AC-1 (2 tests)
  ✅ FS-AI-010 AC-2 (1 test)
  ❌ FS-AI-010 AC-3 (1 pass, 1 fail)    ← reasoning_chain 최소 3단계 미충족
  ✅ FS-AI-010 AC-4 (1 test)
  ...
  ✅ FS-AI-011 AC-4 (3 tests)           ← Frontend 컴포넌트
  ✅ FS-AI-RAG-001 AC-2 (1 test)

COVERAGE:
  Specs with tests:    12/15 (80%)
  ACs with tests:      38/42 (90%)
  ACs passing:         35/38 (92%)
  ACs failing:         3/38  (8%)

UNCOVERED SPECS:
  ⚠ FS-AI-012 (DB Copilot) — Phase 2, no tests yet
  ⚠ FS-AI-013 (LLM Observability) — Phase 2, no tests yet
```

---

## 5. /gen-test 스킬 연동

하네스가 `/gen-test` 스킬로 테스트를 생성할 때 이 문서를 참조합니다.

### 5.1 Backend 테스트 생성 규칙

```
입력:  Feature Spec (e.g., MTL_RCA_SPEC.md)
출력:  pytest 테스트 파일

규칙:
1. Spec의 AC 섹션에서 각 AC를 1개 이상의 테스트 함수로 변환
2. 함수명: test_{spec_id}_{ac}_{description} (snake_case)
3. @spec_ref 데코레이터 필수
4. API 엔드포인트 테스트: httpx AsyncClient + mock service
5. 비즈니스 로직 테스트: 직접 함수 호출 + mock 의존성
6. 통합 테스트: testcontainers + 실제 DB
```

### 5.2 Frontend 테스트 생성 규칙

```
입력:  Feature Spec (UI 컴포넌트 섹션) + FRONTEND_DESIGN.md
출력:  Vitest + RTL 테스트 파일

규칙:
1. Spec의 UI 컴포넌트 섹션에서 각 시각 요소를 테스트 케이스로 변환
2. describe 블록에 @spec 주석 필수
3. 사용자 관점 테스트 (getByRole, getByText)
4. 디자인 토큰 검증 (클래스명 또는 스타일 확인)
5. 접근성 검증 (ARIA label)
6. MSW 핸들러로 API 모킹
```

---

## 6. 의존성

- **참조**: BACKEND_TEST_SPEC.md, FRONTEND_TEST_SPEC.md, TEST_SPEC.md
- **사용**: 모든 Feature Spec (docs/specs/ai/*.md, API_SPEC.md, ERD.md)
- **도구**: pytest (conftest.py에 spec_ref), Vitest (SpecReporter)
