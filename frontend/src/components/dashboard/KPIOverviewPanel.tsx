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

  // DBA 관점: 중요도 순서 — Throughput → Connection/Lock → Resource/Storage
  // 2행 그리드로 수직 스크롤 최소화
  return (
    <div className="bg-surface-container rounded-xl p-5">
      {/* Row 1: 핵심 KPI 6개 (한 줄에 모두 표시) */}
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-3 mb-3">
        <KPIItem label="TPS" kpi={kpi.throughput.tps} displayUnit="tx/s" />
        <KPIItem label="Active Sess" kpi={kpi.connection.active_sessions} />
        <KPIItem label="Lock Waits" kpi={kpi.lock.lock_waits} />
        <KPIItem label="Hit Ratio" kpi={kpi.resource.buffer_hit_ratio} />
        <KPIItem label="Avg Resp" kpi={kpi.throughput.avg_response_time_ms} />
        <KPIItem label="Deadlocks" kpi={kpi.lock.deadlocks_per_sec} displayUnit="/s" />
      </div>

      {/* Row 2: 보조 KPI 6개 */}
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-3 pt-3 border-t border-white/5">
        <KPIItem label="QPS" kpi={kpi.throughput.qps} displayUnit="q/s" />
        <KPIItem label="Conn Usage" kpi={kpi.connection.connection_usage_pct} />
        <KPIItem label="Slow Query" kpi={kpi.throughput.slow_queries} />
        <KPIItem label="Disk IOPS" kpi={kpi.resource.disk_iops} displayUnit="ops/s" />
        <KPIItem label="DB Size" kpi={kpi.storage.db_size_bytes} />
        <KPIItem label="Repl Lag" kpi={kpi.storage.replication_lag_sec} />
      </div>
    </div>
  );
}
