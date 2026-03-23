# Technical Review #001: Adapter vs Agent 메트릭 수집 방식 검증

- **Date**: 2026-03-21
- **Reviewer**: Architecture Review
- **Status**: Reviewed → Spec 반영 완료
- **관련 Spec**: FR-DB-001, FR-DB-004, DM-001, AG-001

---

## 1. 검토 배경

PRD v3.2는 대상 DB 메트릭 수집을 **Remote Adapter** 방식(NeuralDB 백엔드에서 원격 `pg_stat_*` 조회)으로 설계하고 있다. 1초 해상도 수집이라는 요구사항(FR-DASH-003)과 50+ 인스턴스 동시 모니터링(비기능 요구사항)을 고려할 때, 이 방식의 성능적 한계와 확장 전략을 검증한다.

---

## 2. 비교 분석

### 2.1 수집 방식 비교

| 항목 | Remote Adapter (현재) | Local Agent/Collector |
|------|----------------------|----------------------|
| **배포 위치** | NeuralDB 백엔드 | 대상 DB 서버 (또는 사이드카) |
| **네트워크 의존** | 매 수집마다 TCP 왕복 | 로컬 소켓/Unix Domain |
| **1회 수집 지연** | 쿼리 2ms + RTT 2~20ms | 쿼리 2ms + RTT 0ms |
| **설치 요구** | 없음 (DB 접속 정보만) | 대상 서버에 프로세스 설치 필요 |
| **장애 격리** | 대상 DB 1개 타임아웃 → 전체 수집 사이클 영향 | 개별 독립, 영향 없음 |
| **방화벽** | NeuralDB→대상 DB 포트 오픈 필요 | Agent→NeuralDB 단방향만 |
| **리소스** | NeuralDB 서버에 집중 | 대상 서버에 분산 (~30MB/프로세스) |

### 2.2 규모별 성능 예측

```
1초 사이클 소요 시간 = N × (네트워크 RTT + 쿼리 시간)

가정: 쿼리 2ms, Celery Worker 4개 (동시 4개 DB 수집)
```

| DB 수 | RTT 2ms (같은 DC) | RTT 5ms (VPN) | RTT 20ms (리전 간) | 판정 |
|-------|-------------------|---------------|--------------------| -----|
| 5 | 5ms | 9ms | 28ms | 모두 OK |
| 10 | 10ms | 18ms | 55ms | 모두 OK |
| 20 | 20ms | 35ms | 110ms | OK / OK / ⚠️ |
| 50 | 50ms | 88ms | 275ms | OK / ⚠️ / ⚠️ |
| 100 | 100ms | 175ms | 550ms | ⚠️ / ❌ / ❌ |
| 200 | 200ms | 350ms | 1100ms | ❌ / ❌ / ❌ |

> Worker 병렬화(concurrency=N)로 완화 가능하나, Worker 수 = DB 수에 비례 → 리소스 비용 급증.
> 또한 단일 DB 타임아웃(5초) 시 해당 Worker가 점유되어 다른 DB 수집 지연 발생.

### 2.3 산업 참조

| 솔루션 | 방식 | 1초 수집 | 비고 |
|--------|------|---------|------|
| Datadog DBM | Local Agent | Yes | 대규모 필수 |
| Dynatrace | Local OneAgent | Yes | 커널 수준 계측 |
| IBM Instana | Local Agent | Yes | 1초가 핵심 차별점 |
| pganalyze | Remote Collector | No (10초) | 소규모 특화 |
| Percona PMM | **Hybrid** | 부분 | Agent=상세, Remote=기본 |
| Prometheus | Local Exporter | No (15초) | Exporter는 로컬 |

**결론: 1초 해상도를 대규모에서 보장하는 솔루션은 전부 로컬 수집.**

---

## 3. 검토 결론

### 3.1 현재 설계(Remote Adapter)의 타당성

| 판정 | 근거 |
|------|------|
| **Phase 1 (MVP): 적합** | DB 10대 이하, 같은 DC 내, 1초 수집 가능 |
| **Phase 2: 적합** | DB 20~30대까지 Worker 증설로 대응 가능 |
| **Phase 3: 부적합** | 50대 이상 + 리전 간 → 1초 보장 불가 |
| **Phase 4: 부적합** | 100대+ 멀티 DB → Collector 필수 |

### 3.2 권장 전략: 2-Tier Hybrid Adapter

```
┌──────────────────────────────────────────────────────────────┐
│  Tier 1: Lightweight Collector (Phase 3에서 추가)             │
│                                                              │
│  ┌─────────────────┐     ┌─────────────────┐                │
│  │ 대상 DB 서버 A   │     │ 대상 DB 서버 B   │                │
│  │                 │     │                 │                │
│  │  PostgreSQL     │     │  MySQL          │                │
│  │     ↑           │     │     ↑           │                │
│  │  Collector      │     │  Collector      │                │
│  │  (Python ~30MB) │     │  (Python ~30MB) │                │
│  │     │ 로컬수집   │     │     │ 로컬수집   │                │
│  └─────┼───────────┘     └─────┼───────────┘                │
│        │ Push (Kafka/gRPC)     │                             │
│        └───────────┬───────────┘                             │
│                    ▼                                         │
│  ┌─────────────────────────────────┐                        │
│  │  NeuralDB Backend               │                        │
│  │  MetricIngestionService          │                        │
│  └─────────────────────────────────┘                        │
│                                                              │
│  Tier 2: Remote Adapter (현재, Phase 1~2 + 폴백)             │
│                                                              │
│  NeuralDB Backend ──(TCP)──► 대상 DB (원격 pg_stat_* 조회)   │
│  - Collector 미설치 시 자동 폴백                              │
│  - 10초~1분 해상도로 다운그레이드                              │
│  - 소규모/테스트/PoC 환경용                                   │
└──────────────────────────────────────────────────────────────┘
```

### 3.3 Interface 설계 영향 (변경 불필요)

현재 `BaseAdapter` 인터페이스는 수정 없이 양쪽 모두 지원 가능:

```python
class BaseAdapter(ABC):
    """Phase 1: Remote 구현, Phase 3: Local 구현 추가"""

    @abstractmethod
    async def collect_metrics(self) -> MetricSample: ...

    @abstractmethod
    async def collect_ash(self) -> list[ActiveSession]: ...

# Phase 1 구현 (변경 없음)
class PostgreSQLRemoteAdapter(BaseAdapter):
    """NeuralDB 백엔드에서 원격 조회"""
    def __init__(self, dsn: str):
        self.pool = asyncpg.create_pool(dsn)  # 원격 커넥션

# Phase 3 추가 구현
class PostgreSQLLocalCollector(BaseAdapter):
    """대상 DB 서버에서 로컬 수집 후 Push"""
    def __init__(self):
        self.pool = asyncpg.create_pool("localhost")  # 로컬 커넥션

    async def push(self, data: MetricSample):
        """수집 후 Kafka 또는 gRPC로 NeuralDB에 전송"""
        await kafka_producer.send("metrics.ingest", data.to_bytes())
```

**핵심: Plugin Interface(SPI) 변경 없음. 배포 형태만 다른 구현체 추가.**

---

## 4. 리스크 및 완화

| 리스크 | 영향 | 완화 방안 |
|--------|------|----------|
| Phase 1에서 50대 이상 고객 요청 | 1초 수집 보장 불가 | 해상도 폴백(10초) 명시 + Phase 3 로드맵 안내 |
| 네트워크 지연이 큰 환경 (VPN/리전간) | 수집 누락 | `statement_timeout` + silent skip + 폴백 해상도 |
| 단일 DB 타임아웃이 전체에 영향 | Worker 점유 | DB별 독립 Celery Task + `soft_time_limit=3` |
| Collector 설치 거부 고객 | 상세 모니터링 불가 | Remote Adapter 폴백 (기능은 동일, 해상도만 저하) |
| Collector 버전 관리/업데이트 | 운영 복잡도 | Auto-update 매커니즘 (Phase 4) |

---

## 5. Phase별 반영 사항

| Phase | Adapter 전략 | 해상도 | 최대 DB 수 |
|-------|-------------|--------|-----------|
| **Phase 1 (MVP)** | Remote Adapter only | 1초(Hot), 10초(Warm), 1분(Cold) | ~20대 |
| **Phase 2 (AI 강화)** | Remote Adapter + Worker 최적화 | 동일 | ~30대 |
| **Phase 3 (멀티에이전트)** | **Hybrid** (Collector 추가 + Remote 폴백) | 1초 보장 | ~200대 |
| **Phase 4 (솔루션화)** | Collector 기본 + Remote 옵션 | 1초 보장 | 무제한 (수평 확장) |

---

## 6. Spec 반영 항목

- [x] PRD: Phase별 수집 전략 명시
- [x] Architecture Spec / AGENTS.md: 2-Tier Hybrid 설명 추가
- [x] Adapter SPI Spec: Remote/Local 양쪽 지원 가능 명시
- [x] 비기능 요구사항: 규모별 해상도 폴백 정책 추가
