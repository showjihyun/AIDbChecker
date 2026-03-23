# ADR-007: 대상 DB 인증 정보 암호화 방식

- **Status**: Accepted
- **Date**: 2026-03-21
- **Deciders**: Project Lead
- **관련 Spec**: DM-001 (db_instances.connection_config), FR-ADMIN-003

## Context

`db_instances.connection_config` JSONB 필드에 대상 DB의 비밀번호, SSL 인증서 경로 등 민감 정보가 저장된다. 평문 저장은 보안 위반이며, 암호화 방식을 결정해야 한다.

## Options

| 방식 | 장점 | 단점 |
|------|------|------|
| **A. 앱 레벨 AES-256-GCM** | DB 접근만으로 복호화 불가, 키 분리 가능 | 키 관리 필요 |
| B. PostgreSQL pgcrypto | DB 내장, 추가 의존 없음 | DB 접근 시 복호화 가능 |
| C. HashiCorp Vault | 엔터프라이즈급 시크릿 관리 | MVP에 과잉, 추가 인프라 |

## Decision

**A. 앱 레벨 AES-256-GCM 암호화를 사용한다.**

```python
# app/utils/crypto.py
from cryptography.fernet import Fernet  # or AES-256-GCM

ENCRYPTION_KEY = settings.APP_SECRET_KEY  # .env에서 로드, 64자 랜덤

def encrypt_config(config: dict) -> str:
    """connection_config를 암호화하여 DB에 저장"""

def decrypt_config(encrypted: str) -> dict:
    """DB에서 읽은 암호화 데이터를 복호화"""
```

## Rules

- `connection_config`의 `password`, `ssl_key` 필드만 암호화 (host, port는 평문)
- 암호화 키: `.env`의 `APP_SECRET_KEY` (최소 32바이트)
- 키 로테이션: Phase 2에서 구현 (현재는 단일 키)
- API 응답에서 `password` 필드는 항상 마스킹 (`"****"`)
- 감사 로그에 비밀번호 평문 기록 금지

## Consequences

### Positive
- DB 덤프/백업이 유출되어도 비밀번호 보호
- `cryptography` 패키지 (Apache 2.0 / BSD) 사용 가능

### Negative
- `APP_SECRET_KEY` 분실 시 모든 인증 정보 복호화 불가 → 키 백업 필수
