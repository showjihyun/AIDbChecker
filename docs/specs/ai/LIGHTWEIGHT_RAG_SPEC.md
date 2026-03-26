# Feature Spec: 경량 RAG (Lightweight RAG for MVP)

## 메타데이터
- **Spec ID**: FS-AI-RAG-001
- **PRD 참조**: FR-AI-002, FR-AI-014
- **우선순위**: P0 (MVP)
- **상태**: Approved
- **선행 Spec**: DM-001 (ERD — `rag_documents` 테이블)
- **사용 Spec**: FS-AI-010 (MTL RCA에 RAG 결과 제공)
- **구현 파일**:
  - Backend: `backend/app/services/rag.py`, `backend/app/api/v1/rag.py`
  - Test: `backend/tests/unit/test_ai_rag_001_spec.py`

---

## 1. 개요

MVP 단계에서 **인시던트 이력**을 pgvector에 임베딩하여, 새 인시던트 발생 시 유사 과거 사례를 검색하고 MTL RCA 프롬프트에 컨텍스트로 제공하는 경량 RAG 시스템.

> **풀 RAG Pipeline**(DB 문서/매뉴얼/Playbook 임베딩)은 **Phase 2**에서 구현.
> MVP에서는 **인시던트 이력 임베딩만** 활성화합니다.

---

## 2. 인터페이스 계약

### 2.1 API 엔드포인트

#### 유사 인시던트 검색
- **Method**: POST
- **Path**: `/api/v1/rag/search`
- **Auth**: JWT (DB Admin / Operator 이상)
- **Request Schema**:

```python
# Spec: FR-AI-002
class RAGSearchRequest(BaseModel):
    query: str  # 검색 텍스트 (인시던트 설명 또는 자연어)
    instance_id: UUID | None = None  # 특정 인스턴스 한정
    top_k: int = Field(default=3, ge=1, le=10)
    min_similarity: float = Field(default=0.7, ge=0.0, le=1.0)
```

- **Response Schema**:

```python
# Spec: FR-AI-002
class RAGSearchResponse(BaseModel):
    results: list[RAGSearchResult]
    search_time_ms: int
    embedding_model: str

class RAGSearchResult(BaseModel):
    incident_id: UUID
    similarity: float  # 0.0~1.0 (cosine similarity)
    summary: str  # 인시던트 요약
    root_cause: str | None  # 해결된 경우 원인
    resolution: str | None  # 해결 방법
    created_at: datetime
```

#### 임베딩 상태 조회
- **Method**: GET
- **Path**: `/api/v1/rag/status`
- **Response**:

```python
class RAGStatusResponse(BaseModel):
    total_documents: int
    total_incidents_embedded: int
    last_embedding_at: datetime | None
    embedding_model: str
    vector_dimensions: int
```

- **Error Codes**: 400, 401, 403, 500, 503 (임베딩 서비스 불가)

### 2.2 데이터 모델

#### `rag_documents` 테이블 (MVP 활용)

```sql
-- Spec: FR-AI-002
-- 기존 ERD의 rag_documents 테이블을 MVP에서 활성화
CREATE TABLE rag_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type     VARCHAR(20) NOT NULL DEFAULT 'incident',
    -- MVP: 'incident' only. Phase 2: 'document', 'playbook', 'manual'
    source_id       UUID NOT NULL,  -- incidents.id 참조
    content         TEXT NOT NULL,   -- 임베딩 대상 텍스트
    metadata        JSONB NOT NULL DEFAULT '{}',
    -- {"instance_id": "...", "anomaly_type": "...", "severity": "...",
    --  "resolution": "...", "was_correct": true}

    embedding       vector(384) NOT NULL,  -- sentence-transformers 출력 차원
    -- Phase 2에서 1536차원(OpenAI) 마이그레이션 가능

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- pgvector HNSW 인덱스 (cosine similarity)
CREATE INDEX idx_rag_documents_embedding
    ON rag_documents USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_rag_documents_source ON rag_documents(source_type, source_id);
CREATE INDEX idx_rag_documents_created ON rag_documents(created_at);
```

### 2.3 임베딩 모델

```python
# Spec: FR-AI-002
# MVP 임베딩 설정

EMBEDDING_CONFIG = {
    "model": "all-MiniLM-L6-v2",     # sentence-transformers
    "dimensions": 384,                 # 출력 차원
    "max_tokens": 256,                 # 입력 최대 토큰
    "batch_size": 32,                  # 배치 임베딩 크기
    "device": "cpu",                   # MVP: CPU. Phase 2: GPU 옵션
}

# Phase 2 옵션:
# "model": "text-embedding-3-small"  # OpenAI (1536 차원)
# "model": "BAAI/bge-m3"            # 다국어 로컬 (1024 차원)
```

---

## 3. 동작 규격

### 3.1 임베딩 생성 파이프라인

```
인시던트 생성/갱신 → Celery Task 트리거
    ↓
인시던트 컨텍스트 구성:
    content = f"""
    Type: {incident.anomaly_type}
    Instance: {instance.name}
    Metrics: CPU={cpu}%, Conn={conn}, TPS={tps}
    Top Query: {top_slow_query}
    Wait Events: {wait_summary}
    Description: {incident.description}
    Resolution: {incident.resolution or 'unresolved'}
    """
    ↓
sentence-transformers 임베딩 생성 (384차원)
    ↓
rag_documents 테이블에 UPSERT
```

#### 임베딩 트리거 조건

| 이벤트 | 동작 |
|--------|------|
| 인시던트 생성 | 즉시 임베딩 생성 (Celery task) |
| 인시던트 해결 (resolution 추가) | 임베딩 재생성 (해결 정보 포함) |
| 운영자 피드백 (feedback_correct) | metadata 업데이트 (재임베딩 불필요) |
| 인시던트 삭제 | rag_documents에서 해당 행 삭제 |

### 3.2 유사 검색 알고리즘

```python
# Spec: FR-AI-002
async def search_similar_incidents(
    query: str,
    instance_id: UUID | None,
    top_k: int = 3,
    min_similarity: float = 0.7
) -> list[RAGSearchResult]:
    """pgvector cosine similarity 검색"""

    # 1. 쿼리 텍스트 임베딩
    query_embedding = embedding_model.encode(query)

    # 2. pgvector 검색
    sql = """
        SELECT
            rd.source_id AS incident_id,
            1 - (rd.embedding <=> $1::vector) AS similarity,
            i.description AS summary,
            (rd.metadata->>'resolution') AS resolution,
            rd.created_at
        FROM rag_documents rd
        JOIN incidents i ON i.id = rd.source_id
        WHERE rd.source_type = 'incident'
          AND 1 - (rd.embedding <=> $1::vector) >= $2
          {instance_filter}
        ORDER BY rd.embedding <=> $1::vector
        LIMIT $3
    """

    # 3. instance_id 필터 (선택적)
    instance_filter = "AND (rd.metadata->>'instance_id')::uuid = $4" \
                      if instance_id else ""

    return await db.fetch_all(sql, query_embedding, min_similarity, top_k)
```

### 3.3 RAG → MTL 통합

```python
# Spec: FR-AI-002, FR-AI-010
def format_rag_for_mtl(rag_results: list[RAGSearchResult]) -> str:
    """RAG 검색 결과를 MTL 프롬프트에 삽입할 텍스트로 변환"""
    if not rag_results:
        return "No similar past incidents found."

    lines = []
    for i, r in enumerate(rag_results, 1):
        lines.append(f"--- Similar Incident #{i} (similarity: {r.similarity:.2f}) ---")
        lines.append(f"Summary: {r.summary}")
        if r.root_cause:
            lines.append(f"Root Cause: {r.root_cause}")
        if r.resolution:
            lines.append(f"Resolution: {r.resolution}")
        lines.append("")

    return "\n".join(lines)
```

### 3.4 캐싱 전략

```python
# Spec: FR-AI-002
# Valkey 캐싱으로 반복 검색 최적화

RAG_CACHE_CONFIG = {
    "enabled": True,
    "ttl_seconds": 300,            # 5분 캐시
    "key_prefix": "rag:search:",
    "max_cached_queries": 1000,
}

# 캐시 키: rag:search:{sha256(query + instance_id + top_k)}
# 인시던트 생성/갱신 시 관련 캐시 무효화
```

---

## 4. 성능 요구사항

| 메트릭 | 목표 | 측정 방법 |
|--------|------|----------|
| 임베딩 생성 | < 500ms / 건 | Celery task 실행 시간 |
| 유사 검색 | < 200ms (Top-3) | API 응답 시간 (pgvector HNSW) |
| 인덱스 메모리 | < 500MB (1만 건 기준) | PostgreSQL shared_buffers |
| 임베딩 정확도 | cosine similarity ≥ 0.85 (동일 유형 인시던트) | 테스트 데이터셋 |

---

## 5. 인수 기준 (Acceptance Criteria)

- [ ] **AC-1**: 인시던트 생성 시 5초 이내에 pgvector 임베딩이 자동 생성됨
- [ ] **AC-2**: POST `/api/v1/rag/search` 호출 시 200ms 이내에 Top-3 결과 반환
- [ ] **AC-3**: 동일 유형 인시던트 간 cosine similarity ≥ 0.85
- [ ] **AC-4**: 다른 유형 인시던트 간 cosine similarity < 0.5 (구분력)
- [ ] **AC-5**: RAG 검색 결과가 MTL 프롬프트의 `{rag_results}` 위치에 정확히 삽입됨
- [ ] **AC-6**: 인시던트 해결(resolution 추가) 시 임베딩이 재생성됨
- [ ] **AC-7**: pgvector HNSW 인덱스 사용이 EXPLAIN에서 확인됨
- [ ] **AC-8**: GET `/api/v1/rag/status`에서 임베딩 현황 조회 가능
- [ ] **AC-9**: Valkey 캐시 적중 시 검색 시간 < 10ms

---

## 6. 의존성

- **선행 Spec**: DM-001 (rag_documents 테이블 생성)
- **사용 Spec**: FS-AI-010 (MTL RCA가 RAG 결과를 프롬프트에 활용)
- **후행 Spec**: Phase 2 풀 RAG (문서/매뉴얼 임베딩 확장)
