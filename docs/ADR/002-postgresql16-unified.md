# ADR-002: PostgreSQL 16 단일 DB (TimescaleDB/QuestDB 제거)

- **Status**: Accepted
- **Date**: 2026-03-21
- **Deciders**: Project Lead

## Context

Architecture Spec v3.0에서는 TimescaleDB(시계열), pgvector(벡터), PostgreSQL(메타) 3개 DB를 사용했으나:
- TimescaleDB Community: TSL 라이선스 → SaaS 제공 불가
- QuestDB로 대체 검토했으나 운영 복잡도 증가 (별도 DB 인스턴스)
- PostgreSQL 16의 네이티브 파티셔닝이 충분히 성숙

## Decision

**PostgreSQL 16 하나로 메타 DB + 시계열 메트릭 + 벡터 검색을 모두 처리한다.**

- 시계열: `PARTITION BY RANGE` + pg_partman 자동 파티셔닝
- 다운샘플링: Materialized View + pg_cron (TimescaleDB Continuous Aggregate 대체)
- 벡터: pgvector 확장
- 전문 검색: PostgreSQL tsvector (Elasticsearch 불필요)

## Consequences

### Positive
- 운영 복잡도 극감 (DB 1개만 관리)
- 라이선스 리스크 제로 (PostgreSQL License = MIT 계열)
- 트랜잭션 일관성 보장 (메트릭+메타 조인 가능)
- 백업/복구 단순화

### Negative
- TimescaleDB의 `time_bucket()`, `compression` 기능 미사용 → 수동 구현 필요
- 대규모(50+ 인스턴스) 시 파티션 관리 복잡성 증가 가능
- Continuous Aggregate 없이 Materialized View 수동 갱신 필요

### Mitigation
- pg_partman으로 파티션 자동 관리
- pg_cron으로 5분마다 Materialized View 갱신
- 필요 시 읽기 전용 Replica로 수평 확장
