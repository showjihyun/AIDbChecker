// Spec: FS-KPI-001 -- KPI Overview Panel (12 KPIs, 5 categories)
import { cn } from '@/lib/cn';
import { useInstanceKPI } from '@/api/hooks/useKPI';
import type { KPIValue, KPIStatus } from '@/types/kpi';

interface KPIOverviewPanelProps {
  instanceId: string;
}

// --- Formatting helpers ---

function formatCompact(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(Math.round(n));
}

function formatBytes(bytes: number): string {
  if (bytes >= 1_073_741_824) return `${(bytes / 1_073_741_824).toFixed(1)} GB`;
  if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(1)} MB`;
  if (bytes >= 1_024) return `${(bytes / 1_024).toFixed(1)} KB`;
  return `${bytes} B`;
}

function formatKPIValue(kpi: KPIValue, displayUnit: string): string {
  if (kpi.value == null) return 'N/A';

  if (kpi.unit === 'bytes') {
    return formatBytes(kpi.value);
  }
  if (kpi.unit === '%') {
    return `${kpi.value.toFixed(1)}%`;
  }
  if (kpi.unit === 'ms') {
    return `${kpi.value.toFixed(1)} ms`;
  }
  if (kpi.unit === 'sec') {
    return `${kpi.value.toFixed(1)} s`;
  }
  // count, tx/s, q/s, ops/s, count/s
  const formatted = formatCompact(kpi.value);
  return displayUnit ? `${formatted} ${displayUnit}` : formatted;
}

// Spec: FS-KPI-001 §4.3 — 3-stage traffic light color coding
function statusColor(status: KPIStatus): string {
  switch (status) {
    case 'normal':
      return 'text-tertiary';   // 🟢 Healthy — green
    case 'warning':
      return 'text-warning';    // 🟡 Warning — amber/yellow
    case 'critical':
      return 'text-error';      // 🔴 Critical — red
    case 'unknown':
      return 'text-outline';    // ⚪ Unknown — gray
    default:
      return 'text-on-surface';
  }
}

// --- Sub-components ---

interface KPIItemProps {
  label: string;
  kpi: KPIValue;
  displayUnit?: string;
}

function KPIItem({ label, kpi, displayUnit = '' }: KPIItemProps) {
  return (
    <div className="min-w-0">
      <p className="text-[10px] font-semibold tracking-wider uppercase text-on-surface-variant truncate">
        {label}
      </p>
      <p className={cn('text-base font-sans font-bold tabular-nums', statusColor(kpi.status))}>
        {formatKPIValue(kpi, displayUnit)}
      </p>
    </div>
  );
}

interface CategorySectionProps {
  title: string;
  icon: string;
  children: React.ReactNode;
}

function CategorySection({ title, icon, children }: CategorySectionProps) {
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2">
        <span className="material-symbols-outlined text-sm text-on-surface-variant">
          {icon}
        </span>
        <h4 className="text-[10px] font-semibold tracking-wider uppercase text-on-surface-variant">
          {title}
        </h4>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-2">
        {children}
      </div>
    </div>
  );
}

function KPIOverviewSkeleton() {
  return (
    <div className="bg-surface-container rounded-xl p-5 animate-pulse space-y-4">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i}>
          <div className="h-3 w-28 bg-surface-container-high rounded-sm mb-2" />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {Array.from({ length: i < 2 ? 4 : 2 }).map((_, j) => (
              <div key={j}>
                <div className="h-2.5 w-12 bg-surface-container-high rounded-sm" />
                <div className="h-5 w-16 bg-surface-container-high rounded-sm mt-1" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// --- Main component ---

export function KPIOverviewPanel({ instanceId }: KPIOverviewPanelProps) {
  const { data: kpi, isLoading, isError } = useInstanceKPI(instanceId);

  if (isLoading) {
    return <KPIOverviewSkeleton />;
  }

  if (isError || !kpi) {
    return (
      <div className="bg-surface-container rounded-xl p-5">
        <p className="text-xs text-outline italic">KPI data unavailable</p>
      </div>
    );
  }

  return (
    <div className="bg-surface-container rounded-xl p-5 space-y-4">
      <CategorySection title="Throughput & Latency" icon="speed">
        <KPIItem label="TPS" kpi={kpi.throughput.tps} displayUnit="tx/s" />
        <KPIItem label="QPS" kpi={kpi.throughput.qps} displayUnit="q/s" />
        <KPIItem label="Avg Response" kpi={kpi.throughput.avg_response_time_ms} />
        <KPIItem label="Slow Queries" kpi={kpi.throughput.slow_queries} />
      </CategorySection>

      <CategorySection title="Resource" icon="memory">
        <KPIItem label="Hit Ratio" kpi={kpi.resource.buffer_hit_ratio} />
        <KPIItem label="Disk IOPS" kpi={kpi.resource.disk_iops} displayUnit="ops/s" />
      </CategorySection>

      <CategorySection title="Connection" icon="lan">
        <KPIItem label="Active Sessions" kpi={kpi.connection.active_sessions} />
        <KPIItem label="Conn Usage" kpi={kpi.connection.connection_usage_pct} />
      </CategorySection>

      <CategorySection title="Lock" icon="lock">
        <KPIItem label="Lock Waits" kpi={kpi.lock.lock_waits} />
        <KPIItem label="Deadlocks" kpi={kpi.lock.deadlocks_per_sec} displayUnit="/s" />
      </CategorySection>

      <CategorySection title="Storage" icon="storage">
        <KPIItem label="DB Size" kpi={kpi.storage.db_size_bytes} />
        <KPIItem label="Repl Lag" kpi={kpi.storage.replication_lag_sec} />
      </CategorySection>
    </div>
  );
}
