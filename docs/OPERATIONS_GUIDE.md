# NeuralDB 운영 가이드

> Version: 1.3.0 | 2026-04-02

---

## 1. 시스템 구성

```
Frontend (React)  ──  nginx:3000
     │
     ▼ /api/v1/*
Backend (FastAPI)  ──  uvicorn:8000
     │
     ├── PostgreSQL 16  ──  5432 (메타+메트릭+벡터)
     ├── Valkey 8       ──  6379 (캐시+세션+Celery 브로커)
     ├── Celery Worker   (메트릭 수집, 리포트 생성)
     └── Celery Beat     (스케줄러)
```

---

## 2. Docker 배포

### 2.1 시작

```bash
cd infra/docker

# .env 파일 설정 (최초 1회)
cat > .env << 'EOF'
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_CHANNEL_ID=C0APZRZ4Y7M
SEED_ADMIN_PASSWORD=YourSecurePassword!
EOF

# 전체 시스템 기동
docker compose up -d

# 상태 확인
docker compose ps
curl http://localhost:3000/api/v1/system/health
```

### 2.2 접속 정보

| 서비스 | URL | 비고 |
|--------|-----|------|
| Dashboard | http://localhost:3000 | nginx 프록시 |
| API Docs | http://localhost:3000/docs | Swagger UI |
| PostgreSQL | localhost:5432 | neuraldb/neuraldb |
| Valkey | localhost:6379 | 패스워드: .env 참조 |

### 2.3 관리자 로그인

```
Email: admin@neuraldb.local
Password: (SEED_ADMIN_PASSWORD, 기본: NeuralDB@2026!)
```

### 2.4 업데이트

```bash
git pull origin main
cd infra/docker
docker compose build --no-cache backend frontend
docker compose up -d
```

---

## 3. AI 설정 (LLM Provider)

### 3.1 Settings → AI Configuration

| Provider | 설정 | 비고 |
|----------|------|------|
| **Anthropic (권장)** | API Key + claude-sonnet-4-6 | Native Tool Use, 최고 품질 |
| Ollama | http://host.docker.internal:11434 | 로컬, 무료 |
| OpenAI | API Key + gpt-4o | 대안 |

**설정 방법**: http://localhost:3000/settings/llm → Provider 선택 → API Key 입력 → Save

### 3.2 DBA Agent

- **위치**: 모든 페이지 우하단 채팅 아이콘 또는 사이드바 DBA Agent
- **기능**: 성능 분석, 진단, SQL 실행, NL2SQL, 시스템 상태
- **Claude 사용 시**: Native Tool Use로 7개 DB 진단 도구 자동 호출
- **Multi-Turn**: 이전 대화 컨텍스트 자동 유지 (Valkey, 1시간 TTL)

---

## 4. Slack 연동

### 4.1 설정

http://localhost:3000/settings/slack

1. Slack App 생성 (api.slack.com/apps)
2. Bot Token Scopes: `chat:write`
3. 앱을 워크스페이스에 설치
4. Bot Token (xoxb-...) + Channel ID 입력
5. 채널에 Bot 초대: `/invite @봇이름`
6. 테스트 발송 확인

### 4.2 자동 발송 항목

| 항목 | 스케줄 | 내용 |
|------|--------|------|
| Daily Report | 매일 09:00 | 핵심 지표 + 인시던트 + Slow Query + AI 분석 |
| Weekly Report | 매주 월요일 09:00 | 주간 트렌드 포함 |
| Monthly Report | 매월 1일 09:00 | 월간 종합 |
| 인시던트 알림 | 실시간 | Critical/Warning 감지 시 |
| Self-Healing 결과 | 실시간 | 자동 조치 실행 결과 |

---

## 5. DBA 리포트

### 5.1 수동 생성

http://localhost:3000/reports → "리포트 생성" 버튼

- 인스턴스 선택
- 유형: 일간/주간/월간
- 기간: From ~ To
- Slow Query Top N (기본 10)
- Slack 발송 여부

### 5.2 PDF 다운로드

리포트 목록에서 "PDF" 버튼 클릭 → 한국어 PDF 파일 다운로드

**PDF 내용**:
1. 핵심 지표 테이블 (CPU, Memory, TPS, Connection, 버퍼히트율)
2. 인시던트 요약 (severity별 건수 + 상세)
3. Slow Query Top N (SQL, 실행시간, 호출수)
4. ASH 분석 (Wait Event 분포, 세션 상태)
5. 스키마 변경 이력
6. AI 분석 요약 (한국어)

---

## 6. 모니터링 인스턴스 관리

### 6.1 인스턴스 추가

http://localhost:3000/instances → "Add Instance"

- DB Type: PostgreSQL
- Host/Port/Database
- Connection 테스트 → 등록
- 등록 시 Knowledge Graph 자동 빌드

### 6.2 메트릭 수집 주기

| 카테고리 | 주기 | 소스 |
|----------|------|------|
| Hot | 1초 | pg_stat_activity, pg_stat_database |
| Warm | 10초 | pg_stat_statements, pg_stat_user_tables |
| Cold | 1분 | pg_stat_replication, pg_settings |
| ASH | 1초 | pg_stat_activity (세션 스냅샷) |

---

## 7. 트러블슈팅

### 7.1 Backend 시작 안됨

```bash
docker compose logs backend --tail 30
# 주요 확인: Alembic migration, DB 연결, Knowledge Graph build
```

### 7.2 DBA Agent 응답 없음

1. Settings에서 LLM Provider 확인
2. Claude API Key 유효성 확인 (Settings → Test 버튼)
3. Ollama 실행 여부 확인 (`curl http://localhost:11434/api/tags`)

### 7.3 Slack 발송 실패

1. Settings → Slack → 테스트 발송
2. `channel_not_found`: 채널에 Bot 초대 필요
3. `invalid_auth`: Bot Token 재확인

### 7.4 메트릭 수집 안됨

1. Celery Worker 상태: `docker compose logs celery-worker`
2. 대상 DB 연결 확인: 인스턴스 → "Test Connection"
3. `pg_stat_statements` 확장 설치 확인

---

## 8. 기술 스택 요약

| 영역 | 기술 |
|------|------|
| Frontend | React 18 + Vite + TypeScript + TailwindCSS + ECharts |
| Backend | Python 3.12 + FastAPI + SQLAlchemy 2.0 + Celery |
| AI/LLM | Claude Sonnet 4.6 (Native Tool Use) + LangChain (fallback) |
| Database | PostgreSQL 16 (pgvector + pg_partman) |
| Cache | Valkey 8 (Redis API 호환) |
| Deploy | Docker Compose |
