# Service Layer Spec: 비즈니스 로직 서비스 계층

> **Spec ID**: SVC-001
> **PRD 참조**: §5 기능 요구사항 전체
> **상태**: Approved
> **Phase**: MVP

---

## 1. 서비스 아키텍처

```
FastAPI Route → Depends(get_service) → Service → Repository → SQLAlchemy → PostgreSQL
                                          ↓
                                    Valkey (cache)
                                    Kafka (events)
                                    LLM API (AI)
```

### DI 패턴

```python
# backend/app/api/deps.py
# Spec: SVC-001

from app.services.instance_service import InstanceService

async def get_instance_service(
    db: AsyncSession = Depends(get_db),
    cache: ValkeyCli = Depends(get_cache),
) -> InstanceService:
    return InstanceService(db=db, cache=cache)

# Route에서 사용:
@router.get("/instances")
async def list_instances(
    service: InstanceService = Depends(get_instance_service),
):
    return await service.list_all()
```

---

## 2. 서비스 정의

### 2.1 InstanceService

```python
# backend/app/services/instance_service.py
# Spec: SVC-001, FR-DB-001

class InstanceService:
    def __init__(self, db: AsyncSession, cache: ValkeyCli): ...

    async def list_all(self, cursor: str | None, limit: int = 20) -> PaginatedResult[InstanceResponse]:
        """등록된 인스턴스 목록 (커서 페이지네이션)"""

    async def get(self, instance_id: UUID) -> InstanceResponse:
        """인스턴스 상세 조회. 없으면 INSTANCE_NOT_FOUND"""

    async def create(self, data: InstanceCreateRequest) -> InstanceResponse:
        """인스턴스 등록. 중복 host:port → INSTANCE_DUPLICATE"""

    async def update(self, instance_id: UUID, data: InstanceUpdateRequest) -> InstanceResponse:
        """인스턴스 수정"""

    async def delete(self, instance_id: UUID) -> None:
        """인스턴스 삭제 + 관련 수집 태스크 중지"""

    async def test_connection(self, instance_id: UUID) -> ConnectionTestResult:
        """asyncpg로 연결 테스트 + pg_stat_statements 확인"""
        # Transaction: 읽기 전용, DB 변경 없음
        # Timeout: COLLECT_STATEMENT_TIMEOUT_MS
```

### 2.2 MetricService

```python
# backend/app/services/metric_service.py
# Spec: SVC-001, FR-DASH-001, FR-DB-001

class MetricService:
    def __init__(self, db: AsyncSession, cache: ValkeyCli): ...

    async def query(self, instance_id: UUID, metric_type: str | None,
                    from_time: datetime, to_time: datetime,
                    resolution: str = "auto") -> list[MetricSample]:
        """메트릭 범위 조회. resolution=auto → 시간 범위에 따라 자동 선택"""
        # Cache: Valkey key=f"metrics:{instance_id}:{hash}" TTL=60s

    async def get_latest(self, instance_id: UUID) -> MetricSnapshot:
        """최신 메트릭 스냅샷 (WebSocket fallback용)"""
        # Cache: Valkey key=f"latest:{instance_id}" TTL=5s

    async def ingest(self, instance_id: UUID, samples: list[MetricSample]) -> int:
        """Kafka 컨슈머가 호출. 배치 INSERT. 반환값=저장 건수"""
        # Transaction: 배치 INSERT, 실패 시 전체 롤백
```

### 2.3 ASHService

```python
# backend/app/services/ash_service.py
# Spec: SVC-001, FR-DASH-003

class ASHService:
    def __init__(self, db: AsyncSession): ...

    async def get_sessions(self, instance_id: UUID, from_time: datetime,
                           to_time: datetime, wait_event_type: str | None) -> list[ActiveSession]:
        """ASH 세션 조회 (시간 범위 + Wait Event 필터)"""

    async def get_heatmap(self, instance_id: UUID, from_time: datetime,
                          to_time: datetime, resolution: str = "1m") -> HeatmapData:
        """히트맵 데이터. resolution: 1s/10s/1m/1h"""
        # 반환: {categories: ["CPU","I/O","Lock","Network"], timestamps: [...], values: [[...]]}

    async def get_wait_breakdown(self, instance_id: UUID, from_time: datetime,
                                  to_time: datetime) -> list[WaitBreakdown]:
        """Wait Event 카테고리별 비율 집계"""
        # 반환: [{category: "Lock", percentage: 45.2, count: 1234}, ...]
```

### 2.4 IncidentService

```python
# backend/app/services/incident_service.py
# Spec: SVC-001, FR-AI-001, FR-AI-014

class IncidentService:
    def __init__(self, db: AsyncSession, kafka: KafkaProducer,
                 mtl_service: MTLService, rag_service: RAGService): ...

    async def list_all(self, severity: str | None, status: str | None,
                       cursor: str | None, limit: int = 20) -> PaginatedResult[IncidentResponse]:
        """인시던트 목록 (필터 + 페이지네이션)"""

    async def get(self, incident_id: UUID) -> IncidentDetailResponse:
        """인시던트 상세 + MTL 예측 결과 + Reasoning Chain"""

    async def create_from_anomaly(self, instance_id: UUID, anomaly: AnomalyDetection) -> Incident:
        """이상 탐지 → 인시던트 생성 → 경량 RCA 트리거"""
        # Transaction: incident INSERT + Kafka event + RCA trigger
        # 1. incident INSERT (commit)
        # 2. Kafka: neuraldb.incidents.created (비동기)
        # 3. Celery: trigger_mtl_rca.delay(incident_id) (비동기)

    async def update_status(self, incident_id: UUID, status: str, notes: str | None) -> Incident:
        """상태 변경 (open→investigating→resolved→closed)"""
```

### 2.5 MTLService

```python
# backend/app/services/mtl_service.py
# Spec: SVC-001, FS-AI-010, FS-AI-011

class MTLService:
    def __init__(self, db: AsyncSession, llm: LLMClient,
                 rag_service: RAGService, settings: Settings): ...

    async def predict(self, incident_id: UUID) -> MTLPrediction:
        """MTL 4-Head 동시 추론 (경량 RCA)"""
        # 1. Context Builder: 메트릭+ASH+쿼리+RAG 조합
        # 2. LLM 호출 (MTL Lite 프롬프트)
        # 3. JSON 파싱 + Confidence Score 계산
        # 4. mtl_predictions + reasoning_chains + evidence_links INSERT
        # Transaction: 3개 테이블 단일 트랜잭션

    async def submit_feedback(self, prediction_id: UUID, feedback: MTLFeedbackRequest) -> None:
        """운영자 피드백 저장"""
        # Transaction: UPDATE mtl_predictions.feedback_*

    async def get_prediction(self, prediction_id: UUID) -> MTLPredictResponse:
        """예측 결과 + Reasoning Chain + Evidence Links 조회"""

    async def get_confidence_stats(self, instance_id: UUID | None,
                                    from_time: datetime, to_time: datetime) -> ConfidenceStatsResponse:
        """Confidence 통계 집계"""
```

### 2.6 RAGService

```python
# backend/app/services/rag_service.py
# Spec: SVC-001, FS-AI-RAG-001

class RAGService:
    def __init__(self, db: AsyncSession, cache: ValkeyCli, embedding_model): ...

    async def embed_incident(self, incident_id: UUID) -> UUID:
        """인시던트 → sentence-transformers 임베딩 → pgvector 저장"""
        # Transaction: rag_documents UPSERT

    async def search_similar(self, query: str, instance_id: UUID | None,
                              top_k: int = 3, min_similarity: float = 0.7) -> list[RAGSearchResult]:
        """pgvector cosine similarity 검색"""
        # Cache: Valkey key=f"rag:{hash(query+instance_id)}" TTL=300s

    async def get_status(self) -> RAGStatusResponse:
        """임베딩 현황 조회"""
```

### 2.7 NL2SQLService

```python
# backend/app/services/nl2sql_service.py
# Spec: SVC-001, FR-AI-003

class NL2SQLService:
    def __init__(self, db: AsyncSession, llm: LLMClient): ...

    async def query(self, question: str, instance_id: UUID) -> NL2SQLResponse:
        """자연어 → SQL 변환 → 읽기전용 실행 → 결과"""
        # 1. LangChain SQL Agent로 SQL 생성
        # 2. 쓰기 쿼리 차단 (INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE)
        # 3. statement_timeout 적용 후 실행
        # 4. 결과 + 생성된 SQL 반환
        # Transaction: 읽기 전용 (READ ONLY)
```

### 2.8 AlertService

```python
# backend/app/services/alert_service.py
# Spec: SVC-001, FR-ALERT-001

class AlertService:
    def __init__(self, db: AsyncSession, slack: SlackClient, settings: Settings): ...

    async def dispatch(self, incident: Incident, prediction: MTLPrediction | None) -> None:
        """인시던트 → Slack/Webhook 알림 발송"""
        # Throttle: 동일 인스턴스 5분 쿨다운

    async def list_channels(self) -> list[AlertChannel]: ...
    async def create_channel(self, data: AlertChannelCreate) -> AlertChannel: ...
    async def test_channel(self, channel_id: UUID) -> bool: ...
```

### 2.9 AuthService

```python
# backend/app/services/auth_service.py
# Spec: SVC-001, FR-ADMIN-001

class AuthService:
    def __init__(self, db: AsyncSession, settings: Settings): ...

    async def login(self, email: str, password: str) -> TokenPair:
        """이메일/비밀번호 → JWT Access + Refresh Token"""

    async def refresh(self, refresh_token: str) -> TokenPair:
        """Refresh Token → 새 Access + Refresh Token"""

    async def get_current_user(self, token: str) -> User:
        """JWT → User 조회. 만료/무효 시 AUTH_TOKEN_* 에러"""

    async def create_user(self, data: UserCreate) -> User: ...
    async def update_user(self, user_id: UUID, data: UserUpdate) -> User: ...
    async def delete_user(self, user_id: UUID) -> None: ...
```

### 2.10 AuditService

```python
# backend/app/services/audit_service.py
# Spec: SVC-001, FR-ADMIN-003

class AuditService:
    def __init__(self, db: AsyncSession): ...

    async def log(self, user_id: UUID, action: str, resource_type: str,
                  resource_id: UUID | None, details: dict) -> None:
        """감사 로그 기록 (WHO/WHAT/WHEN/WHERE/WHY)"""
        # Transaction: 항상 별도 트랜잭션 (메인 작업 실패 시에도 로그 유지)

    async def list_logs(self, from_time: datetime, to_time: datetime,
                        user_id: UUID | None, action: str | None,
                        cursor: str | None, limit: int = 50) -> PaginatedResult[AuditLog]: ...
```

---

## 3. 트랜잭션 경계 정책

| 시나리오 | 트랜잭션 범위 | 실패 시 |
|---------|-------------|--------|
| 인시던트 생성 + RCA 트리거 | incident INSERT 단일 커밋, RCA는 비동기 | incident 롤백, RCA 미실행 |
| MTL 예측 저장 (3테이블) | prediction + reasoning + evidence 단일 트랜잭션 | 전체 롤백 |
| 메트릭 배치 INSERT | 배치 단위 트랜잭션 (1000건) | 해당 배치 롤백, 다음 배치 계속 |
| 감사 로그 | 항상 별도 트랜잭션 | 메인 작업과 독립 |
| 사용자 CRUD | 단일 트랜잭션 | 롤백 |

---

## 4. 캐싱 전략

| 키 패턴 | TTL | 무효화 조건 |
|---------|-----|-----------|
| `latest:{instance_id}` | 5s | 새 메트릭 수집 시 |
| `metrics:{instance_id}:{hash}` | 60s | 자연 만료 |
| `baseline:{instance_id}:{metric}` | 6h | 재학습 시 |
| `rag:search:{hash}` | 300s | 인시던트 생성/갱신 시 |
| `incidents:list:{hash}` | 30s | 인시던트 생성/상태변경 시 |

---

## 5. 인수 기준

- [ ] AC-1: 모든 서비스가 `Depends()` 로 FastAPI 라우트에 주입 가능
- [ ] AC-2: 트랜잭션 경계 정책에 따라 롤백 동작 확인
- [ ] AC-3: Valkey 캐시 적중 시 DB 쿼리 미실행 확인
- [ ] AC-4: 감사 로그가 메인 작업 실패 시에도 기록됨
