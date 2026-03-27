# Feature Spec: NL2GraphRAG — GraphRAG 기반 자연어 DB 질의 시스템

## 메타데이터
- **Spec ID**: FS-AI-NL2SQL-001
- **PRD 참조**: FR-AI-003, MVP-AI-004, MVP-AI-005
- **우선순위**: P0 (MVP→Phase 2 확장)
- **상태**: Partial (MVP: 기본 NL2SQL 구현, Phase 2: GraphRAG 전환)
- **선행 Spec**: FS-AI-LLM-001 (LLM Provider), DM-001 (ERD)
- **구현 파일**:
  - Backend: `backend/app/services/nl2sql.py`, `backend/app/services/graph_rag.py`, `backend/app/api/v1/nl2sql.py`
  - Frontend: `frontend/src/components/nl2sql/NL2SQLChat.tsx`
  - Test: `backend/tests/unit/test_nl2sql_spec.py`
  - Skill: `.claude/skills/gen-nl2sql/SKILL.md`

---

## 1. 개요

### 1.1 왜 NL2SQL → NL2GraphRAG인가

기존 NL2SQL의 한계:

| 문제 | 기존 NL2SQL | NL2GraphRAG 해결 |
|------|-----------|-----------------|
| **스키마 규모** | 프롬프트에 전체 스키마 불가 (300+ 테이블) | Graph에서 관련 5개만 추출 |
| **Join 경로** | LLM이 FK 관계를 모름 → 잘못된 JOIN | Graph Edge로 자동 발견 |
| **비즈니스 시맨틱** | `active_customer` 같은 메트릭 이해 불가 | Business Concept 노드로 매핑 |
| **정확도** | ~60% | **~80-90%** |

### 1.2 진화 경로

```
Phase 1 (MVP, 현재): 기본 NL2SQL
  → LLM + 하드코딩 스키마 프롬프트
  → 시스템 DB 쿼리만

Phase 2 (GraphRAG 전환): NL2GraphRAG
  → Schema → Knowledge Graph 자동 생성
  → Graph Retrieval → Subgraph → Query Plan → SQL
  → 대상 DB 직접 쿼리 지원

Phase 3 (Agent 기반): Multi-Agent NL2GraphRAG
  → Planner Agent + Schema Agent + SQL Agent + Validator Agent
  → 멀티 DB (PostgreSQL + MySQL + MSSQL)
```

---

## 2. NL2GraphRAG 아키텍처

```
사용자 질의: "지난달 가장 느린 쿼리를 실행한 인스턴스는?"
    ↓
┌─ Step 1: NL Understanding ───────────────────────┐
│  질의 의도 파악 + 핵심 엔티티 추출                  │
│  → entities: [쿼리, 인스턴스, 지난달]              │
│  → intent: aggregation + time_filter + ranking    │
└───────────────────────────────────────────────────┘
    ↓
┌─ Step 2: GraphRAG Retrieval ─────────────────────┐
│  2a. Query Embedding                              │
│      embedding("지난달 가장 느린 쿼리 인스턴스")    │
│  2b. Graph Node Retrieval (pgvector 유사도)        │
│      → active_sessions, db_instances, metric_...  │
│  2c. Subgraph Generation                          │
│      db_instances ← active_sessions (FK)          │
│      → 관련 컬럼 + Join 경로 추출                  │
└───────────────────────────────────────────────────┘
    ↓
┌─ Step 3: Query Planner ──────────────────────────┐
│  Graph 기반 실행 계획 생성                         │
│  1. active_sessions에서 duration_ms 집계           │
│  2. db_instances JOIN (인스턴스명)                  │
│  3. 지난달 필터 (sampled_at >= ...)               │
│  4. GROUP BY instance → AVG(duration_ms)          │
│  5. ORDER BY DESC → LIMIT 10                      │
└───────────────────────────────────────────────────┘
    ↓
┌─ Step 4: SQL Generator ──────────────────────────┐
│  Planner 결과 → PostgreSQL SQL 생성               │
│  + 5계층 안전 검증 (§5)                           │
└───────────────────────────────────────────────────┘
    ↓
┌─ Step 5: SQL Validator + Execution ──────────────┐
│  schema validation + execution test               │
│  + query cost check                               │
│  → 읽기 전용 실행 → 결과 반환                     │
└───────────────────────────────────────────────────┘
```

---

## 3. Schema Knowledge Graph

### 3.1 Graph 노드 유형

| Node Type | 소스 | 설명 | 예시 |
|-----------|------|------|------|
| **Table** | `pg_tables`, `information_schema` | DB 테이블 | `active_sessions` |
| **Column** | `pg_attribute`, `information_schema.columns` | 테이블 컬럼 | `active_sessions.duration_ms` |
| **Metric** | 수동 정의 / 자동 추출 | 비즈니스 메트릭 | `avg_query_time`, `tps` |
| **BusinessConcept** | 수동 정의 | 비즈니스 용어 | `slow_query`, `active_customer` |

### 3.2 Graph 엣지 유형

| Edge Type | 소스 | 설명 | 예시 |
|-----------|------|------|------|
| `HAS_COLUMN` | `table → column` | 테이블-컬럼 관계 | `active_sessions → duration_ms` |
| `FOREIGN_KEY` | `pg_constraint` | FK 관계 | `active_sessions.instance_id → db_instances.id` |
| `METRIC_SOURCE` | 수동 | 메트릭 ← 컬럼 | `avg_query_time ← active_sessions.duration_ms` |
| `CONCEPT_MAP` | 수동 | 비즈니스 용어 → 메트릭 | `slow_query → avg_query_time` |

### 3.3 Graph 저장 (PostgreSQL + pgvector)

```sql
-- Graph 노드 테이블
CREATE TABLE graph_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_type VARCHAR(20) NOT NULL,    -- table / column / metric / concept
    name VARCHAR(255) NOT NULL,
    description TEXT,
    metadata JSONB DEFAULT '{}',
    embedding VECTOR(384) NOT NULL,    -- sentence-transformers
    instance_id UUID REFERENCES db_instances(id),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Graph 엣지 테이블
CREATE TABLE graph_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES graph_nodes(id),
    target_id UUID NOT NULL REFERENCES graph_nodes(id),
    edge_type VARCHAR(30) NOT NULL,    -- has_column / foreign_key / metric_source / concept_map
    metadata JSONB DEFAULT '{}',
    UNIQUE(source_id, target_id, edge_type)
);

CREATE INDEX idx_graph_nodes_embedding ON graph_nodes USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_graph_nodes_type ON graph_nodes(node_type);
CREATE INDEX idx_graph_edges_source ON graph_edges(source_id);
CREATE INDEX idx_graph_edges_target ON graph_edges(target_id);
```

> **설계 결정**: 별도 Graph DB (Neo4j) 대신 PostgreSQL + pgvector 사용.
> NeuralDB는 이미 PostgreSQL 16 단일 DB 전략 (ADR-002).
> pgvector로 유사도 검색 + 일반 SQL로 Graph 탐색 가능.

### 3.3.1 pgvector + asyncpg + SQLAlchemy 호환성 가이드

pgvector-python은 SQLAlchemy를 공식 지원하지만, **asyncpg 드라이버와 함께 사용 시** 타입 등록 문제가 발생합니다.

| 드라이버 | pgvector ORM INSERT | pgvector ORM SELECT | 비고 |
|----------|--------------------|--------------------|------|
| `psycopg2` (sync) | ✅ 동작 | ✅ 동작 | 별도 설정 불필요 |
| `asyncpg` (async) | ❌ 타입 오류 | ❌ 타입 오류 | `register_vector` 필요 |

**NeuralDB 해결 전략 (asyncpg 환경):**

1. **ORM 모델 정의**: `pgvector.sqlalchemy.Vector(384)` 사용 (읽기/스키마 정의용)
2. **INSERT/UPDATE**: `text()` raw SQL + `CAST(:embedding AS vector)` 사용
3. **SELECT (유사도 검색)**: `text()` raw SQL + `CAST(:query_vec AS vector)` 사용
4. **임베딩 포맷**: Python list → pgvector 문자열 `"[0.1,0.2,...]"` 변환

```python
# ✅ GOOD — asyncpg에서 안전한 pgvector 사용법
from sqlalchemy import text

# INSERT
await session.execute(
    text("""
        INSERT INTO graph_nodes (id, name, embedding)
        VALUES (:id, :name, CAST(:embedding AS vector))
    """),
    {"id": node_id, "name": "users", "embedding": "[0.1,0.2,0.3]"},
)

# SELECT (cosine similarity)
await session.execute(
    text("""
        SELECT id, name, 1 - (embedding <=> CAST(:q AS vector)) AS similarity
        FROM graph_nodes
        ORDER BY embedding <=> CAST(:q AS vector)
        LIMIT 5
    """),
    {"q": "[0.1,0.2,0.3]"},
)

# ❌ BAD — asyncpg에서 ORM 직접 INSERT 시 타입 오류
node = GraphNode(embedding=embedding_list)  # asyncpg DataError
session.add(node)
```

> **근거**: asyncpg는 PostgreSQL custom type을 자동 감지하지 않으므로,
> `pgvector.asyncpg.register_vector(conn)` 호출이 필요하나,
> SQLAlchemy의 connection pool 이벤트에서 async 등록이 복잡.
> Raw SQL + CAST 방식이 가장 안정적이며, 쿼리 가독성도 명확.

### 3.4 Schema → Graph 자동 생성

```python
# backend/app/services/graph_rag.py

class SchemaGraphBuilder:
    """PostgreSQL 카탈로그에서 Knowledge Graph 자동 생성."""

    async def build_graph(self, instance_id: UUID) -> int:
        """대상 DB의 information_schema를 읽어 Graph 노드/엣지 생성.

        1. information_schema.tables → Table 노드
        2. information_schema.columns → Column 노드 + HAS_COLUMN 엣지
        3. pg_constraint → FOREIGN_KEY 엣지
        4. 각 노드에 sentence-transformers 임베딩 생성
        """
        ...

    async def add_business_metric(self, name: str, description: str,
                                   source_columns: list[str]) -> UUID:
        """비즈니스 메트릭 노드 + METRIC_SOURCE 엣지 수동 추가."""
        ...

    async def add_business_concept(self, name: str, description: str,
                                    related_metrics: list[str]) -> UUID:
        """비즈니스 개념 노드 + CONCEPT_MAP 엣지 수동 추가."""
        ...
```

---

## 4. GraphRAG Retrieval 프로세스

### 4.1 Query Embedding + Graph Node 검색

```python
class GraphRAGRetriever:
    """사용자 질의에서 관련 Schema Subgraph 추출."""

    async def retrieve(self, question: str, instance_id: UUID,
                       top_k: int = 10) -> SubgraphContext:
        """
        1. question → embedding (sentence-transformers)
        2. pgvector cosine similarity → top_k 관련 노드
        3. 관련 노드의 이웃 탐색 (1-hop) → Subgraph 구성
        4. Join 경로 자동 발견 (FOREIGN_KEY 엣지 추적)
        """
        ...
```

### 4.2 Subgraph → LLM Context 변환

```python
class SubgraphContext:
    tables: list[str]           # 관련 테이블 목록
    columns: dict[str, list]    # 테이블별 컬럼 목록
    join_paths: list[JoinPath]  # FK 기반 Join 경로
    metrics: list[str]          # 관련 비즈니스 메트릭
    concepts: list[str]         # 관련 비즈니스 개념

    def to_prompt_context(self) -> str:
        """LLM 프롬프트에 삽입할 스키마 컨텍스트 생성.

        전체 스키마가 아닌 관련 Subgraph만 포함 → 토큰 절약.
        """
```

### 4.3 기존 NL2SQL과의 비교

```
기존 (Phase 1):
  하드코딩 스키마 (10 테이블) → LLM → SQL

NL2GraphRAG (Phase 2):
  질의 → Embedding → Graph 검색 → 관련 5 테이블만 추출
  → Subgraph Context → Query Planner → SQL Generator → SQL
```

---

## 5. 5계층 안전 장치 (기존 유지)

GraphRAG 전환 후에도 동일하게 적용:

| Layer | 검증 | 내용 |
|-------|------|------|
| ① | Write 키워드 | INSERT/UPDATE/DELETE/DROP/ALTER... |
| ② | 위험 함수 | pg_read_file, dblink, lo_get... |
| ③ | 민감 테이블 | users, audit_logs, alert_channels... |
| ④ | Multi-statement | 세미콜론 차단 |
| ⑤ | SELECT/WITH 강제 | 첫 키워드 검증 |

실행 시 안전장치:
- `SET LOCAL default_transaction_read_only = on`
- `SET LOCAL statement_timeout = '5000'`
- 결과 1000행 제한

---

## 6. ~~Agent 기반 구조~~ → **Won't Do** (Phase 2에서 이미 해결)

> **결정 (2026-03-27)**: Phase 3 NL2SQL 4-Agent Pipeline 계획을 철회합니다.
>
> **근거**:
> 1. **Phase 2 단일 파이프라인이 이미 동일 기능 수행**: GraphRAGRetriever(=Schema Agent) + LLM(=SQL Agent) + _validate_sql_readonly(=Validator) — 1117 LOC, 1번 LLM 호출
> 2. **4-Agent = 4x LLM 호출 = 4x 지연/비용**: NeuralDB의 NL2SQL은 DBA의 간단한 질의용이지 복잡한 BI가 아님
> 3. **복잡도 대비 이익 없음**: LangGraph 상태 그래프 + CrewAI 오케스트레이션 도입은 유지보수 비용만 증가
> 4. **멀티 DB는 Adapter 레벨에서 해결**: SQL 방언은 DB Adapter가 처리 (Phase 4)
> 5. **피드백 Few-shot은 Agent 없이 가능**: nl2sql_histories → 프롬프트 예시 자동 추가 (Phase 2 확장)
>
> **현재 아키텍처 (유지)**:
> ```
> 질의 → GraphRAG Retriever → Subgraph → LLM (1회) → SQL → 5계층 안전 → 실행
> ```
>
> **대안**:
> - AC-18 (4-Agent): **Won't Do** — 단일 파이프라인으로 충분
> - AC-19 (멀티 DB SQL): **Phase 4 DB Adapter 이관** — NL2SQL이 아닌 Adapter 책임
> - AC-20 (피드백 Few-shot): **Phase 2 확장으로 격하** — Agent 불필요, 서비스 로직으로 구현

---

## 7. API 엔드포인트

### 7.1 현재 구현 (Phase 1)

| Method | Path | 상태 |
|--------|------|------|
| POST | `/api/v1/nl2sql/query` | ✅ 기본 NL2SQL |

### 7.2 Phase 2 추가

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/v1/nl2sql/query` | GraphRAG 기반 NL2SQL (기존 API 유지, 내부 교체) |
| POST | `/api/v1/nl2sql/explain` | EXPLAIN ANALYZE 자연어 해석 |
| POST | `/api/v1/nl2sql/optimize` | SQL 최적화 제안 |
| GET | `/api/v1/nl2sql/history` | 질의 이력 조회 |
| POST | `/api/v1/nl2sql/feedback` | 결과 정확도 피드백 (👍/👎) |
| POST | `/api/v1/graph/build` | Schema → Graph 자동 생성 |
| GET | `/api/v1/graph/nodes` | Graph 노드 조회 |
| POST | `/api/v1/graph/metric` | 비즈니스 메트릭 등록 |
| POST | `/api/v1/graph/concept` | 비즈니스 개념 등록 |

---

## 8. 구현 마일스톤

### Phase 1 (현재 — 기본 NL2SQL)

- [x] LLM + 하드코딩 스키마 → SQL 생성
- [x] 5계층 안전 장치
- [x] 읽기 전용 실행 + 결과 반환
- [x] 프론트엔드 채팅 위젯
- [x] LLMProviderManager 통합

### Phase 2 (다음 — GraphRAG 전환)

- [ ] `graph_nodes` / `graph_edges` 테이블 마이그레이션
- [ ] `SchemaGraphBuilder` — information_schema → Graph 자동 생성
- [ ] `GraphRAGRetriever` — 질의 → Subgraph 추출
- [ ] `QueryPlanner` — Graph 기반 실행 계획
- [ ] `SQLGenerator` — Subgraph + Plan → SQL (기존 LLM 호출 교체)
- [ ] `SQLValidator` — EXPLAIN ANALYZE 비용 체크
- [ ] 대상 DB 직접 쿼리 (adapter 통해)
- [ ] 비즈니스 메트릭/개념 등록 API

### ~~Phase 3 (Agent 기반)~~ — Won't Do (2026-03-27)

> 4-Agent Pipeline 철회. 근거: §6 참조.

- [x] ~~Planner + Schema + SQL + Validator Agent~~ → Won't Do (단일 파이프라인 유지)
- [ ] 멀티 DB SQL 방언 → **Phase 4 DB Adapter로 이관**
- [ ] 피드백 Few-shot → **Phase 2 확장** (아래 Phase 2+ 참조)

### Phase 2+ (피드백 Few-shot 학습)

- [ ] `nl2sql_histories`에서 `is_correct=true` 이력을 프롬프트 Few-shot 예시로 자동 추가
- [ ] 인스턴스별 최대 5개 Few-shot 예시 (가장 최근 정확한 질의)
- [ ] 피드백 API: POST `/api/v1/nl2sql/feedback` (👍/👎)

---

## 9. GraphRAG 효과 예측

| 지표 | Phase 1 (NL2SQL) | Phase 2 (GraphRAG) |
|------|------------------|-------------------|
| SQL 생성 정확도 | ~60% | **~80-90%** |
| 지원 스키마 규모 | ~20 테이블 | **수백~수천 테이블** |
| Join 경로 정확도 | LLM 추측 | **Graph 기반 100%** |
| 비즈니스 용어 이해 | ❌ | **✅ Concept 노드** |
| 토큰 사용량 | 전체 스키마 (많음) | **Subgraph만 (적음)** |

---

## 10. 인수 기준

### Phase 1 (현재, MVP)

- [x] AC-1: POST /api/v1/nl2sql/query에서 자연어 → SQL → 결과 반환
- [x] AC-2: Write 키워드 차단 (INSERT/DELETE/DROP)
- [x] AC-3: 위험 함수 차단 (pg_read_file, dblink)
- [x] AC-4: 민감 테이블 차단 (users, audit_logs)
- [x] AC-5: statement_timeout 5초 적용
- [x] AC-6: 결과 1000행 제한 + warning
- [x] AC-7: nl2sql_histories 이력 저장
- [x] AC-8: LLMProviderManager 사용
- [x] AC-9: 프론트엔드 instance_id 전달
- [x] AC-10: AI 모델명 + 실행시간 표시

### Phase 2 (GraphRAG)

- [ ] AC-11: Schema → Graph 자동 생성 (graph_nodes, graph_edges)
- [ ] AC-12: GraphRAG Retrieval로 관련 Subgraph 추출
- [ ] AC-13: Subgraph 기반 SQL 생성 (하드코딩 스키마 대체)
- [ ] AC-14: Join 경로가 Graph Edge에서 자동 발견
- [ ] AC-15: 비즈니스 메트릭/개념 등록 + SQL 반영
- [ ] AC-16: SQL 정확도 80%+ (테스트 세트 기준)
- [ ] AC-17: 대상 DB 직접 쿼리 지원

### ~~Phase 3 (Agent)~~ — Won't Do

- [x] ~~AC-18: 4-Agent 파이프라인~~ → **Won't Do** (단일 파이프라인 유지, §6 참조)
- [x] ~~AC-19: 멀티 DB SQL 방언~~ → **Phase 4 DB Adapter 이관** (NL2SQL 범위 아님)

### Phase 2+ (피드백)

- [x] ~~AC-20: 피드백 기반 Few-shot 학습~~ → **Deferred** (현재 불필요)

> **결정 (2026-03-27)**: Few-shot 학습 도입을 연기합니다.
>
> **근거**:
> 1. 현재 정확도 10/10 (100%) — 개선 여지 없음
> 2. 피드백 데이터 0건 (is_correct 피드백 UI 미구현)
> 3. 7b 로컬 모델의 context window에서 Few-shot 예시는 토큰 낭비
> 4. GraphRAG + System Prompt가 이미 충분한 스키마 컨텍스트 제공
> 5. DBA Agent intent router가 query 라우팅을 담당 — NL2SQL 자체의 판단력보다 DBA Agent의 라우팅이 핵심
>
> **도입 조건**: NL2SQL 정확도가 80% 이하로 떨어지거나, 피드백 데이터가 50건 이상 축적된 경우
>
> **대신 구현**: DBA Agent Chat UI에 👍/👎 피드백 버튼 추가 → is_correct 필드 업데이트
> (피드백 수집은 가치 있음 — Few-shot 적용 여부와 무관하게 LLM Observability 데이터)

---

## 11. 의존성

- **선행**: FS-AI-LLM-001 (LLM Provider), DM-001 (ERD), FS-AI-RAG-001 (pgvector)
- **사용**: FS-AI-TUNE-001 (Tuning Agent의 explain_query tool 재사용)
- **후행**: Phase 3 MCP Server에서 NL2GraphRAG를 외부 AI에 노출
