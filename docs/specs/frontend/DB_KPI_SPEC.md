# Feature Spec: DB 핵심 성능 지표 대시보드

## 메타데이터
- **Spec ID**: FS-KPI-001
- **PRD 참조**: FR-DASH-001, MVP-DASH-001~002
- **우선순위**: P0 (MVP)
- **상태**: Approved
- **선행 Spec**: DM-001 (metric_samples), AG-001 (PostgreSQL Adapter)
- **참조**: `docs/etc/DB 핵심 성능지표.txt`
- **구현 파일**:
  - Backend: `backend/app/api/v1/kpi.py`, `backend/app/services/kpi_calculator.py`
  - Frontend: `frontend/src/components/dashboard/KPIOverviewPanel.tsx`
  - Test: `backend/tests/unit/test_kpi_001_spec.py`

---

## 1. 개요

모니터링 대상 DB 인스턴스별로 **5개 카테고리 12개 핵심 성능 지표(KPI)**를 실시간 대시보드에 표시한다. 모든 지표는 pg_stat_* 뷰에서 수집되며, 누적 카운터는 **delta/초** 기반으로 변환하여 표시한다.

---

## 2. 핵심 성능 지표 정의

### 2.1 처리량 및 응답 속도 (Throughput & Latency)

| KPI ID | 지표명 | 수집 소스 | 계산 방식 | 단위 | 임계값 |
|--------|--------|----------|----------|------|--------|
| KPI-01 | **TPS** | `pg_stat_database.xact_commit` | delta/초 | tx/s | warn:5000, crit:10000 |
| KPI-02 | **QPS** | `pg_stat_database.tup_returned` | delta/초 | q/s | warn:50000, crit:100000 |
| KPI-03 | **Avg Response Time** | `pg_stat_statements.mean_exec_time` | 직접 | ms | warn:100, crit:500 |
| KPI-04 | **Slow Queries** | `pg_stat_activity` WHERE duration > 1s | count | 건 | warn:5, crit:20 |

### 2.2 리소스 및 시스템 (System & Resource)

| KPI ID | 지표명 | 수집 소스 | 계산 방식 | 단위 | 임계값 |
|--------|--------|----------|----------|------|--------|
| KPI-05 | **Buffer Hit Ratio** | `pg_stat_database.blks_hit/blks_read` | delta 비율 | % | warn:<95, crit:<90 |
| KPI-06 | **Disk IOPS** | `pg_stat_database.blks_read` | delta/초 | ops/s | warn:1000, crit:5000 |

### 2.3 연결 및 세션 (Connection & Session)

| KPI ID | 지표명 | 수집 소스 | 계산 방식 | 단위 | 임계값 |
|--------|--------|----------|----------|------|--------|
| KPI-07 | **Active Sessions** | `pg_stat_activity` WHERE state='active' | count | 건 | warn:50, crit:100 |
| KPI-08 | **Connection Usage** | `numbackends / max_connections * 100` | 비율 | % | warn:80, crit:95 |

### 2.4 잠금 및 경합 (Lock & Contention)

| KPI ID | 지표명 | 수집 소스 | 계산 방식 | 단위 | 임계값 |
|--------|--------|----------|----------|------|--------|
| KPI-09 | **Lock Waits** | `pg_stat_activity` WHERE wait_event_type='Lock' | count | 건 | warn:5, crit:20 |
| KPI-10 | **Deadlocks** | `pg_stat_database.deadlocks` | delta/초 | 건/s | warn:0.1, crit:1 |

### 2.5 가용성 및 저장 공간 (Availability & Storage)

| KPI ID | 지표명 | 수집 소스 | 계산 방식 | 단위 | 임계값 |
|--------|--------|----------|----------|------|--------|
| KPI-11 | **DB Size** | `pg_database_size()` | 직접 | GB | warn:80%용량, crit:95%용량 |
| KPI-12 | **Replication Lag** | `pg_stat_replication.replay_lag` | 직접 | sec | warn:10, crit:60 |

---

## 3. 수집 계층 매핑

| 수집 계층 | 주기 | 포함 KPI |
|----------|------|---------|
| **Hot** | 1초 | KPI-01, KPI-02, KPI-05, KPI-06, KPI-07, KPI-08, KPI-09, KPI-10 |
| **Warm** | 10초 | KPI-03 (pg_stat_statements), KPI-04 (slow query count) |
| **Cold** | 1분 | KPI-11 (DB size), KPI-12 (replication lag) |

---

## 4. 프론트엔드 컴포넌트

### 4.1 인스턴스별 KPI 카드 (InstanceCard 확장)

```
┌──────────────────────────────────────┐
│ neuraldb-system    ● Healthy         │
│ postgres:5432                        │
├──────────────────────────────────────┤
│ TPS    Hit%    Conn    Locks   Size  │
│ 27/s   99.8%   31/200  0      8.5GB │
└──────────────────────────────────────┘
```

### 4.2 KPI Overview Panel (신규, 대시보드 상단)

인스턴스 선택 시 5개 카테고리의 12개 KPI를 한눈에 보여주는 패널.

```
┌─ Throughput & Latency ────────────────────────────┐
│ TPS: 27/s  QPS: 1.2K/s  Avg RT: 2.3ms  Slow: 0  │
├─ Resource ────────────────────────────────────────┤
│ Hit Ratio: 99.8%  Disk IOPS: 0 ops/s             │
├─ Connection ──────────────────────────────────────┤
│ Active: 3  Conn Usage: 31/200 (15%)               │
├─ Lock ────────────────────────────────────────────┤
│ Lock Waits: 0  Deadlocks: 0                       │
├─ Storage ─────────────────────────────────────────┤
│ DB Size: 8.5 GB  Repl Lag: N/A                    │
└───────────────────────────────────────────────────┘
```

### 4.3 색상 코딩 (3단계 신호등)

| 상태 | 조건 | 색상 | Tailwind | 의미 |
|------|------|------|----------|------|
| **Healthy** | 값이 정상 범위 | 🟢 초록 | `text-tertiary` (#4edea3) | 쾌적 |
| **Warning** | warn 임계값 도달 | 🟡 노란/주황 | `text-warning` (#f59e0b) | 주의 필요 |
| **Critical** | crit 임계값 초과 | 🔴 빨간 | `text-error` (#ef4444) | 즉시 조치 |
| **Unknown** | 데이터 없음 | ⚪ 회색 | `text-outline` (#88929b) | 수집 불가 |

### 4.4 임계값 기본값 + 인스턴스별 설정

각 KPI의 임계값은 DB 인스턴스의 성능 스펙에 따라 **Settings에서 조정 가능**합니다.

| KPI | 기본 Warning | 기본 Critical | 방향 | 비고 |
|-----|-------------|--------------|------|------|
| TPS | 5,000 tx/s | 10,000 tx/s | ↑ 높을수록 위험 | OLTP 기준 |
| QPS | 50,000 q/s | 100,000 q/s | ↑ | |
| Avg RT | 100 ms | 500 ms | ↑ | |
| Slow Queries | 5건 | 20건 | ↑ | |
| Hit Ratio | 95% | 90% | ↓ **낮을수록 위험** | |
| Disk IOPS | 1,000 ops/s | 5,000 ops/s | ↑ | |
| Active Sessions | 50 | 100 | ↑ | max_connections 대비 |
| Conn Usage | 80% | 95% | ↑ | |
| Lock Waits | 5건 | 20건 | ↑ | |
| Deadlocks | 0.1/s | 1.0/s | ↑ | |
| DB Size | 80% 용량 | 95% 용량 | ↑ | |
| Repl Lag | 10 sec | 60 sec | ↑ | |

### 4.5 Metrics Timeline X축 시간 포맷

시간 범위 프리셋에 따라 X축 레이블 포맷과 데이터 다운샘플링이 적응적으로 변경됩니다.

| 프리셋 | X축 포맷 | 최대 포인트 | 레이블 간격 | 회전 | 예시 |
|--------|----------|-----------|-----------|------|------|
| **15m** | `HH:mm:ss` | 150 | 매 15번째 | 0° | 14:30:15 |
| **1h** | `HH:mm` | 120 | 매 12번째 | 0° | 14:30 |
| **6h** | `HH:mm` | 90 | 매 9번째 | 0° | 14:30 |
| **24h** | `HH:mm` | 72 | 매 6번째 | 35° | 14:30 |
| **7d** | `MM/dd HH` | 56 | 매 4번째 | 35° | 03/25 14 |

#### X축 레이블 규칙

- **짧은 범위 (15m~6h)**: 수평 레이블, 약 10개 레이블 표시
- **긴 범위 (24h~7d)**: 35° 회전, 차트 하단 패딩 48px로 증가
- **7d**: 시간 표시 `HH`만 (분 생략) — 날짜 구분이 더 중요
- **포인트 수**: 범위가 길수록 적게 (56~150개) — 패턴 가독성 우선

#### 다운샘플링 로직

```
원본 데이터 (1초 간격, N 포인트)
    ↓
프리셋별 maxPoints에 맞춰 등간격 추출
    ↓
차트에 표시 (56~150 포인트)
```

- **게이지 메트릭** (numbackends): 추출된 포인트 값 그대로
- **카운터 메트릭** (xact_commit): 인접 포인트 delta/interval

### 4.6 카운터 리셋 처리

`xact_commit`, `blks_hit`, `blks_read`, `deadlocks` 등 누적 카운터는 PostgreSQL 재시작 또는 `pg_stat_reset()` 호출 시 0으로 리셋됩니다.

```
delta = current - previous
if delta < 0:
    # 카운터 리셋 — 이 구간의 delta/s는 계산 불가
    return null (차트에 빈 구간으로 표시)
```

- 차트에서 음수 값을 **절대 표시하지 않음**
- 리셋 구간은 차트에서 gap(빈 구간)으로 나타남
- KPI 패널에서 delta 계산 불가 시 `unknown` 상태 표시

---

## 5. 백엔드 API 확장

### 5.1 Hot 메트릭 수집 확장

현재 `pg_stat_database`만 수집하는 hot 어댑터에 추가 쿼리:

```sql
-- KPI-04: Slow queries (duration > 1s)
SELECT count(*) AS slow_query_count
FROM pg_stat_activity
WHERE state = 'active'
  AND clock_timestamp() - query_start > INTERVAL '1 second'
  AND backend_type = 'client backend'
  AND pid <> pg_backend_pid();

-- KPI-07: Active sessions
SELECT count(*) AS active_sessions
FROM pg_stat_activity
WHERE state = 'active'
  AND backend_type = 'client backend';

-- KPI-08: Connection usage ratio
SELECT numbackends,
       (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') AS max_connections
FROM pg_stat_database
WHERE datname = current_database();

-- KPI-09: Lock waits
SELECT count(*) AS lock_waits
FROM pg_stat_activity
WHERE wait_event_type = 'Lock';

-- KPI-10: Deadlocks (cumulative counter)
SELECT deadlocks FROM pg_stat_database WHERE datname = current_database();
```

### 5.2 KPI 계산 서비스

```python
# backend/app/services/kpi_calculator.py
# Spec: FS-KPI-001

class KPICalculator:
    """Compute derived KPI values from raw metric samples."""

    @staticmethod
    def compute_delta_rate(current: int, previous: int, interval_sec: float) -> float:
        """Compute per-second rate from cumulative counter delta."""
        if interval_sec <= 0:
            return 0.0
        return max(0.0, (current - previous) / interval_sec)

    @staticmethod
    def compute_hit_ratio(delta_hit: int, delta_read: int) -> float:
        """Buffer cache hit ratio from delta values."""
        total = delta_hit + delta_read
        if total <= 0:
            return 100.0  # no I/O = 100% cache
        return round((delta_hit / total) * 100, 2)
```

### 5.3 API 엔드포인트

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/instances/{id}/kpi` | 인스턴스별 12개 KPI 현재값 + 상태 |

**Response:**

```json
{
  "instance_id": "uuid",
  "timestamp": "2026-03-25T12:00:00Z",
  "throughput": {
    "tps": { "value": 27, "unit": "tx/s", "status": "normal" },
    "qps": { "value": 1200, "unit": "q/s", "status": "normal" },
    "avg_response_time_ms": { "value": 2.3, "unit": "ms", "status": "normal" },
    "slow_queries": { "value": 0, "unit": "count", "status": "normal" }
  },
  "resource": {
    "buffer_hit_ratio": { "value": 99.8, "unit": "%", "status": "normal" },
    "disk_iops": { "value": 0, "unit": "ops/s", "status": "normal" }
  },
  "connection": {
    "active_sessions": { "value": 3, "unit": "count", "status": "normal" },
    "connection_usage_pct": { "value": 15.5, "unit": "%", "status": "normal" }
  },
  "lock": {
    "lock_waits": { "value": 0, "unit": "count", "status": "normal" },
    "deadlocks_per_sec": { "value": 0, "unit": "count/s", "status": "normal" }
  },
  "storage": {
    "db_size_bytes": { "value": 8958435, "unit": "bytes", "status": "normal" },
    "replication_lag_sec": { "value": null, "unit": "sec", "status": "unknown" }
  }
}
```

---

## 6. Advisory 시스템 (확장 미설치 감지 + 알림)

### 6.1 KPI Advisory

KPI API 응답에 `advisories` 배열을 포함하여, 대상 DB의 구성 문제를 사전에 감지하고 사용자에게 안내한다.

```python
class KPIAdvisory(BaseModel):
    level: Literal["info", "warning", "error"]
    title: str          # 문제 요약 (e.g., "pg_stat_statements 미설치")
    message: str        # 상세 설명
    action: str | None  # 해결 SQL (e.g., "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;")
```

### 6.2 감지 대상

| 조건 | Level | Title | Action |
|------|-------|-------|--------|
| `pg_stat_statements` 미설치 (avg_response_time = null) | warning | pg_stat_statements 미설치 | `CREATE EXTENSION IF NOT EXISTS pg_stat_statements;` |
| Replication 미구성 (replication_lag = null) | info | Replication 미구성 | None |

### 6.3 Toast 알림 컴포넌트

```
┌─ Toast (화면 우상단) ─────────────────────┐
│ ⚠️ pg_stat_statements 미설치              │  ← warning: 12초 후 자동 닫힘
│ 쿼리 성능 분석에 필요한 확장이 설치되어    │     info: 8초 후 자동 닫힘
│ 있지 않습니다.                        [✕] │
└──────────────────────────────────────────┘
```

- 같은 title+instanceName의 Toast는 중복 표시하지 않음
- 여러 Toast는 수직 스택으로 쌓임
- Level별 색상: info=primary, warning=warning-container, error=error-container

### 6.4 Notification Panel (알림 벨 드롭다운)

TopNav 알림 아이콘(🔔) 클릭 시 드롭다운 패널 표시:

```
┌─ Notifications ──────────────────────────┐
│ ⚠️ pg_stat_statements 미설치 (inst-name) │
│   쿼리 성능 분석에 필요한 확장이...       │
│   ┌──────────────────────────────────┐   │
│   │ CREATE EXTENSION IF NOT EXISTS   │ 📋│  ← 클립보드 복사 버튼
│   │ pg_stat_statements;              │   │
│   └──────────────────────────────────┘   │
│                                          │
│ ℹ️ Replication 미구성 (inst-name)         │
│   단일 인스턴스 모드입니다.              │
│                                          │
│ [Mark all read]  [Clear all]             │
└──────────────────────────────────────────┘
```

- 미읽음 알림 수: 🔔 아이콘에 빨간 배지로 표시
- 최대 50개 알림 (FIFO)
- 동일 title+instanceName 중복 방지
- action 필드가 있으면 monospace 코드 블록 + 복사 버튼 표시

### 6.5 Notification Store (Zustand)

```typescript
interface Notification {
  id: string;
  level: 'info' | 'warning' | 'error';
  title: string;
  message: string;
  action?: string;
  timestamp: Date;
  read: boolean;
  instanceName?: string;
}
```

---

## 7. 인수 기준

- [ ] AC-1: GET /api/v1/instances/{id}/kpi에서 12개 KPI가 모두 반환됨
- [ ] AC-2: TPS, QPS, Deadlocks는 delta/초 기반으로 계산됨
- [ ] AC-3: Buffer Hit Ratio는 delta 기반 (누적 비율이 아님)
- [ ] AC-4: 인스턴스 카드에 5개 핵심 KPI가 표시됨 (TPS, Hit%, Conn, Locks, Size)
- [ ] AC-5: KPI Overview Panel이 인스턴스 선택 시 12개 전체 KPI 표시
- [ ] AC-6: 임계값에 따라 normal/warning/critical 색상 코딩
- [ ] AC-7: max_connections 대비 연결 사용률(%) 표시
- [ ] AC-8: pg_stat_statements 미설치 시 advisory warning + CREATE EXTENSION SQL 안내
- [ ] AC-9: Toast 알림이 화면 우상단에 표시되고 자동 닫힘 (info 8초, warning 12초)
- [ ] AC-10: Notification Panel에서 advisory 목록 확인 + SQL action 복사 가능
- [ ] AC-11: 알림 벨에 미읽음 수 빨간 배지 표시
