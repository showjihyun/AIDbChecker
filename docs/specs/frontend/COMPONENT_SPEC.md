# Component Spec: MVP React 컴포넌트 인터페이스

> **Spec ID**: FE-COMP-001
> **PRD 참조**: FR-DASH-001~005, FR-AI-011, FR-AI-014
> **상태**: Approved
> **디자인 참조**: FRONTEND_DESIGN.md
> **API 참조**: API_SPEC.md (API-001)

---

## 1. 공통 타입

```typescript
// src/types/common.ts

/** UUID v4 문자열 */
type UUID = string;

/** ISO 8601 날짜/시간 문자열 (e.g., "2026-03-21T14:32:00Z") */
type ISO8601 = string;

/** 인시던트 심각도 */
type SeverityLevel = 'CRITICAL' | 'WARNING' | 'NOTICE' | 'INFO';

/** AI 예측 신뢰도 등급 */
type ConfidenceGrade = 'HIGH' | 'MEDIUM' | 'LOW' | 'VERY_LOW';

/** DB 인스턴스 헬스 상태 */
type InstanceStatus = 'healthy' | 'warning' | 'critical' | 'offline' | 'learning';

/** 인시던트 처리 상태 */
type IncidentStatus = 'open' | 'investigating' | 'resolved' | 'closed';

/** DB 환경 구분 */
type Environment = 'production' | 'staging' | 'development' | 'dr';

/** 메트릭 카테고리 (Hot/Warm/Cold 계층) */
type MetricCategory = 'hot' | 'warm' | 'cold';

/** 시간 해상도 */
type Resolution = '1s' | '10s' | '1m' | '1h' | '1d' | 'auto';

/** 자율 등급 (1~5) */
type AutonomyLevel = 1 | 2 | 3 | 4 | 5;

/** RBAC 역할 */
type UserRole = 'viewer' | 'operator' | 'db_admin' | 'super_admin';

/** 알림 채널 종류 */
type AlertChannelType = 'slack' | 'email' | 'webhook';

/** 커서 기반 페이지네이션 응답 래퍼 */
interface PaginatedResponse<T> {
  items: T[];
  total: number;
  has_next: boolean;
  next_cursor?: string;
}

/** 트렌드 방향 */
type TrendDirection = 'up' | 'down' | 'flat';

/** 타임 범위 */
interface TimeRange {
  from: ISO8601;
  to: ISO8601;
}
```

---

## 2. API 응답 타입

```typescript
// src/types/api.ts

/** GET /api/v1/instances → items[] */
interface Instance {
  id: UUID;
  name: string;
  db_type: 'postgresql';
  host: string;
  port: number;
  environment: Environment;
  is_active: boolean;
  autonomy_level: AutonomyLevel;
  health_status: InstanceStatus;
  metadata: Record<string, unknown>;
}

/** GET /api/v1/instances/{id} */
interface InstanceDetail extends Instance {
  database_name: string;
  ssl_mode: 'disable' | 'require' | 'verify-ca' | 'verify-full';
  created_at: ISO8601;
  updated_at: ISO8601;
  last_collected_at: ISO8601 | null;
  baseline_status: BaselineStatus;
  tags: string[];
}

/** GET /api/v1/instances/{id}/metrics → items[] */
interface MetricSample {
  sampled_at: ISO8601;
  category: MetricCategory;
  metrics: Record<string, number>;
}

/** GET /api/v1/instances/{id}/metrics/latest */
interface MetricSnapshot {
  instance_id: UUID;
  sampled_at: ISO8601;
  cpu_usage: number;
  memory_usage: number;
  active_connections: number;
  tps: number;
  buffer_hit_ratio: number;
  replication_lag_ms: number | null;
  cache_hit_ratio: number;
  deadlocks: number;
  long_running_queries: number;
}

/** GET /api/v1/instances/{id}/ash → items[] */
interface ActiveSession {
  pid: number;
  query_snippet: string;
  state: 'active' | 'idle' | 'idle in transaction' | 'locked';
  wait_event_type: string | null;
  wait_event: string | null;
  duration_ms: number;
  database: string;
  username: string;
  application_name: string;
  client_addr: string;
  backend_start: ISO8601;
  query_start: ISO8601;
}

/** GET /api/v1/instances/{id}/ash/heatmap */
interface HeatmapData {
  time_range: TimeRange;
  resolution: Resolution;
  categories: string[];  // ["CPU", "I/O", "Lock", "Network"]
  data: HeatmapCell[];
}

interface HeatmapCell {
  time: ISO8601;
  [category: string]: number | string;  // CPU: 0.3, IO: 0.7, etc.
}

/** GET /api/v1/instances/{id}/ash/wait-breakdown */
interface WaitBreakdown {
  wait_event_type: string;
  wait_event: string;
  total_wait_ms: number;
  percentage: number;
  sample_count: number;
  color: string;  // hex color for chart
}

/** GET /api/v1/incidents → items[] */
interface Incident {
  id: UUID;
  instance_id: UUID;
  instance_name: string;
  severity: SeverityLevel;
  status: IncidentStatus;
  title: string;
  description: string;
  detected_at: ISO8601;
  resolved_at: ISO8601 | null;
  assigned_to: UUID | null;
  prediction_id: UUID | null;
}

/** GET /api/v1/incidents/{id} */
interface IncidentDetail extends Incident {
  timeline: IncidentTimelineEntry[];
  related_metrics: MetricSample[];
  rca: RCAResult | null;
}

interface IncidentTimelineEntry {
  timestamp: ISO8601;
  action: string;
  actor: string;
  details: string;
}

interface RCAResult {
  id: UUID;
  incident_id: UUID;
  root_cause: string;
  confidence: number;
  causal_chain: CausalChainNode[];
  recommendations: Recommendation[];
  ai_model: string;
  similar_incidents: SimilarIncident[];
}

interface CausalChainNode {
  node: string;
  type: 'trigger' | 'effect' | 'symptom';
  description: string;
}

interface Recommendation {
  action: string;
  description: string;
  risk_level: 'low' | 'medium' | 'high';
  estimated_impact: string;
  sql?: string;
}

interface SimilarIncident {
  id: UUID;
  title: string;
  similarity_score: number;
  resolved_at: ISO8601;
}

/** GET /api/v1/mtl/predictions/{id} */
interface MTLPrediction {
  id: UUID;
  incident_id: UUID;
  anomaly_type: string;
  root_cause: string;
  confidence: number;
  confidence_grade: ConfidenceGrade;
  reasoning_chain: ReasoningStep[];
  evidence_links: EvidenceLink[];
  recommendations: Recommendation[];
  ai_model: string;
  latency_ms: number;
  created_at: ISO8601;
  feedback: 'positive' | 'negative' | null;
}

/** Reasoning Chain 단계 */
interface ReasoningStep {
  step: number;
  title: string;
  description: string;
  evidence_ids: UUID[];
  confidence_contribution: number;
}

/** Evidence Link (XAI 근거) */
interface EvidenceLink {
  id: UUID;
  type: 'metric' | 'log' | 'schema_change' | 'similar_incident' | 'baseline';
  label: string;
  summary: string;
  source_url?: string;
  relevance_score: number;
}

/** POST /api/v1/rag/search → response */
interface RAGSearchResult {
  query: string;
  results: RAGDocument[];
  total: number;
  search_latency_ms: number;
}

interface RAGDocument {
  id: UUID;
  incident_id: UUID;
  title: string;
  content: string;
  similarity_score: number;
  created_at: ISO8601;
}

/** POST /api/v1/nl2sql/query → response */
interface NL2SQLResponse {
  natural_query: string;
  generated_sql: string;
  result: NL2SQLResult | null;
  ai_model: string;
  confidence: number;
  execution_time_ms: number;
}

interface NL2SQLResult {
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
}

/** GET /api/v1/instances/{id}/baselines */
interface BaselineStatus {
  instance_id: UUID;
  status: 'ready' | 'training' | 'insufficient_data' | 'stale';
  last_trained_at: ISO8601 | null;
  data_points: number;
  metrics_covered: string[];
  next_retrain_at: ISO8601;
}

/** GET /api/v1/instances/{id}/schema-changes → items[] */
interface SchemaChange {
  id: UUID;
  instance_id: UUID;
  change_type: 'CREATE' | 'ALTER' | 'DROP' | 'RENAME';
  object_type: 'TABLE' | 'INDEX' | 'COLUMN' | 'CONSTRAINT' | 'FUNCTION';
  object_name: string;
  ddl_statement: string;
  detected_at: ISO8601;
  detected_by: string;
  impact_score: number | null;
}

/** GET /api/v1/audit-logs → items[] */
interface AuditLog {
  id: UUID;
  user_id: UUID;
  user_email: string;
  action: string;
  resource_type: string;
  resource_id: UUID;
  details: Record<string, unknown>;
  ip_address: string;
  timestamp: ISO8601;
}

/** GET /api/v1/users → items[] */
interface User {
  id: UUID;
  email: string;
  name: string;
  role: UserRole;
  is_active: boolean;
  last_login_at: ISO8601 | null;
  created_at: ISO8601;
}

/** GET /api/v1/alerts/channels → items[] */
interface AlertChannel {
  id: UUID;
  name: string;
  type: AlertChannelType;
  config: SlackConfig | EmailConfig | WebhookConfig;
  is_enabled: boolean;
  created_at: ISO8601;
}

interface SlackConfig {
  webhook_url: string;
  channel: string;
  mention_on_critical: string[];
}

interface EmailConfig {
  recipients: string[];
  smtp_host: string;
  smtp_port: number;
}

interface WebhookConfig {
  url: string;
  method: 'POST' | 'PUT';
  headers: Record<string, string>;
  secret?: string;
}

/** GET /api/v1/system/health */
interface SystemHealth {
  status: 'healthy' | 'degraded' | 'down';
  uptime_seconds: number;
  version: string;
  components: {
    database: ComponentHealth;
    valkey: ComponentHealth;
    celery: CeleryHealth;
  };
}

interface ComponentHealth {
  status: 'healthy' | 'degraded' | 'down';
  latency_ms: number;
}

interface CeleryHealth {
  status: 'healthy' | 'degraded' | 'down';
  active_workers: number;
  queued_tasks: number;
}
```

---

## 3. 컴포넌트 Props 인터페이스

### 3.1 SummaryCard

> **위치**: `src/components/dashboard/SummaryCard.tsx`
> **디자인 참조**: FRONTEND_DESIGN.md 4.1 Summary Cards

```typescript
interface SummaryCardProps {
  /** 카드 라벨 (e.g., "Total Instances") */
  label: string;
  /** 표시 값 (e.g., "52", "12ms") */
  value: string | number;
  /** Material Symbols 아이콘명 (e.g., "dns", "group", "warning", "timer") */
  icon: string;
  /** 좌측 보더 색상 변형 */
  borderVariant: 'primary' | 'primary-container' | 'error' | 'tertiary' | 'secondary';
  /** 트렌드 정보 (선택) */
  trend?: {
    direction: TrendDirection;
    value: string;       // e.g., "+5%"
    label?: string;      // e.g., "vs 24h ago"
  };
}

// States:
//   Loading  → <Skeleton variant="rect" width="100%" height="120px" />
//   Error    → 값 영역에 "--" 표시, tooltip에 에러 메시지
//   Empty    → value="0" 기본 표시

// Design tokens:
//   Container: bg-surface-container p-5 rounded-xl border-l-4 shadow-sm
//   Value:     text-3xl font-headline font-bold
//   Label:     text-xs font-semibold tracking-wider uppercase text-slate-400
//   Hover:     hover:bg-surface-container-high transition-colors
//   Icon:      w-10 h-10 rounded-xl bg-{borderVariant}/10
```

### 3.2 InstanceCard

> **위치**: `src/components/instances/InstanceCard.tsx`

```typescript
interface InstanceCardProps {
  /** 인스턴스 데이터 */
  instance: Instance;
  /** 선택 여부 */
  isSelected: boolean;
  /** 클릭 핸들러 */
  onClick: (instanceId: UUID) => void;
}

// States:
//   Loading  → <Skeleton variant="rect" width="100%" height="88px" />
//   Offline  → opacity-60, 상태 아이콘 변경
//   Learning → 보라색 shimmer 애니메이션 (ai-shimmer)

// Events:
//   onClick → 인스턴스 선택, useDashboardStore.setInstance(id) 호출

// Design tokens:
//   Container:  bg-surface-container p-4 rounded-xl border border-white/10
//   Selected:   bg-surface-container-high border-primary/30 ring-1 ring-primary/20
//   Status dot: w-2 h-2 rounded-full (healthy=tertiary, warning=amber-500, critical=error, offline=slate-500)
//   Name:       text-sm font-medium text-on-surface
//   Host:       text-xs text-on-surface-variant font-mono
```

### 3.3 InstanceGrid

> **위치**: `src/components/instances/InstanceGrid.tsx`

```typescript
interface InstanceGridProps {
  /** 인스턴스 목록 */
  instances: Instance[];
  /** 인스턴스 선택 핸들러 */
  onSelect: (instanceId: UUID) => void;
  /** 현재 선택된 인스턴스 ID */
  selectedId?: UUID;
}

// States:
//   Loading  → grid-cols-3 with 6x <Skeleton />
//   Error    → <EmptyState title="인스턴스를 불러올 수 없습니다" actionLabel="재시도" />
//   Empty    → <EmptyState title="등록된 인스턴스가 없습니다" actionLabel="인스턴스 추가" />

// Design tokens:
//   Grid: grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4
```

### 3.4 MetricChart

> **위치**: `src/components/metrics/MetricChart.tsx`
> **차트 라이브러리**: Apache ECharts (via echarts-for-react)

```typescript
interface MetricChartProps {
  /** 대상 인스턴스 ID */
  instanceId: UUID;
  /** 표시할 메트릭 종류 */
  metricType: 'cpu_usage' | 'memory_usage' | 'tps' | 'active_connections' |
              'buffer_hit_ratio' | 'replication_lag_ms' | 'cache_hit_ratio';
  /** 시간 범위 */
  timeRange: TimeRange;
  /** 해상도 (기본: auto) */
  resolution?: Resolution;
  /** 베이스라인 오버레이 표시 */
  showBaseline?: boolean;
  /** 차트 높이 (기본: 240px) */
  height?: number;
}

// States:
//   Loading  → 차트 영역 pulse 애니메이션
//   Error    → 차트 영역에 ErrorBoundary 표시 + 재시도 버튼
//   Empty    → "데이터 없음" 메시지

// ECharts 옵션:
//   Theme:      dark (custom neuraldb theme)
//   Line color: primary (#89ceff)
//   Baseline:   stroke-dasharray="4 4" secondary (#d0bcff)
//   Area fill:  primary/10 gradient
//   Tooltip:    glass-panel 스타일
//   Grid:       top=20, right=20, bottom=40, left=60
```

### 3.5 ASHHeatmap

> **위치**: `src/components/ash/ASHHeatmap.tsx`
> **디자인 참조**: FRONTEND_DESIGN.md 4.3 ASH Heatmap
> **차트 라이브러리**: Apache ECharts (heatmap series)

```typescript
interface ASHHeatmapProps {
  /** 히트맵 데이터 */
  data: HeatmapData;
  /** 셀 클릭 핸들러 */
  onCellClick: (time: ISO8601, category: string) => void;
  /** 시간 해상도 */
  resolution: Resolution;
  /** 높이 (기본: 192px = h-48) */
  height?: number;
}

// States:
//   Loading  → 4행 x 24열 Skeleton grid
//   Error    → ErrorBoundary + retry
//   Empty    → "ASH 데이터가 없습니다" 메시지

// Events:
//   onCellClick → SessionTable 필터링, useASHStore.selectCell() 호출

// ECharts 옵션:
//   Y-axis:  ["Network", "I/O", "Lock", "CPU"]
//   Color map:
//     Idle:     surface-variant (#2d3449)
//     I/O:      sky-900 → sky-500 (#0c4a6e → #0ea5e9)
//     Lock:     orange-900 → orange-400 → error (#7c2d12 → #fb923c → #ffb4ab)
//     CPU:      secondary-container 20%~100% (#571bc1)
//   Hover:    scale(1.1) ease-out
```

### 3.6 SessionTable

> **위치**: `src/components/ash/SessionTable.tsx`
> **디자인 참조**: FRONTEND_DESIGN.md 4.3 Session Detail Table

```typescript
interface SessionTableProps {
  /** 세션 목록 */
  sessions: ActiveSession[];
  /** Explain Plan 버튼 클릭 */
  onExplainClick: (pid: number, query: string) => void;
  /** 선택된 PID */
  selectedPid?: number;
}

// States:
//   Loading  → 5행 Skeleton 테이블
//   Error    → ErrorBoundary + retry
//   Empty    → <EmptyState title="활성 세션이 없습니다" />

// Events:
//   onExplainClick → NL2SQL explain API 호출 트리거

// Design tokens:
//   Header:    bg-surface-container-high/50 text-slate-400 text-[10px] uppercase tracking-widest
//   Columns:   PID | Query Snippet | State | Wait Event | Duration | Action
//   State badges:
//     locked:  bg-orange-900/40 text-orange-400 rounded-full
//     active:  bg-sky-900/40 text-sky-400 rounded-full
//     running: bg-secondary-container/40 text-secondary rounded-full
//   Selected row: bg-primary/5
//   Explain btn:  opacity-0 group-hover:opacity-100 transition-opacity
```

### 3.7 WaitBreakdownPanel

> **위치**: `src/components/ash/WaitBreakdownPanel.tsx`
> **디자인 참조**: FRONTEND_DESIGN.md 4.3 Wait Breakdown

```typescript
interface WaitBreakdownPanelProps {
  /** Wait 유형별 데이터 */
  data: WaitBreakdown[];
  /** 로딩 상태 */
  isLoading?: boolean;
}

// States:
//   Loading  → 3개 Skeleton 프로그레스 바
//   Error    → ErrorBoundary
//   Empty    → "Wait 이벤트 없음"

// Design tokens:
//   Bar bg:     bg-surface-variant h-2 rounded-full
//   Bar fill:   각 wait_event_type 색상, rounded-full
//   Label:      text-xs text-on-surface-variant
//   Percentage: text-sm font-mono font-bold text-on-surface
```

### 3.8 IncidentList

> **위치**: `src/components/incidents/IncidentList.tsx`

```typescript
interface IncidentListProps {
  /** 인시던트 목록 */
  incidents: Incident[];
  /** 선택 핸들러 */
  onSelect: (incidentId: UUID) => void;
  /** 현재 선택된 인시던트 ID */
  selectedId?: UUID;
  /** 로딩 상태 */
  isLoading?: boolean;
}

// States:
//   Loading  → 5개 IncidentCard Skeleton
//   Error    → ErrorBoundary + retry
//   Empty    → <EmptyState title="인시던트가 없습니다" description="시스템이 정상입니다" />

// Design tokens:
//   Container: flex flex-col gap-2 overflow-y-auto max-h-[calc(100vh-200px)]
```

### 3.9 IncidentCard

> **위치**: `src/components/incidents/IncidentCard.tsx`

```typescript
interface IncidentCardProps {
  /** 인시던트 데이터 */
  incident: Incident;
  /** 선택 여부 */
  isSelected: boolean;
  /** 클릭 핸들러 */
  onClick: (incidentId: UUID) => void;
}

// Events:
//   onClick → IncidentDetail 패널 표시

// Design tokens:
//   Container:  bg-surface-container p-4 rounded-xl cursor-pointer
//   Selected:   bg-surface-container-high border-l-4 border-{severity-color}
//   Severity colors:
//     CRITICAL: error (#ffb4ab)
//     WARNING:  amber-500 (#f59e0b)
//     NOTICE:   primary (#89ceff)
//     INFO:     on-surface-variant (#bec8d2)
//   Title:      text-sm font-medium text-on-surface truncate
//   Timestamp:  text-xs text-on-surface-variant
//   Status badge: text-[10px] uppercase tracking-wider font-bold
```

### 3.10 ConfidenceBadge

> **위치**: `src/components/ai/ConfidenceBadge.tsx`
> **Spec 참조**: CONFIDENCE_SCORE_SPEC.md

```typescript
interface ConfidenceBadgeProps {
  /** 신뢰도 점수 (0.0 ~ 1.0) */
  confidence: number;
  /** 크기 변형 */
  size?: 'sm' | 'md' | 'lg';
}

// 신뢰도 → 등급 매핑:
//   >= 0.85 → HIGH     → tertiary (#4edea3)
//   >= 0.65 → MEDIUM   → primary (#89ceff)
//   >= 0.40 → LOW      → amber-500 (#f59e0b)
//   <  0.40 → VERY_LOW → error (#ffb4ab)

// Size variants:
//   sm: text-[10px] px-1.5 py-0.5
//   md: text-xs px-2 py-1
//   lg: text-sm px-3 py-1.5

// Design tokens:
//   Container: rounded-full font-mono font-bold bg-{grade-color}/20 text-{grade-color}
//   Tooltip:   "신뢰도: {confidence * 100}% ({grade})"
```

### 3.11 ReasoningChainPanel

> **위치**: `src/components/ai/ReasoningChainPanel.tsx`
> **Spec 참조**: CONFIDENCE_SCORE_SPEC.md, MTL_RCA_SPEC.md

```typescript
interface ReasoningChainPanelProps {
  /** 추론 단계 목록 */
  steps: ReasoningStep[];
  /** 근거 링크 목록 */
  evidenceLinks: EvidenceLink[];
  /** 패널 펼침 여부 */
  isExpanded: boolean;
  /** 펼침/접힘 토글 */
  onToggle: () => void;
}

// States:
//   Loading  → 3개 step Skeleton (타임라인 형태)
//   Error    → "추론 체인을 불러올 수 없습니다"
//   Empty    → "추론 데이터 없음"

// Design tokens:
//   Container:     bg-surface-container rounded-xl border border-white/5
//   Header:        px-5 py-3 cursor-pointer flex justify-between items-center
//   Header text:   text-sm font-medium text-secondary
//   Step timeline: ml-6 border-l-2 border-secondary/30 pl-4
//   Step dot:      w-3 h-3 rounded-full bg-secondary absolute -left-[7px]
//   Evidence chip: bg-surface-container-high px-2 py-0.5 rounded text-[10px] text-on-surface-variant
//   Expand icon:   transform transition-transform (rotate-180 when expanded)
```

### 3.12 MTLPredictionCard

> **위치**: `src/components/ai/MTLPredictionCard.tsx`
> **Spec 참조**: MTL_RCA_SPEC.md

```typescript
interface MTLPredictionCardProps {
  /** MTL 예측 결과 */
  prediction: MTLPrediction;
  /** 피드백 핸들러 */
  onFeedback: (predictionId: UUID, feedback: 'positive' | 'negative') => void;
}

// States:
//   Loading  → ai-shimmer 애니메이션
//   Error    → ErrorBoundary + "AI 분석 실패"
//   Feedback submitted → 해당 버튼 비활성화

// Events:
//   onFeedback → useMTLFeedback() mutation 호출

// Design tokens:
//   Container:     bg-surface-container rounded-xl p-5 border border-secondary/20
//   AI indicator:  ai-shimmer gradient border
//   Title:         text-sm font-medium text-on-surface
//   Root cause:    text-xs text-on-surface-variant mt-1
//   Confidence:    <ConfidenceBadge /> 우상단
//   Feedback btns: flex gap-2 mt-3
//     Positive:    bg-tertiary/10 text-tertiary hover:bg-tertiary/20 rounded-lg px-3 py-1
//     Negative:    bg-error/10 text-error hover:bg-error/20 rounded-lg px-3 py-1
```

### 3.13 NL2SQLChat

> **위치**: `src/components/copilot/NL2SQLChat.tsx`
> **디자인 참조**: FRONTEND_DESIGN.md 3.3 SideNavBar 하단 NL2SQL Assistant

```typescript
interface NL2SQLChatProps {
  /** 대상 인스턴스 ID */
  instanceId: UUID;
  /** 채팅창 열림 여부 */
  isOpen: boolean;
  /** 닫기 핸들러 */
  onClose: () => void;
}

// States:
//   Loading (query in progress) → Spinner + "SQL 생성 중..."
//   Error                       → ChatMessage role="error"
//   Empty                       → "질문을 입력하세요" 안내 메시지

// Events:
//   Submit → useNL2SQL() mutation
//   Close  → useNL2SQLStore.toggle()

// Design tokens:
//   Container:   fixed bottom-4 right-4 w-[480px] h-[600px] glass-panel rounded-2xl z-50
//   Header:      bg-secondary-container/30 px-5 py-3 rounded-t-2xl
//   Input:       bg-surface-container-lowest rounded-xl px-4 py-2 text-sm
//   Send btn:    bg-primary-container text-on-primary-container rounded-lg px-3
```

### 3.14 ChatMessage

> **위치**: `src/components/copilot/ChatMessage.tsx`

```typescript
interface ChatMessageProps {
  /** 메시지 발신자 역할 */
  role: 'user' | 'ai' | 'error';
  /** 메시지 본문 */
  content: string;
  /** 생성된 SQL 코드 (AI 메시지) */
  sqlCode?: string;
  /** 쿼리 실행 결과 테이블 (AI 메시지) */
  resultTable?: NL2SQLResult;
  /** 메시지 타임스탬프 */
  timestamp?: ISO8601;
}

// Design tokens:
//   User bubble:   bg-primary-container/20 text-on-surface rounded-xl rounded-tr-sm ml-12
//   AI bubble:     bg-surface-container text-on-surface rounded-xl rounded-tl-sm mr-12
//   Error bubble:  bg-error/10 text-error rounded-xl
//   SQL block:     bg-surface-container-lowest font-mono text-sm p-3 rounded-lg border border-white/5
//   SQL syntax:    text-secondary-fixed-dim (#d0bcff) for keywords
//   Result table:  compact DataTable, max-h-[200px] overflow-auto
```

### 3.15 AddDatabaseWizard

> **위치**: `src/components/admin/AddDatabaseWizard.tsx`

```typescript
interface AddDatabaseWizardProps {
  /** 완료 핸들러 */
  onComplete: (instance: InstanceDetail) => void;
  /** 취소 핸들러 */
  onCancel: () => void;
}

// 3-step wizard:
//   Step 1: Connection Info (host, port, database_name, ssl_mode, environment)
//   Step 2: Credentials (username, password) + Test Connection
//   Step 3: Configuration (name, tags, autonomy_level) + Confirm

// Internal state:
interface WizardState {
  currentStep: 1 | 2 | 3;
  formData: Partial<CreateInstanceRequest>;
  connectionTestResult: 'idle' | 'testing' | 'success' | 'failed';
  errors: Record<string, string>;
}

interface CreateInstanceRequest {
  name: string;
  host: string;
  port: number;
  database_name: string;
  ssl_mode: 'disable' | 'require' | 'verify-ca' | 'verify-full';
  environment: Environment;
  username: string;
  password: string;
  tags: string[];
  autonomy_level: AutonomyLevel;
}

// Design tokens:
//   Container: Modal size="lg"
//   Steps:     flex gap-8, step indicator circles (completed=tertiary, current=primary, future=surface-variant)
//   Form:      flex flex-col gap-4
//   Input:     bg-surface-container-lowest rounded-xl px-4 py-2 border border-white/5
//   Buttons:   "이전" (ghost), "다음" (primary-container), "등록" (tertiary)
```

### 3.16 AlertChannelForm

> **위치**: `src/components/admin/AlertChannelForm.tsx`

```typescript
interface AlertChannelFormProps {
  /** 기존 채널 (수정 모드) */
  channel?: AlertChannel;
  /** 저장 핸들러 */
  onSave: (channel: Omit<AlertChannel, 'id' | 'created_at'>) => void;
  /** 취소 핸들러 */
  onCancel: () => void;
}

// Design tokens:
//   Container: bg-surface-container rounded-xl p-6
//   Type selector: 3-button toggle (Slack/Email/Webhook)
//   Form fields: 타입별 동적 렌더링
//   Test btn:     "테스트 발송" bg-surface-variant
//   Save btn:     bg-primary-container text-on-primary-container
```

### 3.17 UserTable

> **위치**: `src/components/admin/UserTable.tsx`

```typescript
interface UserTableProps {
  /** 사용자 목록 */
  users: User[];
  /** 수정 핸들러 */
  onEdit: (userId: UUID) => void;
  /** 삭제 핸들러 */
  onDelete: (userId: UUID) => void;
}

// Columns: Name | Email | Role | Last Login | Status | Actions
// Design tokens:
//   Table:       <DataTable /> 컴포넌트 활용
//   Role badge:  text-[10px] uppercase font-bold rounded-full px-2 py-0.5
//     super_admin: bg-error/20 text-error
//     db_admin:    bg-secondary/20 text-secondary
//     operator:    bg-primary/20 text-primary
//     viewer:      bg-surface-variant text-on-surface-variant
//   Status:      is_active ? tertiary dot : slate-500 dot
//   Actions:     Edit (pencil icon) + Delete (trash icon, confirm modal)
```

### 3.18 SchemaChangeTimeline

> **위치**: `src/components/schema/SchemaChangeTimeline.tsx`

```typescript
interface SchemaChangeTimelineProps {
  /** 스키마 변경 이력 */
  changes: SchemaChange[];
}

// States:
//   Loading  → 4개 timeline item Skeleton
//   Empty    → <EmptyState title="DDL 변경 이력이 없습니다" />

// Design tokens:
//   Timeline:    relative ml-4 border-l-2 border-outline-variant/30
//   Dot:         w-3 h-3 rounded-full absolute -left-[7px]
//     CREATE:    bg-tertiary
//     ALTER:     bg-primary
//     DROP:      bg-error
//     RENAME:    bg-amber-500
//   DDL block:   font-mono text-xs bg-surface-container-lowest p-2 rounded-lg
//   Timestamp:   text-[10px] text-on-surface-variant
```

### 3.19 SystemHealthCard

> **위치**: `src/components/admin/SystemHealthCard.tsx`

```typescript
interface SystemHealthCardProps {
  /** 컴포넌트명 (e.g., "PostgreSQL", "Valkey", "Celery") */
  component: string;
  /** 상태 */
  status: 'up' | 'down' | 'degraded';
  /** 컴포넌트별 메트릭 */
  metrics: Record<string, string | number>;
  /** Material Symbols 아이콘명 */
  icon?: string;
}

// Design tokens:
//   Container:   bg-surface-container p-4 rounded-xl
//   Status indicator:
//     up:        w-2 h-2 rounded-full bg-tertiary animate-pulse
//     down:      w-2 h-2 rounded-full bg-error
//     degraded:  w-2 h-2 rounded-full bg-amber-500 animate-pulse
//   Component name: text-sm font-medium text-on-surface
//   Metrics:     text-xs text-on-surface-variant font-mono
```

### 3.20 공통 UI 컴포넌트

#### Tabs

> **위치**: `src/components/ui/Tabs.tsx`

```typescript
interface TabItem {
  key: string;
  label: string;
  icon?: string;
  badge?: number;
  disabled?: boolean;
}

interface TabsProps {
  /** 탭 항목 목록 */
  items: TabItem[];
  /** 활성 탭 키 */
  activeKey: string;
  /** 탭 변경 핸들러 */
  onChange: (key: string) => void;
  /** 변형 */
  variant?: 'underline' | 'pills';
}

// Design tokens:
//   Underline variant:
//     Active:   text-primary border-b-2 border-primary
//     Inactive: text-on-surface-variant hover:text-on-surface
//   Pills variant:
//     Active:   bg-primary-container text-on-primary-container rounded-lg
//     Inactive: text-on-surface-variant hover:bg-surface-bright rounded-lg
//   Badge:      bg-error text-on-error rounded-full text-[10px] min-w-[18px] px-1
```

#### Toast

> **위치**: `src/components/ui/Toast.tsx`

```typescript
interface ToastProps {
  /** 메시지 내용 */
  message: string;
  /** 변형 */
  variant: 'success' | 'error' | 'warning' | 'info';
  /** 닫기 핸들러 */
  onClose: () => void;
  /** 자동 닫힘 시간 (ms, 기본: 5000) */
  duration?: number;
}

// Design tokens:
//   Container: fixed top-4 right-4 z-[100] glass-panel rounded-xl px-4 py-3 min-w-[320px]
//   Variants:
//     success: border-l-4 border-tertiary
//     error:   border-l-4 border-error
//     warning: border-l-4 border-amber-500
//     info:    border-l-4 border-primary
//   Message:   text-sm text-on-surface
//   Close btn: text-on-surface-variant hover:text-on-surface
//   Animation: slide-in from right (translateX 100% → 0, 200ms ease-out)
```

#### Modal

> **위치**: `src/components/ui/Modal.tsx`

```typescript
interface ModalProps {
  /** 열림 여부 */
  isOpen: boolean;
  /** 닫기 핸들러 */
  onClose: () => void;
  /** 제목 */
  title: string;
  /** 모달 내용 */
  children: React.ReactNode;
  /** 크기 변형 */
  size?: 'sm' | 'md' | 'lg' | 'xl';
  /** 오버레이 클릭으로 닫기 허용 (기본: true) */
  closeOnOverlay?: boolean;
}

// Size:
//   sm:  max-w-sm  (384px)
//   md:  max-w-md  (448px)
//   lg:  max-w-2xl (672px)
//   xl:  max-w-4xl (896px)

// Design tokens:
//   Overlay:   fixed inset-0 bg-black/60 backdrop-blur-sm z-[90]
//   Container: glass-panel rounded-2xl p-0 shadow-2xl
//   Header:    px-6 py-4 border-b border-white/5
//   Title:     text-lg font-headline font-bold text-on-surface
//   Body:      px-6 py-4 overflow-y-auto max-h-[70vh]
//   Close btn: absolute top-4 right-4 text-on-surface-variant hover:text-on-surface
//   Animation: fade-in overlay (opacity 0→1) + scale-in content (scale 0.95→1, 200ms ease-out)
```

#### Spinner

> **위치**: `src/components/ui/Spinner.tsx`

```typescript
interface SpinnerProps {
  /** 크기 변형 */
  size?: 'sm' | 'md' | 'lg';
  /** 색상 (기본: primary) */
  color?: string;
}

// Size:
//   sm: w-4 h-4
//   md: w-6 h-6
//   lg: w-10 h-10

// Design tokens:
//   Element:   border-2 border-primary/30 border-t-primary rounded-full animate-spin
```

#### EmptyState

> **위치**: `src/components/ui/EmptyState.tsx`

```typescript
interface EmptyStateProps {
  /** 제목 */
  title: string;
  /** 설명 */
  description?: string;
  /** CTA 버튼 라벨 */
  actionLabel?: string;
  /** CTA 버튼 클릭 핸들러 */
  onAction?: () => void;
  /** 아이콘 (Material Symbols) */
  icon?: string;
}

// Design tokens:
//   Container:   flex flex-col items-center justify-center py-16
//   Icon:        text-4xl text-on-surface-variant/50 mb-4
//   Title:       text-lg font-medium text-on-surface
//   Description: text-sm text-on-surface-variant mt-1
//   Action btn:  bg-primary-container text-on-primary-container px-4 py-2 rounded-xl mt-4
```

#### Skeleton

> **위치**: `src/components/ui/Skeleton.tsx`

```typescript
interface SkeletonProps {
  /** 너비 (CSS value) */
  width?: string | number;
  /** 높이 (CSS value) */
  height?: string | number;
  /** 형태 변형 */
  variant: 'text' | 'rect' | 'circle';
  /** 추가 className */
  className?: string;
}

// Variant:
//   text:   h-4 rounded
//   rect:   rounded-xl
//   circle: rounded-full, width = height

// Animation:
//   @keyframes shimmer {
//     0%   { transform: translateX(-100%); }
//     100% { transform: translateX(100%); }
//   }
//   background: linear-gradient(90deg, transparent, surface-container-high/50, transparent)
//   animation: shimmer 1.5s ease-in-out infinite

// Design tokens:
//   Base bg:  bg-surface-container-high/30
//   Shimmer:  bg-gradient-to-r from-transparent via-surface-container-high/50 to-transparent
```

#### Tooltip

> **위치**: `src/components/ui/Tooltip.tsx`

```typescript
interface TooltipProps {
  /** 툴팁 내용 */
  content: string | React.ReactNode;
  /** 트리거 엘리먼트 */
  children: React.ReactNode;
  /** 위치 */
  placement?: 'top' | 'bottom' | 'left' | 'right';
  /** 표시 딜레이 (ms, 기본: 200) */
  delay?: number;
}

// Design tokens:
//   Container: glass-panel rounded-lg px-3 py-1.5 text-xs text-on-surface z-[80]
//   Arrow:     w-2 h-2 rotate-45 glass-panel
//   Animation: fade-in (opacity 0→1, 100ms ease-out)
```

#### DataTable

> **위치**: `src/components/ui/DataTable.tsx`

```typescript
interface Column<T = any> {
  key: string;
  header: string;
  width?: string;
  sortable?: boolean;
  render?: (value: any, row: T, index: number) => React.ReactNode;
  align?: 'left' | 'center' | 'right';
}

interface DataTableProps<T = any> {
  /** 컬럼 정의 */
  columns: Column<T>[];
  /** 테이블 데이터 */
  data: T[];
  /** 페이지네이션 (선택) */
  pagination?: {
    total: number;
    page: number;
    pageSize: number;
    onPageChange: (page: number) => void;
  };
  /** 정렬 핸들러 */
  onSort?: (key: string, direction: 'asc' | 'desc') => void;
  /** 행 키 추출 */
  rowKey?: string | ((row: T) => string);
  /** 행 클릭 핸들러 */
  onRowClick?: (row: T) => void;
  /** 로딩 상태 */
  isLoading?: boolean;
  /** 빈 상태 메시지 */
  emptyMessage?: string;
  /** 고정 헤더 */
  stickyHeader?: boolean;
  /** 최대 높이 (스크롤) */
  maxHeight?: string;
}

// Design tokens:
//   Container:   bg-surface-container rounded-xl overflow-hidden
//   Header row:  bg-surface-container-high/50 text-slate-400 text-[10px] uppercase tracking-widest
//   Body row:    border-b border-white/5 hover:bg-surface-bright/30 transition-colors
//   Sort icon:   text-on-surface-variant, active: text-primary
//   Pagination:  flex justify-between items-center px-4 py-2 border-t border-white/5
//   Page btn:    bg-surface-container-high rounded-lg px-2 py-1 text-xs
```

---

## 4. Loading / Error / Empty 상태 패턴

### 4.1 Loading 패턴

```typescript
// 모든 데이터 의존 컴포넌트는 isLoading 상태에서 Skeleton 컴포넌트를 사용한다.

// Skeleton Shimmer 키프레임
// @keyframes shimmer {
//   0%   { transform: translateX(-100%); }
//   100% { transform: translateX(100%); }
// }
// animation: shimmer 1.5s ease-in-out infinite

// 사용 패턴:
function MetricChartLoading() {
  return (
    <div className="bg-surface-container rounded-xl p-5">
      <Skeleton variant="text" width="40%" height={16} />
      <Skeleton variant="rect" width="100%" height={240} className="mt-3" />
    </div>
  );
}
```

### 4.2 Error 패턴

```typescript
// ErrorBoundary + 재시도 버튼 조합

interface ErrorFallbackProps {
  error: Error;
  resetErrorBoundary: () => void;
}

function ErrorFallback({ error, resetErrorBoundary }: ErrorFallbackProps) {
  return (
    <div className="flex flex-col items-center justify-center p-8 bg-surface-container rounded-xl">
      <span className="material-symbols-outlined text-3xl text-error mb-2">error</span>
      <p className="text-sm text-on-surface-variant mb-3">{error.message}</p>
      <button
        onClick={resetErrorBoundary}
        className="bg-primary-container text-on-primary-container px-4 py-2 rounded-xl text-sm"
      >
        재시도
      </button>
    </div>
  );
}

// TanStack Query 에러 처리:
//   queryClient.setDefaultOptions({
//     queries: {
//       retry: 2,
//       retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 10000),
//     },
//   });
```

### 4.3 Empty 패턴

```typescript
// EmptyState 컴포넌트를 사용하며, CTA 버튼으로 다음 행동을 유도한다.

// 사용 예:
<EmptyState
  icon="inbox"
  title="인시던트가 없습니다"
  description="모니터링 중인 인스턴스에서 이상이 감지되면 여기에 표시됩니다."
  actionLabel="인스턴스 추가"
  onAction={() => navigate('/admin/instances/new')}
/>
```

---

## 5. 인수 기준

| ID | 기준 | 검증 방법 |
|----|------|----------|
| AC-1 | 모든 컴포넌트에 TypeScript Props 인터페이스가 정의되어 있다 | `tsc --noEmit` 통과, 모든 Props에 JSDoc 주석 포함 |
| AC-2 | 모든 API 응답 타입이 백엔드 Pydantic 스키마와 필드명/타입이 일치한다 | API_SPEC.md의 JSON 응답과 1:1 대응 확인 |
| AC-3 | Design token 참조가 FRONTEND_DESIGN.md와 일치한다 | 컴포넌트별 Design tokens 섹션의 클래스명이 FRONTEND_DESIGN.md 2절과 일치 |
| AC-4 | 모든 컴포넌트에 Loading/Error/Empty 3가지 상태가 정의되어 있다 | Storybook 스토리에서 3가지 상태 시각 확인 가능 |
| AC-5 | 공통 UI 컴포넌트(Tabs, Toast, Modal 등)가 디자인 시스템과 일관된다 | FRONTEND_DESIGN.md의 spacing, radius, color 규칙 준수 |
