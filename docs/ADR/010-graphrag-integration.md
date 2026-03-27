# ADR-010: GraphRAG 통합 (Phase 2 RAG 전략 전환)

- **Status**: Accepted
- **Date**: 2026-03-27
- **Deciders**: Project Lead
- **관련 Spec**: FS-AI-RAG-001 (Lightweight RAG), FS-AI-NL2SQL-001 (NL2SQL)

## Context

MVP에서 경량 RAG(pgvector cosine similarity)를 구현했으나, Phase 2에서 NL2SQL 정확도 향상을 위해 스키마 이해 능력이 필요했다. 단순 벡터 검색으로는 테이블 간 관계, 컬럼 의미, JOIN 경로를 충분히 전달할 수 없었다.

### 후보 방식

| 방식 | 장점 | 단점 |
|------|------|------|
| **기존 RAG (벡터만)** | 단순, 구현 완료 | 스키마 관계 표현 불가 |
| **GraphRAG (Knowledge Graph + 벡터)** | 스키마 관계 모델링, 정확한 JOIN 경로 | 그래프 구축/유지 비용 |
| **Fine-tuning** | 최고 정확도 가능 | 학습 데이터 필요, 모델별 재학습 |

## Decision

**Phase 2에서 GraphRAG를 NL2SQL 파이프라인에 통합한다.**

### 구현 전략

```
MVP (유지):   pgvector 경량 RAG → 인시던트 유사 검색
Phase 2 (추가): Knowledge Graph → NL2SQL 스키마 이해

NL2SQL 파이프라인:
  자연어 질의
    → GraphRAG: 관련 테이블/컬럼/관계 검색 (Knowledge Graph)
    → LLM: 스키마 컨텍스트 + 질의 → SQL 생성
    → 안전 검증 → 읽기 전용 실행
```

### 기술 선택

| 항목 | 선택 |
|------|------|
| 그래프 저장 | PostgreSQL 테이블 (`graph_nodes`, `graph_edges`) — 별도 그래프 DB 없음 |
| 벡터 저장 | pgvector (기존 `rag_documents`) |
| 검색 | 그래프 순회(재귀 CTE) + 벡터 유사도 하이브리드 |
| 임베딩 | sentence-transformers (MVP와 동일) |

## Consequences

### Positive
- NL2SQL 정확도 향상 (스키마 관계 인식)
- PostgreSQL 단일 DB 유지 (별도 Neo4j/Neptune 불필요 → ADR-002 준수)
- 기존 pgvector 인프라 재활용
- 인시던트 RAG와 NL2SQL GraphRAG가 동일 임베딩 모델 공유

### Negative
- 그래프 구축 초기 비용 (스키마 파싱 → 노드/엣지 생성)
- 스키마 변경 시 그래프 갱신 필요 (FS-SCHEMA-001과 연동)
- 복잡한 JOIN(3+ 테이블) 시 검색 정확도 검증 필요

### Mitigation
- 그래프 자동 갱신: 스키마 변경 감지(FS-SCHEMA-001) 시 Celery 태스크로 그래프 재구축
- Fallback: GraphRAG 실패 시 하드코딩 스키마 컨텍스트로 폴백 (NL2SQL_SPEC v2.0)
