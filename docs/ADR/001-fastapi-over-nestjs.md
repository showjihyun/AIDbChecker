# ADR-001: Python/FastAPI 단일 백엔드 (NestJS 제거)

- **Status**: Accepted
- **Date**: 2026-03-21
- **Deciders**: Project Lead

## Context

Architecture Spec v3.0에서는 NestJS(TypeScript) API Layer + Python Core Engine 2층 구조였으나, 다음 문제가 발생:
- API ↔ Engine 간 IPC 오버헤드 (HTTP/gRPC 브릿지)
- TypeORM(NestJS) + SQLAlchemy(Python) 이중 ORM 유지 부담
- TypeScript + Python 동시 CI/CD 파이프라인 복잡성
- LangChain/CrewAI 등 AI 프레임워크가 Python에 집중되어 있어 NestJS에서 호출 시 래퍼 필요

## Decision

**Python/FastAPI로 API + Core Engine을 단일 레이어로 통합한다.**

- REST API: FastAPI
- GraphQL: Strawberry (Python Code-First)
- WebSocket: python-socketio
- ORM: SQLAlchemy 2.0 async
- Task Queue: Celery

## Consequences

### Positive
- 단일 언어/런타임으로 배포·디버깅·채용 단순화
- AI 프레임워크와 네이티브 통합 (import 한 줄)
- IPC 제거, 메모리 공유로 성능 향상
- ORM 하나로 마이그레이션 통합

### Negative
- NestJS의 DI/모듈 시스템 대비 FastAPI는 수동 의존성 주입 (Depends로 보완)
- TypeScript 타입 안전성 손실 → Pydantic v2 + mypy strict로 보완

### Risks
- Architecture Spec v3.0에 NestJS 잔존 → AGENTS.md에 "무시할 것" 명시
