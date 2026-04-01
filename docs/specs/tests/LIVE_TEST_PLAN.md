# Live Test Plan: DB 부하 → Incident 감지 → Metrics 시각화 검증

## 메타데이터
- **Spec ID**: TEST-LIVE-001
- **PRD 참조**: FR-DB-001, FR-DASH-001, FR-ALERT-003
- **상태**: Approved
- **대상 인스턴스**: neuraldb-system (시스템 DB, Docker 내부)

---

## 1. 목적

실제 DB에 인위적 부하를 발생시켜 NeuralDB의 **End-to-End 모니터링 파이프라인**이 정상 동작하는지 검증합니다.

```
DB 부하 발생 → 메트릭 수집 (1초) → 이상 탐지 → 인시던트 생성 → 대시보드 표시
```

---

## 2. 테스트 시나리오

### Scenario 1: CPU/커넥션 부하
- **방법**: `pg_stat_statements` 재귀 CTE로 CPU 집중 쿼리 반복 실행
- **기대**: CPU 메트릭 급등 → 베이스라인 이탈 → Incident 자동 생성
- **확인**: Dashboard Metrics Timeline에 CPU 스파이크 표시

### Scenario 2: Slow Query 생성
- **방법**: `pg_sleep()` + 대량 조인 쿼리로 느린 쿼리 발생
- **기대**: ASH에 active 세션 증가, wait event 표시
- **확인**: ASH Explorer에 히트맵 변화

### Scenario 3: 커넥션 포화
- **방법**: 다수 커넥션 동시 오픈 + idle in transaction 유지
- **기대**: active_connections 메트릭 급증 → Incident 생성
- **확인**: Incidents 페이지에 WARNING 표시

### Scenario 4: Lock 경합
- **방법**: 두 트랜잭션이 같은 row를 동시 UPDATE (advisory lock)
- **기대**: ASH에 Lock wait event 표시
- **확인**: ASH wait-breakdown에 Lock 카테고리 증가

---

## 3. 실행 순서

| Step | 작업 | 소요 시간 | 검증 포인트 |
|------|------|----------|------------|
| 0 | 시스템 정상 확인 (health check) | 10초 | status: healthy |
| 1 | 부하 시작 전 메트릭 스냅샷 저장 | 5초 | baseline CPU/conn |
| 2 | **CPU 부하 쿼리 실행** (30초간) | 30초 | - |
| 3 | **Slow Query 다수 실행** (동시 5개) | 15초 | - |
| 4 | **커넥션 다수 오픈** (20개 idle) | 10초 | - |
| 5 | 30초 대기 (수집 + 탐지 사이클) | 30초 | - |
| 6 | 메트릭 API 확인 (CPU 변화) | 5초 | metrics/latest |
| 7 | ASH API 확인 (active 세션) | 5초 | ash wait-breakdown |
| 8 | 인시던트 목록 확인 | 5초 | incidents 생성 여부 |
| 9 | 부하 정리 (커넥션 해제) | 5초 | - |

---

## 4. 인수 기준

- [ ] **AC-1**: CPU 부하 쿼리 실행 중 metrics/latest의 cpu_usage가 부하 전 대비 20%+ 증가
- [ ] **AC-2**: Slow Query 실행 중 ASH에 active 세션 수가 부하 전 대비 증가
- [ ] **AC-3**: 커넥션 다수 오픈 후 metrics의 active_connections 증가 확인
- [ ] **AC-4**: 이상 탐지 후 incidents 목록에 새 인시던트 생성 (또는 기존 임계값 기반)
- [ ] **AC-5**: Dashboard Metrics Timeline에서 부하 구간이 시각적으로 구분 가능
- [ ] **AC-6**: 부하 정리 후 메트릭이 정상 수준으로 복귀

---

## 5. 부하 쿼리

```sql
-- CPU 부하: 재귀 CTE (30초간)
WITH RECURSIVE cpu_load AS (
    SELECT 1 AS n, md5(random()::text) AS hash
    UNION ALL
    SELECT n + 1, md5(hash || random()::text)
    FROM cpu_load WHERE n < 500000
)
SELECT count(*), max(hash) FROM cpu_load;

-- Slow Query: pg_sleep
SELECT pg_sleep(5), count(*) FROM generate_series(1, 100000) AS g(x)
CROSS JOIN generate_series(1, 100) AS g2(y);

-- 커넥션 flood: asyncpg 다수 연결
-- Python 스크립트로 20개 커넥션 동시 오픈 + 10초 유지
```

---

## 6. 주의사항

- neuraldb-system은 **시스템 DB**이므로 과도한 부하 주의
- `statement_timeout` 설정으로 쿼리 폭주 방지 (최대 60초)
- 테스트 후 반드시 부하 정리 (커넥션 해제, pg_terminate_backend)
