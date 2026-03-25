// Spec: DM-001 (ERD), API_SPEC.md

export interface Instance {
  id: string;
  name: string;
  db_type: 'postgresql' | 'mysql' | 'mssql';
  host: string;
  port: number;
  database_name: string;
  cluster_id: string | null;
  environment: 'production' | 'staging' | 'development';
  is_active: boolean;
  autonomy_level: number;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface MetricSample {
  id: string;
  instance_id: string;
  sampled_at: string;
  category: 'hot' | 'warm' | 'cold';
  metrics: Record<string, number | undefined> & {
    // Computed/standardized fields (Phase 2+)
    cpu_usage?: number;
    memory_usage?: number;
    active_connections?: number;
    tps?: number;
    buffer_hit_ratio?: number;
    // Raw pg_stat_database fields (Phase 1 — directly from adapter)
    numbackends?: number;
    xact_commit?: number;
    xact_rollback?: number;
    blks_hit?: number;
    blks_read?: number;
    tup_returned?: number;
    tup_fetched?: number;
    tup_inserted?: number;
    tup_updated?: number;
    tup_deleted?: number;
  };
}

export interface ActiveSession {
  id: string;
  instance_id: string;
  sampled_at: string;
  pid: number;
  query: string | null;
  query_hash: number | null;
  state: 'active' | 'idle' | 'idle in transaction' | 'locked';
  wait_event_type: string | null;
  wait_event: string | null;
  backend_type: string | null;
  client_addr: string | null;
  application_name: string | null;
  query_start: string | null;
  duration_ms: number | null;
}

export interface ASHHeatmapData {
  time_buckets: string[];
  wait_event_types: string[];
  values: number[][];
}

export interface WaitBreakdown {
  wait_event_type: string;
  count: number;
  percentage: number;
}

export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'down';
  components: {
    database: ComponentHealth;
    valkey: ComponentHealth;
    celery: ComponentHealth;
    kafka: ComponentHealth;
  };
  uptime_seconds: number;
}

export interface ComponentHealth {
  status: 'up' | 'down' | 'degraded';
  latency_ms: number | null;
  details: Record<string, unknown>;
}

// Spec: FS-DASH-004
export type IncidentSeverity = 'critical' | 'warning' | 'notice' | 'info';
export type IncidentStatus = 'open' | 'acknowledged' | 'in_progress' | 'resolved' | 'closed';

export interface Incident {
  id: string;
  instance_id: string | null;
  instance_name: string | null;
  severity: IncidentSeverity;
  status: IncidentStatus;
  title: string;
  description: string | null;
  source: string;
  metric_type: string | null;
  metric_value: number | null;
  baseline_value: number | null;
  detected_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
}

export interface IncidentListResponse {
  items: Incident[];
  total: number;
}

export interface IncidentFilters {
  severity?: IncidentSeverity;
  status?: IncidentStatus;
  instance_id?: string;
  limit?: number;
  cursor?: string;
}

export interface ApiError {
  detail: string;
  code: string;
  status: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  cursor: string | null;
}

export interface TimeRange {
  from: string;
  to: string;
}

export interface CreateInstanceRequest {
  name: string;
  db_type: 'postgresql' | 'mysql' | 'mssql';
  host: string;
  port: number;
  database_name: string;
  cluster_id?: string;
  environment: 'production' | 'staging' | 'development';
  connection_config?: Record<string, unknown>;
}

export interface TestConnectionRequest {
  host: string;
  port: number;
  database_name: string;
  connection_config?: Record<string, unknown>;
}

export interface TestConnectionResponse {
  success: boolean;
  latency_ms: number;
  version: string | null;
  error: string | null;
}
