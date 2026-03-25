// Spec: MVP-DASH-001 — Instance card with status, key metrics
import { cn } from '@/lib/cn';
import { Badge } from '@/components/common/Badge';
import { EmptyState } from '@/components/common/EmptyState';
import type { Instance, MetricSample } from '@/types/api';

interface InstanceCardProps {
  instance: Instance;
  latestMetric?: MetricSample;
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
  isSelected,
  onClick,
}: InstanceCardProps) {
  const status = getInstanceStatus(instance, latestMetric);
  const metrics = latestMetric?.metrics;

  return (
    <button
      onClick={() => onClick(instance.id)}
      className={cn(
        'w-full text-left rounded-xl p-5 transition-all duration-200 ease-out',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/50',
        isSelected
          ? 'bg-surface-container-high shadow-neural-glow'
          : 'bg-surface-container hover:bg-surface-container-high'
      )}
      aria-pressed={isSelected}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-on-surface truncate">
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

      {metrics ? (
        <div className="grid grid-cols-3 gap-3">
          <MetricValue
            label="Conn"
            value={metrics.numbackends ?? metrics.active_connections}
            unit=""
            warn={100}
            crit={200}
          />
          <MetricValue
            label="TPS"
            value={metrics.xact_commit ?? metrics.tps}
            unit=""
            warn={5000}
            crit={10000}
          />
          <MetricValue
            label="Hit%"
            value={
              metrics.blks_hit != null && metrics.blks_read != null
                ? Math.round(
                    (metrics.blks_hit / (metrics.blks_hit + metrics.blks_read + 0.001)) * 100
                  )
                : undefined
            }
            unit="%"
            warn={0}
            crit={0}
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
}

function MetricValue({ label, value, unit, warn, crit }: MetricValueProps) {
  const displayValue = value != null ? Math.round(value) : '--';
  const color =
    value == null
      ? 'text-outline'
      : value >= crit
        ? 'text-error'
        : value >= warn
          ? 'text-warning'
          : 'text-on-surface';

  return (
    <div>
      <p className="text-[10px] font-semibold tracking-wider uppercase text-on-surface-variant">
        {label}
      </p>
      <p className={cn('text-lg font-sans font-bold tabular-nums', color)}>
        {displayValue}
        {value != null && (
          <span className="text-xs font-sans font-normal text-on-surface-variant ml-0.5">
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
          <div className="grid grid-cols-3 gap-3">
            {Array.from({ length: 3 }).map((_, j) => (
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
