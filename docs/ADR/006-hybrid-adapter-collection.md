# ADR-006: 2-Tier Hybrid Adapter 수집 전략

- **Status**: Accepted
- **Date**: 2026-03-21
- **Deciders**: Project Lead
- **Review**: `docs/review/001-adapter-vs-agent-collection.md`

## Context

1초 해상도 메트릭 수집(FR-DASH-003)을 50+ DB 인스턴스에서 보장하려면, 중앙 집중식 Remote Adapter만으로는 네트워크 RTT 누적으로 한계가 있다. 반면 MVP 단계에서 대상 서버에 Agent 설치를 요구하면 도입 장벽이 높아진다.

## Decision

**2-Tier Hybrid Adapter 전략을 채택한다.**

- **Tier 2 (Remote Adapter)**: Phase 1~2 기본. NeuralDB에서 원격 조회. 설치 불필요. 30대 이하 / 같은 DC 내에서 1초 보장.
- **Tier 1 (Lightweight Collector)**: Phase 3 추가. 대상 DB 서버에 Python 프로세스(~30MB) 설치. 로컬 수집 후 Kafka/gRPC Push. 항상 1초 보장.
- Collector 미설치 시 Remote Adapter로 자동 폴백 (해상도 다운그레이드).
- 양쪽 모두 동일한 `BaseAdapter` 인터페이스 구현 (Plugin Interface 변경 없음).

## Consequences

### Positive
- MVP에서 Agent 설치 없이 즉시 시작 가능 (영업 장벽 제거)
- Phase 3에서 대규모 확장 경로 확보
- 고객이 Agent 설치를 거부해도 Remote 폴백으로 기능 유지
- Interface 변경 없이 구현체만 추가

### Negative
- Remote Adapter 사용 시 네트워크 지연에 따라 해상도 저하 가능
- Collector 도입 시 배포/업데이트 관리 시스템 필요 (Phase 4)

### Phase별 적용
| Phase | 전략 | 최대 DB 수 |
|-------|------|-----------|
| Phase 1 (MVP) | Remote only | ~20대 |
| Phase 2 | Remote + Worker 최적화 | ~30대 |
| Phase 3 | Hybrid (Collector + Remote 폴백) | ~200대 |
| Phase 4 | Collector 기본 + Remote 옵션 | 무제한 |
