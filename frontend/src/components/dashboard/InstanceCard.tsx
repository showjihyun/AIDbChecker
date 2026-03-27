// Spec: MVP-DASH-001, FS-KPI-001 — Instance card with status, 5 key KPIs
import { cn } from '@/lib/cn';
import { Badge } from '@/components/common/Badge';
import { EmptyState } from '@/components/common/EmptyState';
import type { Instance, MetricSample } from '@/types/api';
import type { KPIResponse } from '@/types/kpi';

interface InstanceCardProps {
  instance: Instance;
  latestMetric?: MetricSample;
  kpiData?: KPIResponse;
  isSelected: boolean;
  onClick: (id: string) => void;
}

function getInstanceStatus(
  instance: Instance,
  metric?: MetricSample
): 'healthy' | 'critical' | 'warning' {
  if (!instance.is_active) return 'critical';
  if (!metric) return 'warning';

  // pg_stat_database raw metrics — numbackends as connection proxy
  const connections = metric.metrics.numbackends ?? metric.metrics.active_connections ?? 0;
  if (connections >= 200) return 'critical';
  if (connections >= 100) return 'warning';
  return 'healthy';
}

const statusLabels = {
  healthy: 'Healthy',
  critical: 'Critical',
  warning: 'Warning',
} as const;

export function InstanceCard({
  instance,
  latestMetric,
  kpiData,
  isSelected,
  onClick,
}: InstanceCardProps) {
  const status = getInstanceStatus(instance, latestMetric);
  const metrics = latestMetric?.metrics;
  const hasData = kpiData || metrics;

  // Derive 5 key KPIs from KPI API only — never show raw cumulative counters
  // Raw metrics (xact_commit, blks_hit) are cumulative and misleading as display values
  const tpsValue = kpiData?.throughput.tps.value ?? undefined;
  const tpsStatus = kpiData?.throughput.tps.status;

  const hitRatioValue = kpiData?.resource.buffer_hit_ratio.value ?? undefined;
  const hitStatus = kpiData?.resource.buffer_hit_ratio.status;

  // Conn: KPI active_sessions preferred, raw numbackends as fallback (it's a gauge, safe to show)
  const connValue = kpiData
    ? (kpiData.connection.active_sessions.value ?? undefined)
    : (metrics?.numbackends ?? metrics?.active_connections);
  const connStatus = kpiData?.connection.active_sessions.status;

  const lockValue = kpiData?.lock.lock_waits.value ?? undefined;
  const lockStatus = kpiData?.lock.lock_waits.status;

  const sizeBytes = kpiData?.storage.db_size_bytes.value ?? undefined;
  const sizeStatus = kpiData?.storage.db_size_bytes.status;

  return (
    <button
      onClick={() => onClick(instance.id)}
      className={cn(
        'w-full text-left rounded-xl p-5 transition-all duration-200 ease-out border-2',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/50',
        isSelected
          ? 'bg-primary/10 border-primary shadow-lg shadow-primary/20 ring-1 ring-primary/30'
          : 'bg-surface-container border-transparent hover:bg-surface-container-high hover:border-white/10'
      )}
      aria-pressed={isSelected}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="min-w-0">
          <h3 className={cn(
            'text-sm font-semibold truncate',
            isSelected ? 'text-primary' : 'text-on-surface'
          )}>
            {instance.name}
          </h3>
          <p className="text-xs text-on-surface-variant mt-0.5">
            {instance.host}:{instance.port}
          </p>
        </div>
        <Badge variant={status} dot>
          {statusLabels[status]}
        </Badge>
      </div>

      {hasData ? (
        <div className="grid grid-cols-5 gap-2">
          <MetricValue
            label="TPS"
            value={tpsValue}
            unit="/s"
            format="compact"
            warn={5000}
            crit={10000}
            kpiStatus={tpsStatus}
          />
          <MetricValue
            label="Hit%"
            value={hitRatioValue}
            unit="%"
            warn={0}
            crit={0}
            invertThreshold
            kpiStatus={hitStatus}
          />
          <MetricValue
            label="Conn"
            value={connValue}
            unit=""
            warn={50}
            crit={100}
            kpiStatus={connStatus}
          />
          <MetricValue
            label="Locks"
            value={lockValue}
            unit=""
            warn={5}
            crit={20}
            kpiStatus={lockStatus}
          />
          <MetricValue
            label="Size"
            value={sizeBytes != null ? sizeBytes : undefined}
            unit=""
            warn={999999999999}
            crit={999999999999}
            format="bytes"
            kpiStatus={sizeStatus}
          />
        </div>
      ) : (
        <p className="text-xs text-outline italic">
          {instance.is_active ? '수집 대기 중...' : '수집 중단'}
        </p>
      )}
    </button>
  );
}

interface MetricValueProps {
  label: string;
  value: number | undefined;
  unit: string;
  warn: number;
  crit: number;
  format?: 'default' | 'compact' | 'bytes';
  /** When true, lower values are worse (e.g., Hit Ratio: <95 warn, <90 crit) */
  invertThreshold?: boolean;
  /** Override color from KPI API status */
  kpiStatus?: 'normal' | 'warning' | 'critical' | 'unknown';
}

function formatCompact(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(Math.round(n));
}

function formatBytes(bytes: number): string {
  if (bytes >= 1_073_741_824) return `${(bytes / 1_073_741_824).toFixed(1)}G`;
  if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(0)}M`;
  if (bytes >= 1_024) return `${(bytes / 1_024).toFixed(0)}K`;
  return `${bytes}B`;
}

// Spec: FS-KPI-001 §4.3 — 3-stage traffic light
const kpiStatusColorMap: Record<string, string> = {
  normal: 'text-tertiary',    // 🟢 Healthy — green
  warning: 'text-warning',    // 🟡 Warning — amber
  critical: 'text-error',     // 🔴 Critical — red
  unknown: 'text-outline',    // ⚪ Unknown — gray
};

function MetricValue({
  label,
  value,
  unit,
  warn,
  crit,
  format: fmt = 'default',
  kpiStatus,
}: MetricValueProps) {
  let displayValue: string;
  if (value == null) {
    displayValue = '--';
  } else if (fmt === 'bytes') {
    displayValue = formatBytes(value);
  } else if (fmt === 'compact') {
    displayValue = formatCompact(value);
  } else {
    displayValue = String(Math.round(value));
  }

  // Use KPI API status if available, otherwise fall back to threshold comparison
  let color: string;
  if (kpiStatus) {
    color = kpiStatusColorMap[kpiStatus] ?? 'text-on-surface';
  } else if (value == null) {
    color = 'text-outline';
  } else if (value >= crit) {
    color = 'text-error';
  } else if (value >= warn) {
    color = 'text-warning';
  } else {
    color = 'text-on-surface';
  }

  return (
    <div className="min-w-0">
      <p className="text-[10px] font-semibold tracking-wider uppercase text-on-surface-variant truncate">
        {label}
      </p>
      <p className={cn('text-base font-sans font-bold tabular-nums', color)}>
        {displayValue}
        {value != null && unit && fmt !== 'bytes' && (
          <span className="text-[10px] font-sans font-normal text-on-surface-variant ml-0.5">
            {unit}
          </span>
        )}
      </p>
    </div>
  );
}

interface InstanceCardSkeletonProps {
  count?: number;
}

export function InstanceCardSkeleton({ count = 3 }: InstanceCardSkeletonProps) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="bg-surface-container rounded-xl p-5 animate-pulse"
        >
          <div className="flex justify-between mb-3">
            <div>
              <div className="h-4 w-32 bg-surface-container-high rounded-sm" />
              <div className="h-3 w-24 bg-surface-container-high rounded-sm mt-1.5" />
            </div>
            <div className="h-6 w-16 bg-surface-container-high rounded-md" />
          </div>
          <div className="grid grid-cols-5 gap-2">
            {Array.from({ length: 5 }).map((_, j) => (
              <div key={j}>
                <div className="h-3 w-8 bg-surface-container-high rounded-sm" />
                <div className="h-6 w-12 bg-surface-container-high rounded-sm mt-1" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </>
  );
}

interface InstanceCardEmptyProps {
  onRegister: () => void;
}

export function InstanceCardEmpty({ onRegister }: InstanceCardEmptyProps) {
  return (
    <EmptyState
      icon="dns"
      message="인스턴스를 등록하세요"
      description="모니터링할 PostgreSQL 인스턴스를 등록하면 실시간 메트릭과 ASH 데이터를 확인할 수 있습니다."
      action={{ label: '인스턴스 등록', onClick: onRegister }}
    />
  );
}
