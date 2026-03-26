# Integration Test Spec: 통합 테스트 환경 및 DB 연결

> **Spec ID**: TEST-INT-001
> **PRD 참조**: TEST-001 Layer 3 (Integration)
> **상태**: Approved
> **Phase**: MVP

---

## 1. 테스트 DB 연결 설정

### 1.1 Docker 환경 (기본)

통합 테스트는 Docker Compose로 기동된 PostgreSQL을 사용합니다.

```
Host: localhost
Port: 5432
Database: neuraldb
User: neuraldb
Password: neuraldb
URL: postgresql+asyncpg://neuraldb:neuraldb@localhost:5432/neuraldb
```

### 1.2 환경변수 오버라이드

```bash
# 기본값 (Docker Compose 환경)
TEST_DATABASE_URL=postgresql+asyncpg://neuraldb:neuraldb@localhost:5432/neuraldb
TEST_VALKEY_URL=redis://localhost:6379/0

# 외부 DB 사용 시
TEST_DATABASE_URL=postgresql+asyncpg://user:pass@host:port/dbname
```

### 1.3 사전 조건

- `docker compose up -d postgres valkey` 실행 상태
- `alembic upgrade head` 마이그레이션 완료
- pgvector 확장 설치 (`CREATE EXTENSION IF NOT EXISTS vector`)

---

## 2. 통합 테스트 실행

```bash
# 단위 테스트만 (기본, Docker 불필요)
uv run pytest tests/unit/ -q

# 통합 테스트만 (Docker 필요)
uv run pytest tests/integration/ -q -m integration

# 전체 (단위 + 통합)
uv run pytest tests/ -q
```

### 2.1 마커

```python
@pytest.mark.integration
async def test_live_db_query():
    """Docker PostgreSQL에 실제 쿼리 실행"""
    ...
```

통합 테스트는 `@pytest.mark.integration` 마커를 사용합니다.
Docker가 없는 환경에서는 `-m "not integration"` 으로 제외 가능합니다.

---

## 3. 통합 테스트 대상

### 3.1 DB 연결 + 마이그레이션

| AC | 테스트 | 설명 |
|----|--------|------|
| DM-MIG-001 AC-1 | `test_alembic_upgrade_head` | 전체 스키마 생성 확인 |
| DM-MIG-001 AC-2 | `test_alembic_downgrade_base` | 완전 롤백 확인 |
| DM-MIG-001 AC-3 | `test_tables_exist` | 13개 MVP 테이블 존재 확인 |

### 3.2 Adapter + 메트릭 수집

| AC | 테스트 | 설명 |
|----|--------|------|
| FS-AI-RAG-001 AC-1 | `test_embedding_insert` | pgvector 임베딩 저장 |
| FS-AI-RAG-001 AC-7 | `test_hnsw_index_explain` | HNSW 인덱스 사용 확인 |

### 3.3 KPI 라이브 쿼리

| AC | 테스트 | 설명 |
|----|--------|------|
| FS-KPI-001 AC-1 | `test_kpi_live_query` | 실제 DB에서 12 KPI 조회 |

---

## 4. 인수 기준

- [ ] AC-1: `tests/integration/` 디렉토리 존재 + conftest.py에 실제 DB 세션 fixture
- [ ] AC-2: `@pytest.mark.integration` 마커로 통합 테스트 분리 가능
- [ ] AC-3: Docker PostgreSQL 연결 + 13개 테이블 존재 확인 테스트 통과
- [ ] AC-4: `TEST_DATABASE_URL` 환경변수로 외부 DB 연결 가능
