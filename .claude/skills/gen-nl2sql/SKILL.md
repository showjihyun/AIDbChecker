---
name: gen-nl2sql
description: Manage the NL2GraphRAG system — GraphRAG-based natural language to SQL. Handles schema graph building, prompt engineering, graph retrieval, safety validations, and query generation. Phase 1 is basic NL2SQL, Phase 2 adds GraphRAG (Knowledge Graph + pgvector). References NL2SQL_SPEC.md.
argument-hint: "[action: prompt|schema|graph|safety|test|extend]"
allowed-tools: Read, Write, Glob, Grep, Edit, Bash
---

# NL2GraphRAG System Management

You are managing the **NeuralDB NL2GraphRAG** system per `docs/specs/ai/NL2SQL_SPEC.md`.

> **핵심 변경**: 기존 NL2SQL(하드코딩 스키마)에서 NL2GraphRAG(Knowledge Graph 기반)로 전환 중.
> Phase 1 = 기본 NL2SQL (현재), Phase 2 = GraphRAG, Phase 3 = Multi-Agent.

## Spec Reference

**항상 먼저 읽기**: `docs/specs/ai/NL2SQL_SPEC.md`

## Actions

### `/gen-nl2sql prompt` — LLM Prompt 최적화

1. Read `backend/app/services/nl2sql.py` → `_NL2SQL_SYSTEM_PROMPT`
2. Read Spec §3 (프롬프트 설계)
3. Phase 1: 하드코딩 스키마 프롬프트 개선
4. Phase 2: Subgraph Context 기반 동적 프롬프트로 전환

### `/gen-nl2sql schema` — Schema Context 갱신

**Phase 1** (현재):
1. Read ERD.md → 테이블 구조 확인
2. `_NL2SQL_SYSTEM_PROMPT` SCHEMA 섹션 동기화

**Phase 2** (GraphRAG):
1. Read Spec §3.4 (Schema → Graph 자동 생성)
2. `SchemaGraphBuilder` 구현/갱신
3. information_schema → graph_nodes/graph_edges 변환

### `/gen-nl2sql graph` — Knowledge Graph 관리 (Phase 2)

1. Read Spec §3 (Schema Knowledge Graph)
2. graph_nodes/graph_edges Alembic 마이그레이션 생성
3. SchemaGraphBuilder 구현
4. GraphRAGRetriever 구현
5. 비즈니스 메트릭/개념 노드 등록 API

### `/gen-nl2sql safety` — 안전 장치 점검

1. Read `backend/app/services/nl2sql.py` → 5계층 검증 코드
2. Spec §5와 대조
3. 새 위험 패턴 검토 (PL/pgSQL, 서브쿼리 write, information_schema)
4. GraphRAG 전환 후에도 5계층이 유지되는지 확인

### `/gen-nl2sql test` — 테스트 생성

1. Read Spec §10 (인수 기준)
2. Phase 1 AC-1~10 테스트 + Phase 2 AC-11~17 테스트
3. GraphRAG retrieval 정확도 테스트 (mock graph)
4. 안전 장치 negative 테스트

### `/gen-nl2sql extend` — Phase 2/3 확장

1. Read Spec §8 (구현 마일스톤)
2. 선택한 기능 구현:
   - `graph`: Schema → Knowledge Graph 생성
   - `retriever`: GraphRAG Retrieval
   - `planner`: Query Planner
   - `validator`: SQL Validator (EXPLAIN cost check)
   - `explain`: EXPLAIN ANALYZE 자연어 해석
   - `optimize`: SQL 최적화 제안
   - `history`: 질의 이력 API
   - `feedback`: 피드백 학습
   - `target-db`: 대상 DB 직접 쿼리

## NL2GraphRAG 아키텍처 요약

```
Phase 1 (현재):  Question → LLM(하드코딩 스키마) → SQL → Execute
Phase 2 (다음):  Question → Embedding → Graph Search → Subgraph
                  → Query Planner → SQL Generator → Validate → Execute
Phase 3 (최종):  Question → Planner Agent → Schema Agent
                  → SQL Agent → Validator Agent → Execute
```

## 안전 규칙 (MUST)

- NL2SQL 코드 수정 시 **반드시 5계층 안전 장치 유지**
- `_validate_sql_readonly()` 함수를 **절대 약화시키지 않음**
- GraphRAG 전환 시에도 SQL 실행 전 5계층 검증 필수
- 모든 변경 후 `uv run pytest tests/unit/test_nl2sql* -v` 실행
