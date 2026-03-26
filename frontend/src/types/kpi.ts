// Spec: FS-KPI-001 -- DB KPI types (12 KPIs across 5 categories)

export type KPIStatus = 'normal' | 'warning' | 'critical' | 'unknown';

export interface KPIValue {
  value: number | null;
  unit: string;
  status: KPIStatus;
}

export interface KPIThroughput {
  tps: KPIValue;
  qps: KPIValue;
  avg_response_time_ms: KPIValue;
  slow_queries: KPIValue;
}

export interface KPIResource {
  buffer_hit_ratio: KPIValue;
  disk_iops: KPIValue;
}

export interface KPIConnection {
  active_sessions: KPIValue;
  connection_usage_pct: KPIValue;
}

export interface KPILock {
  lock_waits: KPIValue;
  deadlocks_per_sec: KPIValue;
}

export interface KPIStorage {
  db_size_bytes: KPIValue;
  replication_lag_sec: KPIValue;
}

export interface KPIAdvisory {
  level: 'info' | 'warning' | 'error';
  title: string;
  message: string;
  action?: string | null;
}

export interface KPIResponse {
  instance_id: string;
  timestamp: string;
  throughput: KPIThroughput;
  resource: KPIResource;
  connection: KPIConnection;
  lock: KPILock;
  storage: KPIStorage;
  advisories: KPIAdvisory[];
}
