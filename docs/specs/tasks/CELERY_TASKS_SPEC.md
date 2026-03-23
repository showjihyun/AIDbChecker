# Celery Tasks Spec: 비동기 태스크 정의

> **Spec ID**: TASK-001
> **PRD 참조**: FR-DB-001, FR-AI-001, FR-AI-010, FR-AI-014
> **상태**: Approved
> **아키텍처 참조**: ai-db-monitor-architecture-spec-v3.md
> **설정 참조**: SETTINGS_SPEC.md
> **WebSocket 참조**: WEBSOCKET_EVENTS_SPEC.md (FE-WS-001)

---

## 1. Celery 설정

```python
# backend/app/tasks/celery_app.py
# Spec: TASK-001

from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

app = Celery("neuraldb")

app.config_from_object({
    # ── Broker & Backend ──
    "broker_url": settings.VALKEY_URL.replace("/0", f"/{settings.VALKEY_CELERY_DB}"),
    "result_backend": settings.VALKEY_URL.replace("/0", f"/{settings.VALKEY_CELERY_DB}"),

    # ── 직렬화 ──
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
    "timezone": "UTC",
    "enable_utc": True,

    # ── 안정성 ──
    "task_track_started": True,       # STARTED 상태 추적
    "task_acks_late": True,           # 태스크 완료 후 ACK (worker crash 시 재처리)
    "worker_prefetch_multiplier": 1,  # 태스크 하나씩 가져옴 (긴 태스크 방지)
    "task_reject_on_worker_lost": True,  # worker 비정상 종료 시 재큐잉

    # ── 결과 ──
    "result_expires": 3600,           # 결과 1시간 유지
    "result_extended": True,          # 결과에 traceback 포함

    # ── 큐 라우팅 ──
    "task_routes": {
        "app.tasks.collect_*": {"queue": "metrics"},
        "app.tasks.mtl_*": {"queue": "ai"},
        "app.tasks.rag_*": {"queue": "ai"},
        "app.tasks.embed_*": {"queue": "ai"},
        "app.tasks.retrain_*": {"queue": "ai"},
        "app.tasks.detect_*": {"queue": "ai"},
        "app.tasks.alert_*": {"queue": "alerts"},
        "app.tasks.dispatch_*": {"queue": "alerts"},
    },

    # ── 큐 정의 ──
    "task_queues": {
        "metrics": {"exchange": "metrics", "routing_key": "metrics"},
        "ai": {"exchange": "ai", "routing_key": "ai"},
        "alerts": {"exchange": "alerts", "routing_key": "alerts"},
    },

    # ── Worker 제한 ──
    "worker_max_tasks_per_child": 1000,   # 메모리 릭 방지: 1000개 처리 후 worker 재시작
    "worker_max_memory_per_child": 512000, # 512MB 초과 시 worker 재시작
})
```

---

## 2. Beat Schedule

```python
# backend/app/tasks/celery_app.py (계속)
# Spec: TASK-001

app.conf.beat_schedule = {
    # ── Metric Collection ──
    "collect-hot-metrics": {
        "task": "app.tasks.collect_hot_metrics",
        "schedule": settings.COLLECT_HOT_INTERVAL_SEC,  # 1.0s (기본값)
        "args": [],
        "options": {"queue": "metrics", "expires": 2},  # 2초 내 처리 못하면 폐기
    },
    "collect-warm-metrics": {
        "task": "app.tasks.collect_warm_metrics",
        "schedule": settings.COLLECT_WARM_INTERVAL_SEC,  # 10.0s (기본값)
        "args": [],
        "options": {"queue": "metrics", "expires": 15},
    },
    "collect-cold-metrics": {
        "task": "app.tasks.collect_cold_metrics",
        "schedule": settings.COLLECT_COLD_INTERVAL_SEC,  # 60.0s (기본값)
        "args": [],
        "options": {"queue": "metrics", "expires": 90},
    },

    # ── ASH Sampling ──
    "collect-ash-samples": {
        "task": "app.tasks.collect_ash_samples",
        "schedule": 1.0,  # 항상 1초 (Hot 메트릭과 동일)
        "args": [],
        "options": {"queue": "metrics", "expires": 2},
    },

    # ── AI / ML ──
    "retrain-baselines": {
        "task": "app.tasks.retrain_baselines",
        "schedule": crontab(minute=0, hour="*/6"),  # 매 6시간 (00:00, 06:00, 12:00, 18:00 UTC)
        "args": [],
        "options": {"queue": "ai", "expires": 3600},
    },
    "detect-anomalies": {
        "task": "app.tasks.detect_anomalies",
        "schedule": 10.0,  # 10초마다
        "args": [],
        "options": {"queue": "ai", "expires": 15},
    },
}
```

---

## 3. Task Definitions

### 3.1 Metric Collection Tasks

#### collect_hot_metrics

```python
# backend/app/tasks/metric_tasks.py
# Spec: TASK-001 / FR-DB-001

@app.task(
    bind=True,
    name="app.tasks.collect_hot_metrics",
    max_retries=3,
    default_retry_delay=5,
    soft_time_limit=5,
    time_limit=10,
    queue="metrics",
)
def collect_hot_metrics(self):
    """
    모든 활성 인스턴스의 Hot 메트릭 수집 (1초 주기).

    Hot 메트릭:
    - cpu_usage, memory_usage, active_connections, tps,
      buffer_hit_ratio, cache_hit_ratio

    Input:  None (전체 활성 인스턴스 대상)
    Output: int (수집 성공 건수)

    동작 흐름:
    1. Valkey 분산 락 획득 (중복 실행 방지)
    2. 전체 활성 인스턴스 조회 (is_active=True)
    3. 각 인스턴스에 대해 pg_stat_activity + pg_stat_bgwriter 등 쿼리
    4. 수집 결과를 MetricSample로 DB 저장
    5. WebSocket metric:update 이벤트 브로드캐스트
    6. 수집 건수 반환

    예외 처리:
    - ConnectionError (DB 연결 실패) → 3회 재시도 (5초 간격)
    - SoftTimeLimitExceeded → 현재까지 수집한 데이터 저장 후 반환
    - 개별 인스턴스 실패 → 해당 인스턴스만 skip, 나머지 계속 수집
    """
    lock_key = f"task:collect_hot:{int(time.time())}"
    if not cache.set(lock_key, "1", nx=True, ex=10):
        logger.info("collect_hot_metrics already running, skipping")
        return 0

    try:
        instances = instance_repo.get_active_instances()
        success_count = 0
        for instance in instances:
            try:
                metrics = collector.collect_hot(instance)
                metric_service.ingest(instance.id, "hot", metrics)
                success_count += 1
            except ConnectionError as exc:
                logger.warning(f"Failed to collect from {instance.name}: {exc}")
            except Exception as exc:
                logger.error(f"Unexpected error collecting from {instance.name}: {exc}")
        return success_count
    except SoftTimeLimitExceeded:
        logger.warning("collect_hot_metrics soft time limit exceeded")
        return success_count
    except Exception as exc:
        self.retry(exc=exc)
```

#### collect_warm_metrics

```python
@app.task(
    bind=True,
    name="app.tasks.collect_warm_metrics",
    max_retries=3,
    default_retry_delay=10,
    soft_time_limit=10,
    time_limit=20,
    queue="metrics",
)
def collect_warm_metrics(self):
    """
    모든 활성 인스턴스의 Warm 메트릭 수집 (10초 주기).

    Warm 메트릭:
    - lock_count, deadlocks, long_running_queries,
      replication_lag_ms, temp_bytes, table_bloat_ratio

    Input:  None
    Output: int (수집 성공 건수)

    동작 흐름: collect_hot_metrics와 동일 패턴
    예외 처리: collect_hot_metrics와 동일 (재시도 간격 10초)
    """
    ...
```

#### collect_cold_metrics

```python
@app.task(
    bind=True,
    name="app.tasks.collect_cold_metrics",
    max_retries=3,
    default_retry_delay=30,
    soft_time_limit=30,
    time_limit=60,
    queue="metrics",
)
def collect_cold_metrics(self):
    """
    모든 활성 인스턴스의 Cold 메트릭 수집 (60초 주기).

    Cold 메트릭:
    - table_sizes, index_sizes, vacuum_stats,
      pg_stat_statements top queries, schema_info

    Input:  None
    Output: int (수집 성공 건수)

    동작 흐름: collect_hot_metrics와 동일 패턴
    예외 처리: collect_hot_metrics와 동일 (재시도 간격 30초)
    """
    ...
```

#### collect_ash_samples

```python
@app.task(
    bind=True,
    name="app.tasks.collect_ash_samples",
    max_retries=3,
    default_retry_delay=5,
    soft_time_limit=5,
    time_limit=10,
    queue="metrics",
)
def collect_ash_samples(self):
    """
    모든 활성 인스턴스의 ASH 1초 샘플링.

    수집 내용:
    - pg_stat_activity 스냅샷 (pid, query, state, wait_event_type, wait_event, 등)

    Input:  None
    Output: int (수집 성공 건수)

    동작 흐름:
    1. Valkey 분산 락 획득
    2. 전체 활성 인스턴스 조회
    3. 각 인스턴스에 대해 pg_stat_activity SELECT
    4. ASH 샘플을 ash_samples 테이블에 저장
    5. 수집 건수 반환

    예외 처리: collect_hot_metrics와 동일
    """
    ...
```

### 3.2 AI Tasks

#### trigger_mtl_rca

```python
# backend/app/tasks/ai_tasks.py
# Spec: TASK-001 / FR-AI-010

@app.task(
    bind=True,
    name="app.tasks.trigger_mtl_rca",
    max_retries=2,
    default_retry_delay=10,
    soft_time_limit=30,
    time_limit=45,
    queue="ai",
)
def trigger_mtl_rca(self, incident_id: str):
    """
    인시던트 → 경량 RAG 검색 → MTL Lite 추론 → 결과 저장.

    Input:  incident_id (UUID string)
    Output: prediction_id (UUID string)

    동작 흐름:
    1. 인시던트 상세 조회 (incident + 관련 메트릭)
    2. 경량 RAG 검색: 유사 인시던트 top-3 조회
    3. MTL Lite 4-Head 동시 추론:
       - Head 1: 이상 유형 분류 (Anomaly Classification)
       - Head 2: 근본 원인 분석 (Root Cause Analysis)
       - Head 3: 영향도 예측 (Impact Prediction)
       - Head 4: 조치 추천 (Recommendation)
    4. Confidence Score 계산 (내부 일관성 + RAG 유사도 + 모델 확신도)
    5. Reasoning Chain 구성
    6. MTLPrediction DB 저장
    7. prediction_id 반환

    예외 처리:
    - LLM Timeout (30초) → 2회 재시도 (10초 간격)
    - 재시도 모두 실패 → confidence=0.0 저장 + 관리자 알림
    - RAG 검색 실패 → RAG 없이 MTL 추론 진행 (degraded mode)
    """
    try:
        incident = incident_repo.get(incident_id)
        if not incident:
            logger.error(f"Incident {incident_id} not found")
            return None

        # RAG 검색 (실패해도 계속 진행)
        similar_incidents = []
        try:
            similar_incidents = rag_service.search_similar(
                query=incident.description,
                top_k=3,
                min_score=0.5,
            )
        except Exception as exc:
            logger.warning(f"RAG search failed for {incident_id}: {exc}")

        # MTL 추론
        prediction = mtl_service.predict(
            incident=incident,
            similar_incidents=similar_incidents,
            related_metrics=metric_service.get_recent(incident.instance_id, minutes=30),
        )

        # 저장
        prediction_id = prediction_repo.save(prediction)

        # 인시던트에 prediction_id 연결
        incident_repo.set_prediction(incident_id, prediction_id)

        return str(prediction_id)

    except SoftTimeLimitExceeded:
        logger.error(f"MTL RCA timeout for incident {incident_id}")
        # 실패 prediction 저장
        prediction_id = prediction_repo.save_failed(
            incident_id=incident_id,
            error="Timeout: MTL inference exceeded 30s limit",
        )
        dispatch_alert.delay(incident_id, str(prediction_id))
        return str(prediction_id)

    except Exception as exc:
        logger.error(f"MTL RCA failed for {incident_id}: {exc}")
        self.retry(exc=exc)
```

#### embed_incident

```python
@app.task(
    bind=True,
    name="app.tasks.embed_incident",
    max_retries=2,
    default_retry_delay=5,
    soft_time_limit=10,
    time_limit=15,
    queue="ai",
)
def embed_incident(self, incident_id: str):
    """
    인시던트 → sentence-transformers 임베딩 → pgvector 저장.

    Input:  incident_id (UUID string)
    Output: rag_document_id (UUID string)

    동작 흐름:
    1. 인시던트 상세 조회 (title + description + root_cause)
    2. 텍스트 전처리 (SQL 토큰화, 중복 공백 제거)
    3. sentence-transformers 모델로 임베딩 (384차원 벡터)
    4. pgvector rag_documents 테이블에 저장
    5. rag_document_id 반환

    모델: all-MiniLM-L6-v2 (경량, 384차원)

    예외 처리:
    - 모델 로딩 실패 → 2회 재시도 (5초 간격)
    - 재시도 모두 실패 → 로그 ERROR, 수동 재실행 필요
    """
    try:
        incident = incident_repo.get(incident_id)
        if not incident:
            logger.error(f"Incident {incident_id} not found")
            return None

        # 텍스트 준비
        text = f"{incident.title}\n{incident.description}"
        if incident.rca and incident.rca.root_cause:
            text += f"\nRoot Cause: {incident.rca.root_cause}"

        # 임베딩
        embedding = embedding_service.encode(text)

        # pgvector 저장
        doc_id = rag_repo.upsert_document(
            incident_id=incident_id,
            content=text,
            embedding=embedding,
        )

        return str(doc_id)

    except Exception as exc:
        logger.error(f"Embedding failed for incident {incident_id}: {exc}")
        self.retry(exc=exc)
```

#### retrain_baselines

```python
@app.task(
    bind=True,
    name="app.tasks.retrain_baselines",
    max_retries=0,  # 재시도 없음 (다음 6시간 주기에 재시도)
    soft_time_limit=60,
    time_limit=90,
    queue="ai",
)
def retrain_baselines(self):
    """
    전체 인스턴스 베이스라인 재학습 (STL + Isolation Forest).

    Input:  None
    Output: dict { instance_id: status }

    동작 흐름:
    1. 전체 활성 인스턴스 조회
    2. 각 인스턴스에 대해:
       a. 최근 7일 메트릭 데이터 조회
       b. 데이터 포인트 최소 요건 확인 (>= 60,480 포인트 = 7일 * 1초)
       c. STL 분해 (Seasonal-Trend decomposition): 시계열 → trend + seasonal + residual
       d. Isolation Forest 학습: residual 기반 이상치 경계 학습
       e. 베이스라인 모델 저장 (joblib → Valkey 캐시 + DB)
       f. baseline_status 업데이트
    3. 결과 요약 반환

    예외 처리:
    - 개별 인스턴스 실패 → skip, 다른 인스턴스 계속 처리
    - 데이터 부족 → baseline_status = 'insufficient_data' 설정
    - 전체 실패 → 다음 6시간 주기에 자동 재시도
    """
    results = {}
    instances = instance_repo.get_active_instances()

    for instance in instances:
        try:
            metrics_7d = metric_repo.get_range(
                instance_id=instance.id,
                from_time=datetime.utcnow() - timedelta(days=7),
                to_time=datetime.utcnow(),
            )

            if len(metrics_7d) < 60_480:
                baseline_repo.update_status(instance.id, 'insufficient_data')
                results[str(instance.id)] = 'insufficient_data'
                continue

            # STL 분해
            decomposition = baseline_service.stl_decompose(metrics_7d)

            # Isolation Forest 학습
            model = baseline_service.train_isolation_forest(decomposition.residual)

            # 저장
            baseline_repo.save_model(instance.id, model, decomposition)
            baseline_repo.update_status(instance.id, 'ready')
            results[str(instance.id)] = 'ready'

        except Exception as exc:
            logger.error(f"Baseline retrain failed for {instance.name}: {exc}")
            baseline_repo.update_status(instance.id, 'stale')
            results[str(instance.id)] = 'error'

    return results
```

#### detect_anomalies

```python
@app.task(
    bind=True,
    name="app.tasks.detect_anomalies",
    max_retries=0,  # 재시도 없음 (10초 후 다음 주기)
    soft_time_limit=10,
    time_limit=15,
    queue="ai",
)
def detect_anomalies(self):
    """
    최신 메트릭 vs 베이스라인 비교 → 이상 시 인시던트 생성.

    Input:  None
    Output: list[str] (생성된 incident_id 목록)

    동작 흐름:
    1. 전체 활성 인스턴스 조회
    2. 각 인스턴스에 대해:
       a. 최신 메트릭 스냅샷 조회 (최근 10초)
       b. 베이스라인 모델 로딩 (Valkey 캐시 우선)
       c. Isolation Forest predict: -1이면 이상치
       d. Z-Score 계산: 3-sigma 초과 확인
       e. 이상치 감지 시:
          - metric:spike WebSocket 이벤트 발행
          - 기존 open 인시던트 중복 확인 (동일 인스턴스 + 유사 이상)
          - 중복 아니면 인시던트 생성 → incident:new 이벤트
          - trigger_mtl_rca.delay(incident_id)
    3. 생성된 인시던트 ID 목록 반환

    이상 감지 기준 (AND 조건):
    - Isolation Forest score < threshold (-0.5)
    - Z-Score > 3.0 (3-sigma rule)

    중복 인시던트 방지:
    - 동일 인스턴스에서 30분 이내 유사 이상 유형의 open 인시던트가 있으면 skip
    """
    created_incidents = []
    instances = instance_repo.get_active_instances()

    for instance in instances:
        try:
            baseline = baseline_repo.get_model(instance.id)
            if not baseline or baseline.status != 'ready':
                continue

            latest_metrics = metric_repo.get_latest(instance.id)
            if not latest_metrics:
                continue

            # 이상 감지
            anomalies = anomaly_detector.detect(
                metrics=latest_metrics,
                baseline=baseline,
                if_threshold=-0.5,
                zscore_threshold=3.0,
            )

            for anomaly in anomalies:
                # metric:spike WebSocket 이벤트
                await ws_emit_metric_spike(instance.id, anomaly)

                # 중복 확인
                if incident_repo.has_similar_open(instance.id, anomaly.type, minutes=30):
                    continue

                # 인시던트 생성
                incident = incident_service.create_from_anomaly(anomaly)
                created_incidents.append(str(incident.id))

                # MTL RCA 비동기 실행
                trigger_mtl_rca.delay(str(incident.id))

        except Exception as exc:
            logger.error(f"Anomaly detection failed for {instance.name}: {exc}")

    return created_incidents
```

### 3.3 Alert Tasks

#### dispatch_alert

```python
# backend/app/tasks/alert_tasks.py
# Spec: TASK-001 / FR-ALERT-001

@app.task(
    bind=True,
    name="app.tasks.dispatch_alert",
    max_retries=3,
    default_retry_delay=5,
    soft_time_limit=10,
    time_limit=15,
    queue="alerts",
)
def dispatch_alert(self, incident_id: str, prediction_id: str | None = None):
    """
    Slack/Email/Webhook 알림 발송.

    Input:
    - incident_id: 인시던트 UUID
    - prediction_id: MTL 예측 UUID (있는 경우)

    Output: dict { channel_id: status }

    동작 흐름:
    1. 인시던트 조회
    2. 쿨다운 확인: 동일 인스턴스 5분 이내 발송 이력 있으면 skip
    3. 활성 알림 채널 목록 조회
    4. 예측 결과 조회 (prediction_id가 있는 경우)
    5. 각 채널별 메시지 포맷팅:
       - Slack: Block Kit 형식 (severity 색상 + 제목 + root_cause + confidence)
       - Email: HTML 템플릿
       - Webhook: JSON payload
    6. 각 채널로 발송
    7. 발송 결과 반환

    쿨다운 정책:
    - Valkey key: "alert_cooldown:{instance_id}"
    - TTL: 300초 (5분)
    - CRITICAL severity는 쿨다운 무시

    예외 처리:
    - Slack API 실패 → 3회 재시도 (5초 간격)
    - 전체 실패 → 로그 CRITICAL + Webhook 폴백 (설정된 경우)
    """
    try:
        incident = incident_repo.get(incident_id)
        if not incident:
            logger.error(f"Incident {incident_id} not found")
            return {}

        # 쿨다운 확인 (CRITICAL은 제외)
        if incident.severity != 'CRITICAL':
            cooldown_key = f"alert_cooldown:{incident.instance_id}"
            if cache.exists(cooldown_key):
                logger.info(f"Alert cooldown active for instance {incident.instance_id}")
                return {"status": "cooldown"}

        # 쿨다운 설정
        cache.set(f"alert_cooldown:{incident.instance_id}", "1", ex=300)

        # 예측 결과 조회
        prediction = None
        if prediction_id:
            prediction = prediction_repo.get(prediction_id)

        # 활성 채널 조회 및 발송
        channels = alert_channel_repo.get_enabled()
        results = {}

        for channel in channels:
            try:
                message = alert_formatter.format(
                    channel_type=channel.type,
                    incident=incident,
                    prediction=prediction,
                )
                alert_sender.send(channel, message)
                results[str(channel.id)] = "sent"
            except Exception as exc:
                logger.error(f"Alert send failed for channel {channel.name}: {exc}")
                results[str(channel.id)] = "failed"

        return results

    except Exception as exc:
        logger.error(f"dispatch_alert failed for incident {incident_id}: {exc}")
        self.retry(exc=exc)
```

---

## 4. Worker 구성 (MVP Docker Compose)

### 4.1 Docker Compose 서비스 정의

```yaml
# docker-compose.yml (발췌)
# Spec: TASK-001

services:
  # ── Metrics Worker (2 프로세스) ──
  celery-worker-metrics:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: >
      uv run celery -A app.tasks.celery_app worker
      --queues=metrics
      --concurrency=2
      --pool=prefork
      --loglevel=info
      --hostname=worker-metrics@%h
    environment:
      - VALKEY_URL=${VALKEY_URL}
      - DATABASE_URL=${DATABASE_URL}
    depends_on:
      - valkey
      - postgres
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '1.0'

  # ── AI Worker (1 프로세스) ──
  celery-worker-ai:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: >
      uv run celery -A app.tasks.celery_app worker
      --queues=ai
      --concurrency=1
      --pool=prefork
      --loglevel=info
      --hostname=worker-ai@%h
    environment:
      - VALKEY_URL=${VALKEY_URL}
      - DATABASE_URL=${DATABASE_URL}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    depends_on:
      - valkey
      - postgres
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '2.0'

  # ── Alerts Worker (1 프로세스) ──
  celery-worker-alerts:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: >
      uv run celery -A app.tasks.celery_app worker
      --queues=alerts
      --concurrency=1
      --pool=prefork
      --loglevel=info
      --hostname=worker-alerts@%h
    environment:
      - VALKEY_URL=${VALKEY_URL}
      - DATABASE_URL=${DATABASE_URL}
      - SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL}
    depends_on:
      - valkey
      - postgres
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: '0.5'

  # ── Beat Scheduler (단일 인스턴스) ──
  celery-beat:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: >
      uv run celery -A app.tasks.celery_app beat
      --loglevel=info
      --scheduler=celery.beat.PersistentScheduler
      --schedule=/tmp/celerybeat-schedule
    environment:
      - VALKEY_URL=${VALKEY_URL}
    depends_on:
      - valkey
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 128M
          cpus: '0.25'
      replicas: 1  # Beat는 반드시 1개만 실행
```

### 4.2 Worker CLI 명령 (개발 환경)

```bash
# Metrics Worker (2 프로세스)
uv run celery -A app.tasks.celery_app worker --queues=metrics --concurrency=2 --pool=prefork --loglevel=info

# AI Worker (1 프로세스)
uv run celery -A app.tasks.celery_app worker --queues=ai --concurrency=1 --pool=prefork --loglevel=info

# Alerts Worker (1 프로세스)
uv run celery -A app.tasks.celery_app worker --queues=alerts --concurrency=1 --pool=prefork --loglevel=info

# Beat Scheduler (단일)
uv run celery -A app.tasks.celery_app beat --loglevel=info

# 전체 Worker 상태 확인
uv run celery -A app.tasks.celery_app inspect active
uv run celery -A app.tasks.celery_app inspect stats
```

### 4.3 Worker 구성 요약

| Worker | Queue | Concurrency | Pool | Memory Limit | CPU Limit | 용도 |
|--------|-------|-------------|------|-------------|-----------|------|
| worker-metrics | metrics | 2 | prefork | 512MB | 1.0 | 1초/10초/60초 메트릭 수집 |
| worker-ai | ai | 1 | prefork | 1GB | 2.0 | MTL 추론, 임베딩, 이상 감지 |
| worker-alerts | alerts | 1 | prefork | 256MB | 0.5 | Slack/Email/Webhook 발송 |
| celery-beat | - | - | - | 128MB | 0.25 | 스케줄 발행 (단일 인스턴스) |

---

## 5. 에러 처리 정책

### 5.1 태스크별 에러 처리 매트릭스

| 태스크 | 재시도 횟수 | 재시도 간격 | 재시도 실패 시 | 로그 레벨 |
|--------|-----------|-----------|--------------|----------|
| `collect_hot_metrics` | 3회 | 5초 | 로그 WARNING, 다음 주기(1초)에 재시도 | WARNING |
| `collect_warm_metrics` | 3회 | 10초 | 로그 WARNING, 다음 주기(10초)에 재시도 | WARNING |
| `collect_cold_metrics` | 3회 | 30초 | 로그 WARNING, 다음 주기(60초)에 재시도 | WARNING |
| `collect_ash_samples` | 3회 | 5초 | 로그 WARNING, 다음 주기(1초)에 재시도 | WARNING |
| `trigger_mtl_rca` | 2회 | 10초 | confidence=0.0 저장 + 관리자 알림 | ERROR |
| `embed_incident` | 2회 | 5초 | 로그 ERROR, 수동 재실행 필요 | ERROR |
| `retrain_baselines` | 0회 | - | 다음 6시간 주기에 자동 재시도 | ERROR |
| `detect_anomalies` | 0회 | - | 다음 10초 주기에 자동 재시도 | ERROR |
| `dispatch_alert` | 3회 | 5초 | 로그 CRITICAL + webhook 폴백 | CRITICAL |

### 5.2 공통 예외 처리 패턴

```python
# backend/app/tasks/base.py
# Spec: TASK-001

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

class BaseTask(Task):
    """모든 NeuralDB 태스크의 기본 클래스"""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """태스크 최종 실패 시 호출"""
        logger.error(
            f"Task {self.name} failed permanently",
            extra={
                "task_id": task_id,
                "args": args,
                "exception": str(exc),
                "traceback": str(einfo),
            }
        )
        # Prometheus 메트릭 증가
        TASK_FAILURES_TOTAL.labels(task_name=self.name).inc()

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """재시도 시 호출"""
        logger.warning(
            f"Task {self.name} retrying",
            extra={
                "task_id": task_id,
                "attempt": self.request.retries + 1,
                "max_retries": self.max_retries,
                "exception": str(exc),
            }
        )
        TASK_RETRIES_TOTAL.labels(task_name=self.name).inc()

    def on_success(self, retval, task_id, args, kwargs):
        """태스크 성공 시 호출"""
        TASK_SUCCESSES_TOTAL.labels(task_name=self.name).inc()
```

---

## 6. 중복 실행 방지 (Idempotency)

### 6.1 Valkey Distributed Lock

```python
# backend/app/tasks/locks.py
# Spec: TASK-001

import time
from app.core.cache import cache

def acquire_task_lock(
    task_name: str,
    instance_id: str | None = None,
    timestamp_bucket: int | None = None,
    ttl_seconds: int = 10,
) -> bool:
    """
    Valkey 분산 락을 획득한다.

    Lock Key 패턴:
    - Beat 태스크:  "task:{task_name}:{timestamp_bucket}"
    - 인스턴스별:   "task:{task_name}:{instance_id}:{timestamp_bucket}"

    Args:
        task_name: 태스크 이름 (e.g., "collect_hot")
        instance_id: 인스턴스 UUID (인스턴스별 락 필요 시)
        timestamp_bucket: 타임스탬프 버킷 (기본: 현재 초)
        ttl_seconds: 락 TTL (기본: soft_time_limit * 2)

    Returns:
        True: 락 획득 성공, False: 이미 실행 중
    """
    if timestamp_bucket is None:
        timestamp_bucket = int(time.time())

    parts = ["task", task_name]
    if instance_id:
        parts.append(instance_id)
    parts.append(str(timestamp_bucket))

    lock_key = ":".join(parts)

    acquired = cache.set(lock_key, "1", nx=True, ex=ttl_seconds)
    if not acquired:
        logger.info(f"Task {task_name} already running (lock: {lock_key}), skipping")
    return bool(acquired)


def release_task_lock(
    task_name: str,
    instance_id: str | None = None,
    timestamp_bucket: int | None = None,
):
    """락 명시적 해제 (정상 완료 시)"""
    if timestamp_bucket is None:
        timestamp_bucket = int(time.time())

    parts = ["task", task_name]
    if instance_id:
        parts.append(instance_id)
    parts.append(str(timestamp_bucket))

    lock_key = ":".join(parts)
    cache.delete(lock_key)
```

### 6.2 락 TTL 설정

| 태스크 | soft_time_limit | Lock TTL | 설명 |
|--------|----------------|----------|------|
| `collect_hot_metrics` | 5초 | 10초 | soft_time_limit * 2 |
| `collect_warm_metrics` | 10초 | 20초 | soft_time_limit * 2 |
| `collect_cold_metrics` | 30초 | 60초 | soft_time_limit * 2 |
| `collect_ash_samples` | 5초 | 10초 | soft_time_limit * 2 |
| `trigger_mtl_rca` | 30초 | 60초 | soft_time_limit * 2 |
| `detect_anomalies` | 10초 | 20초 | soft_time_limit * 2 |
| `retrain_baselines` | 60초 | 120초 | soft_time_limit * 2 |
| `dispatch_alert` | 10초 | 20초 | soft_time_limit * 2 |

---

## 7. Prometheus 모니터링 메트릭

```python
# backend/app/tasks/metrics.py
# Spec: TASK-001

from prometheus_client import Counter, Histogram, Gauge

# 태스크 실행 카운터
TASK_SUCCESSES_TOTAL = Counter(
    "celery_task_successes_total",
    "Total successful task executions",
    ["task_name"],
)

TASK_FAILURES_TOTAL = Counter(
    "celery_task_failures_total",
    "Total failed task executions (after all retries)",
    ["task_name"],
)

TASK_RETRIES_TOTAL = Counter(
    "celery_task_retries_total",
    "Total task retry attempts",
    ["task_name"],
)

# 태스크 실행 시간
TASK_DURATION_SECONDS = Histogram(
    "celery_task_duration_seconds",
    "Task execution duration in seconds",
    ["task_name"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

# 큐 깊이
QUEUE_DEPTH = Gauge(
    "celery_queue_depth",
    "Number of tasks waiting in queue",
    ["queue_name"],
)

# 메트릭 수집 건수
METRICS_COLLECTED_TOTAL = Counter(
    "neuraldb_metrics_collected_total",
    "Total metric samples collected",
    ["category"],  # hot, warm, cold, ash
)

# 이상 감지 건수
ANOMALIES_DETECTED_TOTAL = Counter(
    "neuraldb_anomalies_detected_total",
    "Total anomalies detected",
    ["severity"],
)
```

---

## 8. 태스크 의존성 흐름

```
                        ┌──────────────────┐
                        │  Celery Beat      │
                        │  (스케줄러)        │
                        └─────┬────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         v                    v                    v
┌─────────────────┐ ┌──────────────────┐ ┌─────────────────┐
│ collect_hot     │ │ collect_warm     │ │ retrain_        │
│ _metrics (1s)   │ │ _metrics (10s)   │ │ baselines (6h)  │
├─────────────────┤ ├──────────────────┤ └────────┬────────┘
│ collect_ash     │ │ collect_cold     │          │
│ _samples (1s)   │ │ _metrics (60s)   │          v
└────────┬────────┘ └──────────────────┘   baseline 모델
         │                                    저장
         v
┌──────────────────┐
│ detect_anomalies │  (10초마다)
│ (baseline 비교)   │
└────────┬─────────┘
         │ 이상 감지 시
         v
┌──────────────────┐
│ IncidentService  │
│ .create_from_    │
│  anomaly()       │
└───┬─────────┬────┘
    │         │
    v         v
┌────────┐ ┌──────────────┐
│dispatch│ │trigger_mtl   │
│_alert  │ │_rca          │
└────────┘ └──────┬───────┘
                  │ 완료 후
                  v
           ┌──────────────┐
           │embed_incident│
           └──────────────┘
```

---

## 9. 인수 기준

| ID | 기준 | 검증 방법 |
|----|------|----------|
| AC-1 | Beat 스케줄이 1초/10초/60초/6시간 간격으로 정확히 태스크를 발행한다 | 통합 테스트: Beat 시작 후 60초간 태스크 발행 로그 확인 |
| AC-2 | 태스크 실패 시 지정된 횟수만큼 재시도한다 | 단위 테스트: mock DB 연결 실패 → 재시도 횟수 카운트 |
| AC-3 | 중복 실행이 방지된다 (동일 인스턴스, 동일 초에 2번 수집 불가) | 통합 테스트: 동시에 2개 태스크 발행 → 1개만 실행 확인 |
| AC-4 | queue별 Worker가 분리 동작한다 (metrics/ai/alerts) | 통합 테스트: 각 큐에 태스크 발행 → 해당 Worker에서만 실행 확인 |
| AC-5 | trigger_mtl_rca 최종 실패 시 confidence=0.0 prediction이 저장된다 | 단위 테스트: LLM timeout mock → prediction 확인 |
| AC-6 | dispatch_alert 5분 쿨다운이 동작한다 (CRITICAL 제외) | 단위 테스트: WARNING 알림 2회 연속 → 2번째 skip 확인 |
| AC-7 | soft_time_limit 초과 시 태스크가 graceful하게 종료된다 | 단위 테스트: SoftTimeLimitExceeded 시뮬레이션 → 정상 반환 확인 |
| AC-8 | Prometheus 메트릭이 태스크 성공/실패/재시도를 추적한다 | 통합 테스트: /metrics 엔드포인트에서 celery_task_* 메트릭 확인 |
