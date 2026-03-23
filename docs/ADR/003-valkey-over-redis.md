# ADR-003: Valkey 채택 (Redis 7.4+ 제거)

- **Status**: Accepted
- **Date**: 2026-03-21
- **Deciders**: Project Lead

## Context

Redis 7.4부터 RSALv2 + SSPL 듀얼 라이선스로 변경. 본 프로젝트가 독립 솔루션/SaaS로 발전 시 라이선스 위반 가능.

## Decision

**Valkey (Linux Foundation, BSD 3-Clause)를 사용한다.**

- Valkey = Redis 7.2 fork, API 100% 호환
- Docker 이미지: `valkey/valkey:8-alpine`
- Python 클라이언트: `redis` 패키지 그대로 사용 (프로토콜 동일)

## Consequences

### Positive
- BSD 3-Clause → SaaS/솔루션 제약 없음
- Linux Foundation 거버넌스 → 장기 안정성
- 기존 Redis 코드/도구 100% 재사용

### Negative
- RedisJSON, RediSearch, RedisGraph 모듈 미지원 → 사용 금지
- 커뮤니티 규모가 Redis 대비 작음 (성장 중)

### Naming Convention
- 환경변수: `VALKEY_URL` (의미 명확)
- 연결 문자열: `redis://valkey:6379/0` (프로토콜은 redis://)
- 코드 주석: Valkey로 명시
