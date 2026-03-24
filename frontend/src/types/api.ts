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
  metrics: {
    cpu_usage?: number;
    memory_usage?: number;
    active_connections?: number;
    tps?: number;
    buffer_hit_ratio?: number;
    disk_read_iops?: number;
    disk_write_iops?: number;
    wal_generation_rate?: number;
    replication_lag_ms?: number;
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
