---
name: gen-nl2sql
description: Optimize and extend the NL2SQL natural language to SQL system. Manages prompt engineering, schema context, safety validations, and query generation. References NL2SQL_SPEC.md for architecture and safety rules.
argument-hint: "[action: prompt|schema|safety|test|extend]"
allowed-tools: Read, Write, Glob, Grep, Edit, Bash
---

# NL2SQL System Management

You are managing the **NeuralDB NL2SQL** system per `docs/specs/ai/NL2SQL_SPEC.md`.

## Spec Reference

**항상 먼저 읽기**: `docs/specs/ai/NL2SQL_SPEC.md`

## Actions

### `/gen-nl2sql prompt` — System Prompt 최적화

1. Read `backend/app/services/nl2sql.py` → `_NL2SQL_SYSTEM_PROMPT`
2. Read `docs/specs/ai/NL2SQL_SPEC.md` §3 (프롬프트 설계)
3. 현재 프롬프트의 문제점 분석:
   - 테이블 스키마 정확성 (ERD.md와 대조)
   - 예시 쿼리 포함 여부 (Few-shot)
   - JSONB 필드 접근 패턴 안내 여부 (`metrics->>'cpu_usage'`)
   - 시간 관련 함수 안내 (`date_trunc`, `CURRENT_DATE`)
4. 개선된 프롬프트 생성

### `/gen-nl2sql schema` — Schema Context 갱신

1. Read `docs/specs/data-model/ERD.md` → 실제 테이블 구조
2. Read `backend/app/models/` → ORM 모델에서 컬럼 추출
3. `_NL2SQL_SYSTEM_PROMPT`의 SCHEMA 섹션을 ERD와 동기화
4. 새 테이블이 추가되었으면 프롬프트에 반영

### `/gen-nl2sql safety` — 안전 장치 점검

1. Read `backend/app/services/nl2sql.py` → 5계층 검증 코드
2. NL2SQL_SPEC.md §4 (안전 장치)와 대조
3. 새로운 위험 패턴 검토:
   - PL/pgSQL 블록 (`DO $$`)
   - 서브쿼리 기반 write (`SELECT * FROM (DELETE ...)`)
   - Information schema 과도 접근
4. 누락된 차단 패턴이 있으면 추가 제안

### `/gen-nl2sql test` — 테스트 생성

1. Read `docs/specs/ai/NL2SQL_SPEC.md` §10 (인수 기준)
2. AC별 테스트 작성 또는 갱신
3. 예시 질의 §8을 사용하여 LLM 응답 mock 테스트
4. 안전 장치별 negative 테스트 (write 시도, 위험 함수, 민감 테이블)

### `/gen-nl2sql extend` — Phase 2 확장

1. Read NL2SQL_SPEC.md §11 (확장 계획)
2. 선택한 기능 구현:
   - `explain`: EXPLAIN ANALYZE 자연어 해석
   - `optimize`: SQL 최적화 제안
   - `history`: 질의 이력 API
   - `feedback`: 👍/👎 피드백 저장
   - `target-db`: 대상 DB 직접 쿼리

## 안전 규칙 (MUST)

- NL2SQL 관련 코드 수정 시 **반드시 5계층 안전 장치 유지**
- `_validate_sql_readonly()` 함수를 **절대 약화시키지 않음**
- 새 테이블을 Schema Context에 추가할 때 `_BLOCKED_TABLES`도 검토
- 모든 변경 후 `uv run pytest tests/unit/test_nl2sql* -v` 실행
