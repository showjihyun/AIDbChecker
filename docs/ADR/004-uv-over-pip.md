# ADR-004: uv 채택 (pip/pip-tools/pyenv 제거)

- **Status**: Accepted
- **Date**: 2026-03-21
- **Deciders**: Project Lead

## Context

Python 프로젝트에서 pip + virtualenv + pyenv + pip-tools를 조합하면:
- 도구 간 버전 충돌 (pip resolve ≠ pip-tools resolve)
- 재현 불가능한 환경 (requirements.txt 해시 불일치)
- CI/CD 속도 저하 (pip resolve O(n²))

## Decision

**uv (Astral, MIT/Apache 2.0)를 단일 Python 패키지 매니저로 사용한다.**

pip, pip-tools, pipx, pyenv, virtualenv를 모두 대체.

## Consequences

### Positive
- 10~100x 빠른 의존성 해석 (Rust 기반)
- `uv.lock` 결정론적 락파일 → 환경 간 100% 재현
- Python 버전 자체도 관리 (`uv python pin 3.12`)
- 단일 도구로 모든 Python 워크플로우 통합

### Negative
- 팀원 학습 곡선 (pip → uv 명령어 차이)
- 일부 레거시 CI 환경에서 uv 미설치 → `pip install uv`로 부트스트랩

### Rules
- `pip install` 명령 사용 금지
- `requirements.txt` 파일 생성 금지
- Dockerfile: `COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv`
