# NeuralDB Demo v1 시연 가이드

> "장애 원인 5분 특정" 시나리오

## 사전 준비

### 1. Docker 기동
```bash
cd infra/docker && docker compose up -d
# 약 30초 후 자동 완료: 마이그레이션 + 시드 + 서버 기동
```

### 2. 접속
- URL: http://localhost:3000
- ID: admin@neuraldb.local
- PW: NeuralDB@2026!

### 3. 사내 DB 등록
- 좌측 메뉴 "Instances" → "Register Instance"
- Host: 사내 PostgreSQL IP
- Port: 5432
- Database: 대상 DB명
- Username/Password: 모니터링 전용 계정

---

## 데모 시나리오 (5분)

### Scene 1: 대시보드 개요 (1분)
1. 로그인 → Dashboard
2. **Summary 카드**: Total Instances, Active Monitoring, Anomalies
3. **인스턴스 카드**: 실시간 TPS, Hit%, Conn, Locks, Size
4. **System Health**: DB/Valkey/Celery 상태

**포인트**: "모니터링 대상 DB의 핵심 지표가 실시간으로 표시됩니다"

### Scene 2: KPI 12개 지표 (1분)
1. 인스턴스 카드 클릭
2. **KPI Overview Panel** 5개 카테고리 표시:
   - Throughput: TPS 27/s, QPS 1.2K/s
   - Resource: Hit Ratio 100%, Disk IOPS 0
   - Connection: Active 3, Usage 15%
   - Lock: Waits 0, Deadlocks 0
   - Storage: DB Size 9MB
3. **색상 코딩**: 🟢초록(정상) / 🟡노란(주의) / 🔴빨간(위험)
4. **Advisory 알림**: pg_stat_statements 미설치 시 Toast 알림 + 설치 SQL 안내

**포인트**: "장애 발생 시 어떤 카테고리에 문제가 있는지 한눈에 파악됩니다"

### Scene 3: Metrics Timeline (1분)
1. **실시간 차트**: Hit Ratio / Connections / TPS/s
2. **시간 범위**: 15m / 1h / 6h / 24h / 7d 전환
3. **delta/s 계산**: 누적 카운터가 아닌 초당 변화량

**포인트**: "시간 흐름에 따른 성능 변화를 추적할 수 있습니다"

### Scene 4: ASH Explorer (1분)
1. 좌측 메뉴 "ASH Explorer"
2. 인스턴스 선택
3. **Wait Event 히트맵**: 10초 버킷 단위 세션 분포
4. **세션 테이블**: pid, query, wait_event, duration

**포인트**: "어떤 쿼리가 어떤 Wait Event로 대기하고 있는지 1초 단위로 분석됩니다"

### Scene 5: NL2SQL (30초)
1. 우하단 💬 챗 버튼 클릭
2. 입력: "현재 가장 오래 실행 중인 쿼리는?"
3. 생성된 SQL + 결과 테이블 확인

**포인트**: "자연어로 DB 상태를 질의할 수 있습니다"

### Scene 6: AI 자동 감지 (30초)
1. **자동 베이스라인**: 2주 데이터로 정상 패턴 학습
2. **이상 탐지**: z-score 기반 → 인시던트 자동 생성
3. **Incidents 페이지**: severity 필터, ACK/Resolve
4. **Slack 알림**: 30초 내 메트릭 포함 알림 발송

**포인트**: "AI가 평소와 다른 패턴을 자동 감지하고 알려줍니다"

---

## 예상 질문 + 답변

| 질문 | 답변 |
|------|------|
| 대상 DB에 부하가 가지 않나? | 읽기 전용 커넥션 2개, statement_timeout 500ms, 수집 실패 시 silent skip |
| 1초 수집이 가능한가? | 같은 DC 내 RTT <2ms면 가능. 원격 환경은 10초로 폴백 |
| MySQL/MSSQL도 지원하나? | Phase 4 예정. 어댑터 인터페이스는 이미 설계됨 |
| 오프라인 환경에서도 되나? | Ollama로 로컬 LLM 전환 가능 (환경변수 1개) |
| 보안은? | JWT 인증, RBAC 5역할, Fernet 암호화, NL2SQL 5계층 방어, CSO 감사 3회 |

---

## 기술 사양

- Backend 테스트: 157 pass + 27 skip (AC 69%)
- Frontend 테스트: 41 pass
- Docker: 6 containers, `docker compose up` 원커맨드
- API: 20+ endpoints (Swagger: http://localhost:8001/docs)
- Spec 문서: 30개, AC 87개 추적
