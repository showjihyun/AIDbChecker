# ADR-011: Kafka 제거 — Celery + Valkey + gRPC로 통합

- **Status**: Accepted
- **Date**: 2026-03-27
- **Deciders**: Project Lead
- **관련 Spec**: KAFKA_SPEC (→ Deprecated), A2A_PROTOCOL, TECH_STACK

## Context

Architecture Spec v3.0에서 Kafka를 "메트릭 버퍼 + A2A 이벤트 스트리밍 + 알림 디스패치"로 설계했으나, Phase 1~3 구현 과정에서 **단 한 줄의 Kafka 코드도 작성되지 않았다**.

### 현재 상태 (검증 결과)
- `backend/app/` 소스코드: Kafka import/사용 **0건**
- `pyproject.toml`: aiokafka 의존성 **미설치**
- `docker-compose.yml`: Kafka 서비스 **미포함**
- 모든 비동기 태스크: **Celery + Valkey** 브로커로 처리 중
- 실시간 메트릭: **python-socketio** WebSocket으로 처리 중

### Kafka가 담당하려던 역할의 실제 대체

| 설계상 역할 | 실제 대체 | 동작 여부 |
|-----------|----------|----------|
| 메트릭 수집 버퍼 | Celery Beat → 직접 DB INSERT | ✅ 1초 수집 정상 |
| 인시던트 이벤트 | Celery Task + WebSocket | ✅ 실시간 알림 정상 |
| 알림 디스패치 | Celery Task (alert.py) | ✅ Slack/Webhook 정상 |
| 감사 로그 | 직접 audit_logs INSERT | ✅ 미들웨어로 자동 |
| A2A 에이전트 통신 | 함수 호출 → Phase 3: gRPC | ✅ Copilot/Playbook 정상 |

## Decision

**Kafka를 기술 스택에서 제거한다. Celery + Valkey + gRPC로 모든 비동기/이벤트를 처리한다.**

### 삭제 범위
- TECH_STACK.md: Kafka 항목 제거, aiokafka 제거, kafka-exporter 제거
- KAFKA_SPEC.md: 상태를 Deprecated로 변경
- docker-compose.yml: Kafka 서비스 참조 불필요 (이미 없음)
- AGENTS.md: "Kafka" → "Celery + gRPC" 대체 표현

### 유지 범위
- A2A_PROTOCOL.md: Kafka 참조를 gRPC/Celery로 대체 (비동기 부분)
- ADR-006 (Hybrid Adapter): "Kafka/gRPC" → "gRPC" (Collector Push)

## Consequences

### Positive
- **운영 복잡도 감소**: Kafka 브로커(KRaft) + 토픽 관리 + kafka-exporter 불필요
- **인프라 비용 절감**: Kafka는 최소 1GB+ 메모리 필요 → 제거
- **Docker Compose 경량화**: 서비스 1개 감소
- **기술 부채 제거**: 설계에만 존재하고 구현에 없는 "유령 의존성" 정리

### Negative
- 50+ 인스턴스 규모에서 이벤트 순서 보장이 Celery 대비 약함
  → **Mitigation**: Phase 4에서 필요 시 NATS/Redis Streams로 경량 대체

### When to Reconsider
- 인스턴스 100대+ 동시 수집 시 Celery Worker 병목 발생
- A2A 외부 파트너 에이전트 연동 시 이벤트 버스 필요
- 이벤트 소싱 패턴 도입 시
