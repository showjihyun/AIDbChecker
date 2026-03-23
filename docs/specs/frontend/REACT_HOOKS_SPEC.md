# React Hooks Spec: 커스텀 훅 인터페이스

> **Spec ID**: FE-HOOK-001
> **PRD 참조**: FR-DASH-001~005, FR-AI-001~014
> **상태**: Approved
> **API 참조**: API_SPEC.md (API-001)
> **컴포넌트 참조**: COMPONENT_SPEC.md (FE-COMP-001)

---

## 1. TanStack Query 훅

> **라이브러리**: `@tanstack/react-query` v5
> **QueryClient 기본 설정**:
> ```typescript
> const queryClient = new QueryClient({
>   defaultOptions: {
>     queries: {
>       retry: 2,
>       retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10000),
>       refetchOnWindowFocus: false,
>       gcTime: 5 * 60 * 1000,  // 5분
>     },
>   },
> });
> ```

### 1.1 Instance Hooks

#### useInstances

```typescript
// src/hooks/useInstances.ts

interface UseInstancesParams {
  cursor?: string;
  environment?: Environment;
  status?: InstanceStatus;
  pageSize?: number;  // 기본: 20
}

function useInstances(params?: UseInstancesParams) {
  return useQuery({
    queryKey: ['instances', params?.cursor, params?.environment, params?.status],
    queryFn: () => api.get<PaginatedResponse<Instance>>('/instances', { params }),
    staleTime: 30_000,       // 30초 — 인스턴스 목록은 자주 변경되지 않음
    refetchInterval: false,  // 수동 갱신
  });
}
```

#### useInstance

```typescript
// src/hooks/useInstance.ts

function useInstance(id: UUID) {
  return useQuery({
    queryKey: ['instances', id],
    queryFn: () => api.get<InstanceDetail>(`/instances/${id}`),
    staleTime: 30_000,
    enabled: !!id,  // id가 있을 때만 실행
  });
}
```

### 1.2 Metric Hooks

#### useMetrics

```typescript
// src/hooks/useMetrics.ts

interface UseMetricsParams {
  instanceId: UUID;
  from: ISO8601;
  to: ISO8601;
  category?: MetricCategory;
  resolution?: Resolution;
}

function useMetrics(params: UseMetricsParams) {
  return useQuery({
    queryKey: ['metrics', params.instanceId, params.from, params.to, params.category, params.resolution],
    queryFn: () => api.get<PaginatedResponse<MetricSample>>(
      `/instances/${params.instanceId}/metrics`,
      { params: { from: params.from, to: params.to, category: params.category, resolution: params.resolution } }
    ),
    staleTime: 10_000,       // 10초 — 메트릭은 빈번히 갱신됨
    refetchInterval: false,  // WebSocket으로 실시간 갱신
    enabled: !!params.instanceId,
  });
}
```

#### useMetricsLatest

```typescript
// src/hooks/useMetricsLatest.ts

function useMetricsLatest(instanceId: UUID) {
  return useQuery({
    queryKey: ['metrics-latest', instanceId],
    queryFn: () => api.get<MetricSnapshot>(`/instances/${instanceId}/metrics/latest`),
    staleTime: 5_000,         // 5초
    refetchInterval: 5_000,   // 5초마다 폴링 (WebSocket 미연결 시 폴백)
    enabled: !!instanceId,
  });
}
```

### 1.3 ASH Hooks

#### useASH

```typescript
// src/hooks/useASH.ts

interface UseASHParams {
  instanceId: UUID;
  from: ISO8601;
  to: ISO8601;
}

function useASH(params: UseASHParams) {
  return useQuery({
    queryKey: ['ash', params.instanceId, params.from, params.to],
    queryFn: () => api.get<PaginatedResponse<ActiveSession>>(
      `/instances/${params.instanceId}/ash`,
      { params: { from: params.from, to: params.to } }
    ),
    staleTime: 5_000,
    enabled: !!params.instanceId,
  });
}
```

#### useASHHeatmap

```typescript
// src/hooks/useASHHeatmap.ts

interface UseASHHeatmapParams {
  instanceId: UUID;
  from: ISO8601;
  to: ISO8601;
  resolution: Resolution;
}

function useASHHeatmap(params: UseASHHeatmapParams) {
  return useQuery({
    queryKey: ['ash-heatmap', params.instanceId, params.from, params.to, params.resolution],
    queryFn: () => api.get<HeatmapData>(
      `/instances/${params.instanceId}/ash/heatmap`,
      { params: { from: params.from, to: params.to, resolution: params.resolution } }
    ),
    staleTime: 5_000,
    enabled: !!params.instanceId,
  });
}
```

#### useWaitBreakdown

```typescript
// src/hooks/useWaitBreakdown.ts

function useWaitBreakdown(instanceId: UUID, from: ISO8601, to: ISO8601) {
  return useQuery({
    queryKey: ['wait-breakdown', instanceId, from, to],
    queryFn: () => api.get<WaitBreakdown[]>(
      `/instances/${instanceId}/ash/wait-breakdown`,
      { params: { from, to } }
    ),
    staleTime: 10_000,
    enabled: !!instanceId,
  });
}
```

### 1.4 Incident Hooks

#### useIncidents

```typescript
// src/hooks/useIncidents.ts

interface UseIncidentsParams {
  severity?: SeverityLevel;
  status?: IncidentStatus;
  instanceId?: UUID;
  cursor?: string;
  pageSize?: number;  // 기본: 20
}

function useIncidents(params?: UseIncidentsParams) {
  return useQuery({
    queryKey: ['incidents', params?.severity, params?.status, params?.instanceId, params?.cursor],
    queryFn: () => api.get<PaginatedResponse<Incident>>('/incidents', { params }),
    staleTime: 10_000,       // 10초
    refetchInterval: false,  // WebSocket으로 실시간 갱신
  });
}
```

#### useIncident

```typescript
// src/hooks/useIncident.ts

function useIncident(id: UUID) {
  return useQuery({
    queryKey: ['incidents', id],
    queryFn: () => api.get<IncidentDetail>(`/incidents/${id}`),
    staleTime: 10_000,
    enabled: !!id,
  });
}
```

### 1.5 AI Hooks

#### useMTLPrediction

```typescript
// src/hooks/useMTLPrediction.ts

function useMTLPrediction(predictionId: UUID) {
  return useQuery({
    queryKey: ['mtl-prediction', predictionId],
    queryFn: () => api.get<MTLPrediction>(`/mtl/predictions/${predictionId}`),
    staleTime: 60_000,  // 1분 — AI 예측 결과는 변경이 드묾
    enabled: !!predictionId,
  });
}
```

#### useConfidenceStats

```typescript
// src/hooks/useConfidenceStats.ts

interface UseConfidenceStatsParams {
  instanceId?: UUID;
  from: ISO8601;
  to: ISO8601;
}

function useConfidenceStats(params: UseConfidenceStatsParams) {
  return useQuery({
    queryKey: ['confidence-stats', params.instanceId, params.from, params.to],
    queryFn: () => api.get<ConfidenceStats>('/confidence/stats', { params }),
    staleTime: 60_000,
    enabled: true,
  });
}

interface ConfidenceStats {
  total_predictions: number;
  avg_confidence: number;
  grade_distribution: Record<ConfidenceGrade, number>;
  trend_7d: { date: string; avg_confidence: number }[];
}
```

#### useRAGSearch (Mutation)

```typescript
// src/hooks/useRAGSearch.ts

interface RAGSearchRequest {
  query: string;
  instance_id?: UUID;
  top_k?: number;       // 기본: 5
  min_score?: number;    // 기본: 0.5
}

function useRAGSearch() {
  return useMutation({
    mutationFn: (request: RAGSearchRequest) =>
      api.post<RAGSearchResult>('/rag/search', request),
  });
}
```

#### useNL2SQL (Mutation)

```typescript
// src/hooks/useNL2SQL.ts

interface NL2SQLRequest {
  question: string;
  instance_id: UUID;
  execute?: boolean;  // 기본: true
}

function useNL2SQL() {
  return useMutation({
    mutationFn: (request: NL2SQLRequest) =>
      api.post<NL2SQLResponse>('/nl2sql/query', request),
  });
}
```

### 1.6 Baseline & Schema Hooks

#### useBaselines

```typescript
// src/hooks/useBaselines.ts

function useBaselines(instanceId: UUID) {
  return useQuery({
    queryKey: ['baselines', instanceId],
    queryFn: () => api.get<BaselineStatus>(`/instances/${instanceId}/baselines`),
    staleTime: 60_000,  // 1분
    enabled: !!instanceId,
  });
}
```

#### useSchemaChanges

```typescript
// src/hooks/useSchemaChanges.ts

function useSchemaChanges(instanceId: UUID) {
  return useQuery({
    queryKey: ['schema-changes', instanceId],
    queryFn: () => api.get<PaginatedResponse<SchemaChange>>(
      `/instances/${instanceId}/schema-changes`
    ),
    staleTime: 60_000,
    enabled: !!instanceId,
  });
}
```

### 1.7 Admin & System Hooks

#### useSystemHealth

```typescript
// src/hooks/useSystemHealth.ts

function useSystemHealth() {
  return useQuery({
    queryKey: ['system-health'],
    queryFn: () => api.get<SystemHealth>('/system/health'),
    staleTime: 5_000,
    refetchInterval: 10_000,  // 10초마다 자동 갱신 (시스템 헬스는 항상 최신 유지)
  });
}
```

#### useAuditLogs

```typescript
// src/hooks/useAuditLogs.ts

interface UseAuditLogsParams {
  from: ISO8601;
  to: ISO8601;
  userId?: UUID;
  action?: string;
  cursor?: string;
}

function useAuditLogs(params: UseAuditLogsParams) {
  return useQuery({
    queryKey: ['audit-logs', params.from, params.to, params.userId, params.action, params.cursor],
    queryFn: () => api.get<PaginatedResponse<AuditLog>>('/audit-logs', { params }),
    staleTime: 30_000,
  });
}
```

#### useUsers

```typescript
// src/hooks/useUsers.ts

function useUsers() {
  return useQuery({
    queryKey: ['users'],
    queryFn: () => api.get<PaginatedResponse<User>>('/users'),
    staleTime: 60_000,
  });
}
```

---

## 2. Mutation Hooks

> 모든 Mutation 훅은 성공 시 관련 쿼리를 무효화(invalidate)하여 UI를 자동 갱신한다.

### 2.1 Instance Mutations

```typescript
// src/hooks/mutations/useInstanceMutations.ts

function useCreateInstance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateInstanceRequest) =>
      api.post<InstanceDetail>('/instances', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['instances'] });
    },
  });
}

function useUpdateInstance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: UUID; data: Partial<CreateInstanceRequest> }) =>
      api.put<InstanceDetail>(`/instances/${id}`, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['instances', variables.id] });
      queryClient.invalidateQueries({ queryKey: ['instances'] });
    },
  });
}

function useDeleteInstance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => api.delete(`/instances/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['instances'] });
    },
  });
}
```

### 2.2 Incident Mutations

```typescript
// src/hooks/mutations/useIncidentMutations.ts

interface UpdateIncidentStatusRequest {
  status: IncidentStatus;
  comment?: string;
}

function useUpdateIncidentStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: UUID; data: UpdateIncidentStatusRequest }) =>
      api.put(`/incidents/${id}/status`, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['incidents', variables.id] });
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
    },
  });
}
```

### 2.3 AI Mutations

```typescript
// src/hooks/mutations/useAIMutations.ts

interface MTLFeedbackRequest {
  feedback: 'positive' | 'negative';
  comment?: string;
}

function useMTLFeedback() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: UUID; data: MTLFeedbackRequest }) =>
      api.post(`/mtl/predictions/${id}/feedback`, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['mtl-prediction', variables.id] });
    },
  });
}
```

### 2.4 Admin Mutations

```typescript
// src/hooks/mutations/useAdminMutations.ts

function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Omit<User, 'id' | 'last_login_at' | 'created_at'> & { password: string }) =>
      api.post<User>('/users', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
}

function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: UUID; data: Partial<User> }) =>
      api.put<User>(`/users/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
}

function useDeleteUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => api.delete(`/users/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
}

function useCreateAlertChannel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Omit<AlertChannel, 'id' | 'created_at'>) =>
      api.post<AlertChannel>('/alerts/channels', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alert-channels'] });
    },
  });
}

function useUpdateAlertChannel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: UUID; data: Partial<AlertChannel> }) =>
      api.put<AlertChannel>(`/alerts/channels/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alert-channels'] });
    },
  });
}
```

---

## 3. WebSocket 훅

> **라이브러리**: `socket.io-client` v4
> **인증**: JWT Bearer token을 handshake `auth` 파라미터로 전달
> **참조**: WEBSOCKET_EVENTS_SPEC.md (FE-WS-001)

### 3.1 useMetricStream

```typescript
// src/hooks/ws/useMetricStream.ts

interface UseMetricStreamReturn {
  /** 최신 메트릭 데이터 */
  latestMetric: MetricSnapshot | null;
  /** WebSocket 연결 상태 */
  isConnected: boolean;
  /** 재연결 시도 횟수 */
  reconnectCount: number;
}

function useMetricStream(instanceId: UUID): UseMetricStreamReturn {
  // 구현 상세:
  // 1. /ws/metrics 네임스페이스에 연결
  // 2. emit("join", { room: `instance:${instanceId}` })
  // 3. on("metric:update", (data: MetricUpdateEvent) => { ... })
  // 4. instanceId 변경 시: 이전 room leave → 새 room join
  // 5. 컴포넌트 언마운트 시: disconnect

  // 재연결 정책:
  //   reconnectionDelay: 3000     // 초기 3초
  //   reconnectionDelayMax: 30000 // 최대 30초
  //   reconnectionAttempts: 5     // 최대 5회
  //   backoff: exponential (delay * 2^attempt)

  // QueryClient 연동:
  //   수신 시 queryClient.setQueryData(['metrics-latest', instanceId], data) 업데이트
  //   → useMetricsLatest 자동 갱신 (refetchInterval 폴링 불필요해짐)
}
```

### 3.2 useIncidentStream

```typescript
// src/hooks/ws/useIncidentStream.ts

interface UseIncidentStreamReturn {
  /** 새 인시던트 목록 (세션 중 수신) */
  newIncidents: Incident[];
  /** 업데이트된 인시던트 목록 */
  updatedIncidents: { incident_id: UUID; status: IncidentStatus; updated_at: ISO8601 }[];
  /** WebSocket 연결 상태 */
  isConnected: boolean;
  /** 새 인시던트 수신 이후 카운트 (알림 뱃지 용) */
  unreadCount: number;
  /** 카운트 리셋 */
  resetUnread: () => void;
}

function useIncidentStream(): UseIncidentStreamReturn {
  // 구현 상세:
  // 1. /ws/incidents 네임스페이스에 연결 (global room)
  // 2. on("incident:new", (data: IncidentNewEvent) => { ... })
  //    → newIncidents 배열에 추가
  //    → unreadCount 증가
  //    → queryClient.invalidateQueries({ queryKey: ['incidents'] })
  //    → Toast 알림 표시 (severity >= WARNING)
  // 3. on("incident:update", (data: IncidentUpdateEvent) => { ... })
  //    → updatedIncidents 배열에 추가
  //    → queryClient.invalidateQueries({ queryKey: ['incidents', data.incident_id] })

  // 재연결 정책: useMetricStream과 동일
}
```

### 3.3 Socket Manager (싱글턴)

```typescript
// src/lib/socket.ts

import { io, Socket } from 'socket.io-client';

interface SocketManager {
  /** 네임스페이스별 소켓 인스턴스 가져오기 (lazy 연결) */
  getSocket(namespace: '/ws/metrics' | '/ws/incidents' | '/ws/system'): Socket;
  /** 전체 연결 해제 (로그아웃 시) */
  disconnectAll(): void;
  /** 토큰 갱신 */
  updateToken(newToken: string): void;
}

// 구현:
// - 네임스페이스별 Socket 인스턴스를 Map으로 관리
// - 첫 getSocket() 호출 시 lazy connect
// - auth: { token: `Bearer ${jwt}` }
// - transports: ['websocket']  (long-polling fallback 없음)
// - autoConnect: false  (수동 connect)
// - on("auth:expired") → useAuthStore.logout() → redirect to /login
```

---

## 4. Zustand 스토어

> **라이브러리**: `zustand` v4 + `immer` middleware
> **Persist**: 필요한 스토어만 `zustand/middleware/persist`로 localStorage 저장

### 4.1 useAuthStore

```typescript
// src/stores/authStore.ts

interface AuthState {
  /** 현재 사용자 */
  user: User | null;
  /** JWT Access Token */
  token: string | null;
  /** JWT Refresh Token */
  refreshToken: string | null;
  /** 사용자 역할 (캐시) */
  role: UserRole | null;
  /** 인증 여부 (token 존재 + 유효) */
  isAuthenticated: boolean;
}

interface AuthActions {
  /** 로그인 (JWT 저장 + 사용자 정보 설정) */
  login: (token: string, refreshToken: string, user: User) => void;
  /** 로그아웃 (상태 초기화 + Socket 연결 해제) */
  logout: () => void;
  /** 역할 확인 (계층형: super_admin > db_admin > operator > viewer) */
  hasRole: (requiredRole: UserRole) => boolean;
  /** 토큰 갱신 */
  setToken: (token: string) => void;
  /** 사용자 정보 갱신 */
  setUser: (user: User) => void;
}

type AuthStore = AuthState & AuthActions;

// Persist: localStorage (token, refreshToken만 저장)
// 역할 계층:
//   const ROLE_HIERARCHY: Record<UserRole, number> = {
//     viewer: 0,
//     operator: 1,
//     db_admin: 2,
//     super_admin: 3,
//   };
//   hasRole(required) → ROLE_HIERARCHY[role] >= ROLE_HIERARCHY[required]
```

### 4.2 useDashboardStore

```typescript
// src/stores/dashboardStore.ts

interface DashboardState {
  /** 선택된 인스턴스 ID */
  selectedInstanceId: UUID | null;
  /** 대시보드 시간 범위 */
  timeRange: TimeRange;
  /** 자동 갱신 활성화 여부 */
  autoRefresh: boolean;
  /** 갱신 주기 (ms) */
  refreshInterval: number;
}

interface DashboardActions {
  /** 인스턴스 선택 */
  setInstance: (instanceId: UUID | null) => void;
  /** 시간 범위 설정 */
  setTimeRange: (range: TimeRange) => void;
  /** 사전정의 범위 설정 (1h, 6h, 24h, 7d, 30d) */
  setPresetRange: (preset: '1h' | '6h' | '24h' | '7d' | '30d') => void;
  /** 자동 갱신 토글 */
  toggleAutoRefresh: () => void;
  /** 갱신 주기 변경 */
  setRefreshInterval: (ms: number) => void;
}

type DashboardStore = DashboardState & DashboardActions;

// 기본값:
//   selectedInstanceId: null
//   timeRange: { from: now - 1h, to: now }
//   autoRefresh: true
//   refreshInterval: 5000
// Persist: sessionStorage (탭 종료 시 초기화)
```

### 4.3 useASHStore

```typescript
// src/stores/ashStore.ts

interface ASHState {
  /** 선택된 인스턴스 ID */
  instanceId: UUID | null;
  /** 히트맵 시간 해상도 */
  resolution: Resolution;
  /** 선택된 히트맵 셀 */
  selectedCell: { time: ISO8601; category: string } | null;
  /** 시간 범위 */
  timeRange: TimeRange;
}

interface ASHActions {
  /** 인스턴스 설정 */
  setInstance: (instanceId: UUID) => void;
  /** 해상도 변경 */
  setResolution: (resolution: Resolution) => void;
  /** 셀 선택 (SessionTable 필터링 트리거) */
  selectCell: (time: ISO8601, category: string) => void;
  /** 셀 선택 해제 */
  clearCell: () => void;
  /** 시간 범위 설정 */
  setTimeRange: (range: TimeRange) => void;
}

type ASHStore = ASHState & ASHActions;

// 기본값:
//   instanceId: null
//   resolution: '1s'
//   selectedCell: null
//   timeRange: { from: now - 5m, to: now }
// Persist: 없음 (메모리 only)
```

### 4.4 useNL2SQLStore

```typescript
// src/stores/nl2sqlStore.ts

interface NL2SQLMessage {
  id: string;            // nanoid
  role: 'user' | 'ai' | 'error';
  content: string;
  sqlCode?: string;
  resultTable?: NL2SQLResult;
  timestamp: ISO8601;
}

interface NL2SQLState {
  /** 채팅창 열림 여부 */
  isOpen: boolean;
  /** 대화 메시지 목록 */
  messages: NL2SQLMessage[];
  /** 대상 인스턴스 ID */
  instanceId: UUID | null;
  /** 로딩 상태 (쿼리 생성 중) */
  isQuerying: boolean;
}

interface NL2SQLActions {
  /** 채팅창 토글 */
  toggle: () => void;
  /** 메시지 추가 */
  addMessage: (message: Omit<NL2SQLMessage, 'id' | 'timestamp'>) => void;
  /** 인스턴스 설정 */
  setInstance: (instanceId: UUID) => void;
  /** 로딩 상태 설정 */
  setQuerying: (isQuerying: boolean) => void;
  /** 대화 초기화 */
  clearMessages: () => void;
}

type NL2SQLStore = NL2SQLState & NL2SQLActions;

// 기본값:
//   isOpen: false
//   messages: []
//   instanceId: null
//   isQuerying: false
// Persist: 없음 (메모리 only)
```

---

## 5. API Client 설정

```typescript
// src/lib/api.ts

import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30_000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: JWT 토큰 주입
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: 401 → 토큰 갱신 → 재시도
api.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const refreshToken = useAuthStore.getState().refreshToken;
        const { data } = await axios.post('/api/v1/auth/refresh', { refresh_token: refreshToken });
        useAuthStore.getState().setToken(data.access_token);
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
        return api(originalRequest);
      } catch {
        useAuthStore.getState().logout();
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);
```

---

## 6. 훅 사용 규칙

| 규칙 | 설명 |
|------|------|
| Query Key 컨벤션 | `[entity, ...params]` 형식 (e.g., `['metrics', instanceId, from, to]`) |
| staleTime 기준 | Hot 데이터(메트릭): 5~10초, Warm 데이터(인시던트): 10~30초, Cold 데이터(사용자/설정): 60초 |
| refetchInterval | WebSocket 대체 가능 시 사용하지 않음, 시스템 헬스 등 폴링 필수 항목만 사용 |
| enabled 조건 | 필수 파라미터(instanceId 등)가 없으면 `enabled: false`로 불필요한 요청 방지 |
| Mutation 후 처리 | `onSuccess`에서 관련 쿼리 `invalidateQueries` 필수 |
| Error 처리 | 훅 레벨에서 처리하지 않음, 컴포넌트의 ErrorBoundary에 위임 |
| WebSocket 연동 | 수신 시 `queryClient.setQueryData()`로 캐시 직접 갱신, 폴링 대체 |

---

## 7. 인수 기준

| ID | 기준 | 검증 방법 |
|----|------|----------|
| AC-1 | 모든 TanStack Query 훅에 queryKey, queryFn, staleTime이 정의되어 있다 | 코드 리뷰 |
| AC-2 | 모든 Mutation 훅이 성공 시 관련 쿼리를 invalidate한다 | 단위 테스트 (msw mock) |
| AC-3 | WebSocket 훅이 재연결 정책(3초, 최대 5회, 지수 백오프)을 구현한다 | 통합 테스트 (ws disconnect 시나리오) |
| AC-4 | Zustand 스토어의 hasRole()이 계층형 RBAC를 올바르게 판단한다 | 단위 테스트 |
| AC-5 | API Client가 401 응답 시 토큰을 갱신하고 원래 요청을 재시도한다 | 통합 테스트 |
| AC-6 | WebSocket 수신 데이터가 TanStack Query 캐시를 올바르게 갱신한다 | E2E 테스트 |
