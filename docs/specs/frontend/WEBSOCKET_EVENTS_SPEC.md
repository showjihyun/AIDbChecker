# WebSocket Events Spec

> **Spec ID**: FE-WS-001
> **PRD 참조**: FR-DASH-001 (실시간 메트릭), FR-AI-010 (인시던트 알림)
> **상태**: Approved
> **API 참조**: API_SPEC.md 16절 WebSocket Namespaces
> **훅 참조**: REACT_HOOKS_SPEC.md 3절 WebSocket 훅

---

## 1. 인증

### 1.1 Handshake

Socket.io 클라이언트 연결 시 `auth` 파라미터로 JWT Access Token을 전달한다.

```typescript
import { io } from 'socket.io-client';

const socket = io('/ws/metrics', {
  auth: {
    token: `Bearer ${accessToken}`,
  },
  transports: ['websocket'],  // long-polling fallback 비활성화
  autoConnect: false,
});

socket.connect();
```

### 1.2 서버 측 인증 미들웨어

```python
# backend/app/ws/middleware.py
# Spec: FE-WS-001

async def authenticate_socket(socket, data):
    """Socket.io 연결 시 JWT 검증"""
    token = data.get("auth", {}).get("token", "")
    if not token.startswith("Bearer "):
        raise ConnectionRefusedError("Missing token")

    payload = verify_jwt(token.replace("Bearer ", ""))
    if not payload:
        raise ConnectionRefusedError("Invalid token")

    socket.user = payload  # { user_id, role, exp }
    return True
```

### 1.3 토큰 만료 처리

| 이벤트 | 방향 | 트리거 | 클라이언트 동작 |
|--------|------|--------|----------------|
| `auth:expired` | Server → Client | JWT exp 도달 시 | disconnect → refresh token → reconnect |

```typescript
// 클라이언트 측 처리
socket.on('auth:expired', () => {
  socket.disconnect();

  // 토큰 갱신 시도
  const refreshToken = useAuthStore.getState().refreshToken;
  api.post('/auth/refresh', { refresh_token: refreshToken })
    .then(({ access_token }) => {
      useAuthStore.getState().setToken(access_token);
      socket.auth = { token: `Bearer ${access_token}` };
      socket.connect();
    })
    .catch(() => {
      useAuthStore.getState().logout();
      window.location.href = '/login';
    });
});
```

### 1.4 RBAC 권한

| Role | /ws/metrics | /ws/incidents | /ws/system |
|------|------------|---------------|------------|
| Viewer | Subscribe (read only) | Subscribe (read only) | --- |
| Operator | Subscribe (read only) | Subscribe + incident actions | --- |
| DB Admin | Subscribe (read only) | Subscribe + incident actions | --- |
| Super Admin | Subscribe (read only) | Subscribe + incident actions | Subscribe |

---

## 2. Namespaces & Rooms

### 2.1 Namespace 구조

| Namespace | 용도 | Room Pattern | Join 조건 |
|-----------|------|-------------|-----------|
| `/ws/metrics` | 실시간 메트릭 스트림 | `instance:{instanceId}` | Auth + 해당 인스턴스 접근 권한 |
| `/ws/incidents` | 인시던트 실시간 알림 | `global` | Auth (모든 인증 사용자) |
| `/ws/system` | 시스템 헬스 모니터링 | `global` | Auth + Super Admin 역할 |

### 2.2 Room Join / Leave

```typescript
// 클라이언트: Room 참여
socket.emit('join', { room: `instance:${instanceId}` });

// 클라이언트: Room 이탈
socket.emit('leave', { room: `instance:${instanceId}` });
```

```python
# 서버: Room 관리
# backend/app/ws/handlers.py

@sio.on('join', namespace='/ws/metrics')
async def handle_join(sid, data):
    room = data.get('room')
    # 권한 검증: 해당 instance에 접근 가능한지 확인
    instance_id = room.replace('instance:', '')
    if not await can_access_instance(sio.get_session(sid)['user'], instance_id):
        await sio.emit('error', {'message': 'Access denied'}, to=sid)
        return
    await sio.enter_room(sid, room, namespace='/ws/metrics')

@sio.on('leave', namespace='/ws/metrics')
async def handle_leave(sid, data):
    room = data.get('room')
    await sio.leave_room(sid, room, namespace='/ws/metrics')
```

---

## 3. Event Payloads

### 3.1 metric:update

> **Namespace**: `/ws/metrics`
> **Room**: `instance:{instanceId}`
> **방향**: Server → Client
> **발생 주기**: 1초 (Celery collect_hot_metrics 완료 시)

```typescript
// src/types/ws.ts

interface MetricUpdateEvent {
  /** 대상 인스턴스 ID */
  instance_id: string;
  /** 샘플링 시각 (ISO8601) */
  sampled_at: string;
  /** 메트릭 값 */
  metrics: {
    /** CPU 사용률 (0.0 ~ 1.0) */
    cpu_usage: number;
    /** 메모리 사용률 (0.0 ~ 1.0) */
    memory_usage: number;
    /** 활성 커넥션 수 */
    active_connections: number;
    /** 초당 트랜잭션 수 */
    tps: number;
    /** 버퍼 캐시 히트율 (0.0 ~ 1.0) */
    buffer_hit_ratio: number;
  };
}
```

```python
# 서버 측 Emit 예시
# backend/app/services/metric_service.py

async def ingest_hot_metrics(instance_id: str, metrics: dict):
    """Hot 메트릭 저장 후 WebSocket 브로드캐스트"""
    # 1. DB 저장
    await metric_repo.insert(instance_id, metrics)

    # 2. WebSocket 브로드캐스트
    await sio.emit(
        'metric:update',
        MetricUpdateEvent(
            instance_id=instance_id,
            sampled_at=datetime.utcnow().isoformat() + 'Z',
            metrics=metrics,
        ).dict(),
        room=f'instance:{instance_id}',
        namespace='/ws/metrics',
    )
```

### 3.2 metric:spike

> **Namespace**: `/ws/metrics`
> **Room**: `instance:{instanceId}`
> **방향**: Server → Client
> **발생 조건**: 메트릭이 베이스라인 대비 3-sigma 초과 시

```typescript
interface MetricSpikeEvent {
  /** 대상 인스턴스 ID */
  instance_id: string;
  /** 스파이크 감지 시각 */
  detected_at: string;
  /** 스파이크 메트릭 이름 */
  metric_name: string;
  /** 현재 값 */
  current_value: number;
  /** 베이스라인 값 */
  baseline_value: number;
  /** 편차 배수 (e.g., 3.2 = 3.2-sigma) */
  deviation_factor: number;
  /** 심각도 */
  severity: SeverityLevel;
}
```

### 3.3 incident:new

> **Namespace**: `/ws/incidents`
> **Room**: `global`
> **방향**: Server → Client
> **발생 조건**: IncidentService.create_from_anomaly() 호출 시

```typescript
interface IncidentNewEvent {
  incident: {
    /** 인시던트 ID */
    id: string;
    /** 발생 인스턴스 ID */
    instance_id: string;
    /** 인스턴스 이름 */
    instance_name: string;
    /** 심각도 */
    severity: SeverityLevel;
    /** 인시던트 제목 */
    title: string;
    /** 인시던트 설명 */
    description: string;
    /** 감지 시각 */
    detected_at: string;
    /** MTL 예측 (있는 경우) */
    prediction?: {
      /** 이상 유형 */
      anomaly_type: string;
      /** 근본 원인 */
      root_cause: string;
      /** 신뢰도 (0.0 ~ 1.0) */
      confidence: number;
    };
  };
}
```

```python
# 서버 측 Emit 트리거
# backend/app/services/incident_service.py

async def create_from_anomaly(anomaly: AnomalyDetection):
    """이상 감지 → 인시던트 생성 → WebSocket 알림 + Alert 발송"""
    # 1. 인시던트 DB 저장
    incident = await incident_repo.create(anomaly)

    # 2. MTL RCA 비동기 실행 (Celery)
    prediction_task = trigger_mtl_rca.delay(str(incident.id))

    # 3. WebSocket 브로드캐스트
    await sio.emit(
        'incident:new',
        IncidentNewEvent(incident=incident).dict(),
        namespace='/ws/incidents',
    )

    # 4. Alert 비동기 발송 (Celery)
    dispatch_alert.delay(str(incident.id), None)
```

### 3.4 incident:update

> **Namespace**: `/ws/incidents`
> **Room**: `global`
> **방향**: Server → Client
> **발생 조건**: IncidentService.update_status() 호출 시

```typescript
interface IncidentUpdateEvent {
  /** 인시던트 ID */
  incident_id: string;
  /** 변경된 상태 */
  status: IncidentStatus;
  /** 변경 시각 */
  updated_at: string;
  /** 변경자 (사용자 이름 또는 "system") */
  updated_by: string;
}
```

```python
# 서버 측 Emit 트리거
# backend/app/services/incident_service.py

async def update_status(incident_id: str, new_status: str, user: User):
    """인시던트 상태 변경 → WebSocket 알림"""
    await incident_repo.update_status(incident_id, new_status, user.id)

    await sio.emit(
        'incident:update',
        IncidentUpdateEvent(
            incident_id=incident_id,
            status=new_status,
            updated_at=datetime.utcnow().isoformat() + 'Z',
            updated_by=user.name,
        ).dict(),
        namespace='/ws/incidents',
    )
```

### 3.5 system:health

> **Namespace**: `/ws/system`
> **Room**: `global`
> **방향**: Server → Client
> **발생 주기**: 10초마다 (FastAPI BackgroundTask)
> **접근 권한**: Super Admin only

```typescript
interface SystemHealthEvent {
  /** 컴포넌트별 상태 */
  components: {
    /** PostgreSQL 메타 DB */
    postgres: 'up' | 'down';
    /** Valkey 캐시 */
    valkey: 'up' | 'down';
    /** Kafka 메시지 브로커 */
    kafka: 'up' | 'down';
    /** Celery 활성 워커 수 */
    celery_workers: number;
    /** Celery Beat 스케줄러 */
    celery_beat: 'up' | 'down';
  };
  /** 타임스탬프 (ISO8601) */
  timestamp: string;
}
```

```python
# 서버 측 주기적 Emit
# backend/app/services/health_service.py

async def broadcast_system_health():
    """10초마다 시스템 헬스를 WebSocket으로 브로드캐스트"""
    health = await check_all_components()

    await sio.emit(
        'system:health',
        SystemHealthEvent(
            components={
                'postgres': 'up' if health.postgres_ok else 'down',
                'valkey': 'up' if health.valkey_ok else 'down',
                'kafka': 'up' if health.kafka_ok else 'down',
                'celery_workers': health.active_worker_count,
                'celery_beat': 'up' if health.beat_ok else 'down',
            },
            timestamp=datetime.utcnow().isoformat() + 'Z',
        ).dict(),
        namespace='/ws/system',
    )
```

---

## 4. Reconnection Policy

### 4.1 자동 재연결 설정

```typescript
// src/lib/socket.ts

const RECONNECTION_CONFIG = {
  /** 초기 재연결 대기 시간 (ms) */
  reconnectionDelay: 1_000,
  /** 최대 재연결 대기 시간 (ms) */
  reconnectionDelayMax: 30_000,
  /** 백오프 승수 */
  reconnectionDelayMultiplier: 2,
  /** 최대 재연결 시도 횟수 */
  reconnectionAttempts: 10,
  /** 자동 재연결 활성화 */
  reconnection: true,
};

// 재연결 지연 시간 계산:
//   attempt 1: 1,000ms
//   attempt 2: 2,000ms
//   attempt 3: 4,000ms
//   attempt 4: 8,000ms
//   attempt 5: 16,000ms
//   attempt 6: 30,000ms (max)
//   ...
//   attempt 10: 30,000ms → 실패 → 수동 재시도 모드
```

### 4.2 재연결 실패 시 UI 처리

```typescript
// 최대 시도 횟수 초과 시
socket.on('reconnect_failed', () => {
  // 1. "Connection lost" 배너 표시 (화면 상단 고정)
  //    - 배경: bg-error/90
  //    - 텍스트: "실시간 연결이 끊어졌습니다"
  //    - 버튼: "재연결" (수동 retry)

  // 2. 폴링 모드로 전환
  //    - useMetricsLatest의 refetchInterval 활성화 (5초)
  //    - useIncidents의 refetchInterval 활성화 (10초)
});

// 수동 재시도 버튼
function handleManualRetry() {
  socket.connect();
  // 재연결 시도 횟수 초기화
}
```

### 4.3 연결 상태 이벤트

| Socket.io 이벤트 | UI 동작 |
|------------------|---------|
| `connect` | 연결 배너 숨김, 폴링 중지, 쿼리 캐시 갱신 |
| `disconnect` | 연결 배너 표시 (자동 재연결 중) |
| `reconnect_attempt` | 배너에 "재연결 중... (N/10)" 표시 |
| `reconnect` | 연결 배너 숨김, room 재참여, 캐시 invalidate |
| `reconnect_failed` | "연결 끊김" 배너 + 수동 재시도 버튼 |
| `auth:expired` | disconnect → refresh → reconnect |
| `error` | 콘솔 로그 + Toast 알림 |

---

## 5. Server-side Emit Triggers

### 5.1 트리거 매핑

| Event | Trigger Condition | Service | Celery Task |
|-------|-------------------|---------|-------------|
| `metric:update` | Celery `collect_hot_metrics` 완료 | `MetricService.ingest()` | `collect_hot_metrics` |
| `metric:spike` | 메트릭 3-sigma 초과 감지 | `AnomalyDetector.check()` | `detect_anomalies` |
| `incident:new` | 이상 감지 → 인시던트 생성 | `IncidentService.create_from_anomaly()` | `detect_anomalies` |
| `incident:update` | 운영자 상태 변경 / 자동 해결 | `IncidentService.update_status()` | (API 직접 호출) |
| `system:health` | 10초 주기 BackgroundTask | `HealthService.broadcast()` | (FastAPI 내장) |

### 5.2 Emit 흐름도

```
[Celery Worker: metrics queue]
    │
    ├─ collect_hot_metrics (1초)
    │   └─ MetricService.ingest()
    │       └─ sio.emit("metric:update", room="instance:{id}")
    │
    ├─ detect_anomalies (10초)
    │   ├─ AnomalyDetector.check()
    │   │   └─ sio.emit("metric:spike", room="instance:{id}")  [조건부]
    │   └─ IncidentService.create_from_anomaly()
    │       └─ sio.emit("incident:new", namespace="/ws/incidents")
    │
[FastAPI BackgroundTask]
    │
    └─ HealthService.broadcast() (10초)
        └─ sio.emit("system:health", namespace="/ws/system")

[API Endpoint]
    │
    └─ PUT /incidents/{id}/status
        └─ IncidentService.update_status()
            └─ sio.emit("incident:update", namespace="/ws/incidents")
```

---

## 6. 메시지 직렬화

### 6.1 직렬화 포맷

| 항목 | 값 |
|------|---|
| 프로토콜 | Socket.io v4 (Engine.IO v4) |
| 전송 방식 | WebSocket only (no long-polling) |
| 직렬화 | JSON |
| 날짜 포맷 | ISO 8601 UTC (e.g., `2026-03-21T14:32:00Z`) |
| ID 포맷 | UUID v4 |
| 숫자 | IEEE 754 double precision |

### 6.2 메시지 크기 제한

| 항목 | 값 |
|------|---|
| maxHttpBufferSize | 1MB (기본값) |
| metric:update 평균 크기 | ~200 bytes |
| incident:new 평균 크기 | ~800 bytes |
| system:health 평균 크기 | ~300 bytes |

---

## 7. 에러 처리

### 7.1 서버 측 에러 이벤트

```typescript
interface WSErrorEvent {
  /** 에러 코드 */
  code: 'AUTH_EXPIRED' | 'ACCESS_DENIED' | 'ROOM_NOT_FOUND' | 'RATE_LIMIT' | 'INTERNAL';
  /** 에러 메시지 */
  message: string;
  /** 타임스탬프 */
  timestamp: string;
}
```

### 7.2 에러 코드별 처리

| Code | HTTP equiv. | 클라이언트 동작 |
|------|------------|----------------|
| `AUTH_EXPIRED` | 401 | refresh token → reconnect |
| `ACCESS_DENIED` | 403 | Toast 경고 + room leave |
| `ROOM_NOT_FOUND` | 404 | 무시 (인스턴스 삭제됨) |
| `RATE_LIMIT` | 429 | 10초 대기 후 재시도 |
| `INTERNAL` | 500 | 콘솔 에러 로그 |

---

## 8. Rate Limiting

| Namespace | 제한 | 설명 |
|-----------|------|------|
| `/ws/metrics` | N/A (서버 push only) | 클라이언트는 join/leave만 가능 |
| `/ws/incidents` | N/A (서버 push only) | 클라이언트는 구독만 가능 |
| `/ws/system` | N/A (서버 push only) | 클라이언트는 구독만 가능 |
| join/leave 이벤트 | 10 req/sec per client | 과도한 room 전환 방지 |

---

## 9. 모니터링 메트릭

> Prometheus로 수집하여 NeuralDB 자체 모니터링 대시보드에 표시

| 메트릭 | 타입 | 설명 |
|--------|------|------|
| `ws_connections_active` | Gauge | 현재 활성 WebSocket 연결 수 |
| `ws_connections_total` | Counter | 누적 연결 수 |
| `ws_messages_sent_total` | Counter | 서버 → 클라이언트 메시지 발송 수 (event별 label) |
| `ws_rooms_active` | Gauge | 현재 활성 room 수 |
| `ws_auth_failures_total` | Counter | 인증 실패 수 |
| `ws_reconnections_total` | Counter | 재연결 수 |

---

## 10. 인수 기준

| ID | 기준 | 검증 방법 |
|----|------|----------|
| AC-1 | JWT 인증 없이 WebSocket 연결 시 거부된다 | 통합 테스트: 토큰 없이 연결 → ConnectionRefused |
| AC-2 | metric:update 이벤트가 1초 간격으로 해당 room에만 전달된다 | E2E 테스트: 2개 인스턴스 구독, 각각 자기 메트릭만 수신 확인 |
| AC-3 | incident:new 이벤트 수신 시 프론트엔드 인시던트 목록이 자동 갱신된다 | E2E 테스트: 서버에서 emit → 클라이언트 useIncidents 캐시 갱신 확인 |
| AC-4 | 재연결 정책이 지수 백오프(1s, 2s, 4s, ..., 30s max)를 따른다 | 단위 테스트: disconnect 후 reconnect_attempt 타이밍 측정 |
| AC-5 | 최대 재연결 시도(10회) 초과 시 "Connection lost" 배너가 표시된다 | E2E 테스트: 서버 down → 10회 실패 → UI 배너 확인 |
| AC-6 | Super Admin이 아닌 사용자가 /ws/system 연결 시 ACCESS_DENIED 에러를 받는다 | 통합 테스트: Viewer 토큰으로 /ws/system 연결 → 거부 확인 |
| AC-7 | 토큰 만료 시 auth:expired → refresh → reconnect 흐름이 동작한다 | 통합 테스트: 만료 토큰 시뮬레이션 → 갱신 후 재연결 확인 |
