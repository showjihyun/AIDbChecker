# Feature Spec: 스키마 변경 감지

## 메타데이터
- **Spec ID**: FS-SCHEMA-001
- **PRD 참조**: MVP-SCHEMA-001, MVP-SCHEMA-002, AC-8
- **우선순위**: P3 (MVP)
- **상태**: Implemented (MVP)
- **선행 Spec**: DM-001 (schema_changes 테이블)
- **구현 파일**:
  - Backend: `backend/app/services/schema_detector.py`, `backend/app/api/v1/schema_changes.py`
  - Test: `backend/tests/unit/test_schema_001_spec.py`

---

## 1. 개요

대상 PostgreSQL DB의 DDL 변경(CREATE/ALTER/DROP)을 주기적으로 폴링하여 `schema_changes` 테이블에 기록. 대시보드에서 타임라인으로 조회.

> Event Trigger 방식은 대상 DB에 트리거 설치가 필요하므로 MVP에서는 **폴링 방식** 사용.
> `pg_stat_user_tables` + `information_schema` 스냅샷 비교로 변경 감지.

---

## 2. 감지 방식 (Polling)

### 2.1 Celery Beat 스케줄

| 태스크 | 주기 | 설명 |
|--------|------|------|
| `detect_schema_changes` | 1분 | 모든 활성 인스턴스의 스키마 스냅샷 비교 |

### 2.2 스냅샷 비교 대상

```sql
-- 현재 테이블/컬럼 목록
SELECT table_schema, table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY table_schema, table_name, ordinal_position;

-- 현재 인덱스 목록
SELECT schemaname, tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname NOT IN ('pg_catalog', 'information_schema');
```

### 2.3 변경 유형 판별

| 이전 스냅샷 대비 | change_type | object_type |
|-----------------|-------------|-------------|
| 새 테이블 출현 | CREATE | TABLE |
| 테이블 소멸 | DROP | TABLE |
| 새 컬럼 출현 | ALTER | COLUMN |
| 컬럼 소멸 | ALTER | COLUMN |
| 컬럼 타입 변경 | ALTER | COLUMN |
| 새 인덱스 출현 | CREATE | INDEX |
| 인덱스 소멸 | DROP | INDEX |

---

## 3. API 엔드포인트

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/instances/{id}/schema-changes` | DDL 변경 이력 (시간순) |

### Response

```json
{
  "items": [
    {
      "id": "uuid",
      "instance_id": "uuid",
      "change_type": "ALTER",
      "object_type": "COLUMN",
      "object_name": "users.email",
      "before_state": { "data_type": "varchar(100)" },
      "after_state": { "data_type": "varchar(255)" },
      "detected_at": "2026-03-25T12:00:00Z"
    }
  ],
  "total": 3
}
```

---

## 4. 인수 기준

- [ ] AC-1: 새 테이블 CREATE 감지 시 schema_changes 레코드 생성
- [ ] AC-2: 컬럼 ALTER (타입/nullable 변경) 감지
- [ ] AC-3: 인덱스 CREATE/DROP 감지
- [ ] AC-4: GET /api/v1/instances/{id}/schema-changes에서 이력 조회
- [ ] AC-5: 스냅샷은 Valkey에 캐싱 (인스턴스별 마지막 스냅샷)
- [ ] AC-6: DDL 변경 감지 시 Knowledge Graph(pgvector) 자동 갱신 트리거 (`_refresh_graph()`)
