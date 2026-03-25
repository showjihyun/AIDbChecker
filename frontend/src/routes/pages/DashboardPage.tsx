// Spec: MVP-DASH-001~005 — Dashboard main page
import { useState, useCallback } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { subHours } from 'date-fns';
import { useMemo } from 'react';
import { useInstances } from '@/api/hooks/useInstances';
import { useMetrics, useAllInstancesLatestMetrics } from '@/api/hooks/useMetrics';
import {
  InstanceCard,
  InstanceCardSkeleton,
  InstanceCardEmpty,
} from '@/components/dashboard/InstanceCard';
import { MetricChart } from '@/components/dashboard/MetricChart';
import { SystemHealthPanel } from '@/components/dashboard/SystemHealth';
import { useMetricStore, useLatestMetricsShallow } from '@/stores/metricStore';
import type { TimeRange } from '@/types/api';

export function DashboardPage() {
  const navigate = useNavigate();
  const { data: instances, isLoading: instancesLoading } = useInstances();
  const selectedInstanceId = useMetricStore((s) => s.selectedInstanceId);
  const setSelectedInstanceId = useMetricStore((s) => s.setSelectedInstanceId);
  const wsConnected = useMetricStore((s) => s.wsConnected);
  const wsLatestMetrics = useLatestMetricsShallow();

  // REST API fallback: poll latest metrics when WebSocket is disconnected
  const instanceIds = useMemo(
    () => (instances ?? []).map((i) => i.id),
    [instances]
  );
  const { data: restLatestMetrics } = useAllInstancesLatestMetrics(instanceIds, wsConnected);

  // Merge: prefer WebSocket data (real-time), fall back to REST polling
  const latestMetrics = useMemo(() => {
    const merged = { ...(restLatestMetrics ?? {}) };
    // WebSocket data overwrites REST data (more fresh)
    for (const [id, metric] of Object.entries(wsLatestMetrics)) {
      merged[id] = metric;
    }
    return merged;
  }, [wsLatestMetrics, restLatestMetrics]);

  const [timeRange, setTimeRange] = useState<TimeRange>(() => ({
    from: subHours(new Date(), 1).toISOString(),
    to: new Date().toISOString(),
  }));

  const { data: metricsData, isLoading: metricsLoading } = useMetrics(
    selectedInstanceId ?? undefined,
    timeRange
  );

  const handleTimeRangeChange = useCallback((from: string, to: string) => {
    setTimeRange({ from, to });
  }, []);

  const handleInstanceClick = useCallback(
    (id: string) => {
      setSelectedInstanceId(id === selectedInstanceId ? null : id);
    },
    [selectedInstanceId, setSelectedInstanceId]
  );

  const handleRegister = useCallback(() => {
    navigate({ to: '/instances' });
  }, [navigate]);

  const activeCount = instances?.filter((i) => i.is_active).length ?? 0;
  const totalCount = instances?.length ?? 0;

  return (
    <div className="space-y-module-gap">
      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
        <SummaryCard
          icon="dns"
          label="Total Instances"
          value={totalCount}
          accentColor="bg-primary-container"
        />
        <SummaryCard
          icon="group"
          label="Active Monitoring"
          value={activeCount}
          accentColor="bg-primary"
        />
        <SummaryCard
          icon="warning"
          label="Anomalies"
          value={0}
          accentColor="bg-error"
        />
        <SummaryCard
          icon="timer"
          label="Avg Latency"
          value="--"
          suffix="ms"
          accentColor="bg-tertiary"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Instance list */}
        <div className="lg:col-span-4 space-y-3">
          <h2 className="text-xs font-semibold tracking-wider uppercase text-on-surface-variant">
            Instances
          </h2>
          {instancesLoading ? (
            <InstanceCardSkeleton count={3} />
          ) : !instances || instances.length === 0 ? (
            <InstanceCardEmpty onRegister={handleRegister} />
          ) : (
            instances.map((instance) => (
              <InstanceCard
                key={instance.id}
                instance={instance}
                latestMetric={latestMetrics[instance.id]}
                isSelected={selectedInstanceId === instance.id}
                onClick={handleInstanceClick}
              />
            ))
          )}
        </div>

        {/* Charts and system health */}
        <div className="lg:col-span-8 space-y-6">
          <MetricChart
            data={metricsData}
            isLoading={metricsLoading}
            onTimeRangeChange={handleTimeRangeChange}
          />
          <SystemHealthPanel />
        </div>
      </div>
    </div>
  );
}

interface SummaryCardProps {
  icon: string;
  label: string;
  value: number | string;
  suffix?: string;
  accentColor: string;
}

function SummaryCard({ icon, label, value, suffix, accentColor }: SummaryCardProps) {
  return (
    <div
      className="bg-surface-container rounded-xl overflow-hidden hover:bg-surface-container-high transition-colors duration-200 ease-out flex"
    >
      {/* Fix #9: Replace border-l-4 with a color strip div (No-Line Rule) */}
      <div className={`w-1 shrink-0 ${accentColor}`} />
      <div className="p-5 flex-1">
      <div className="flex items-center gap-2 mb-2">
        <span className="material-symbols-outlined text-lg text-on-surface-variant">
          {icon}
        </span>
        <span className="text-[10px] font-semibold tracking-wider uppercase text-on-surface-variant">
          {label}
        </span>
      </div>
      <p className="text-3xl font-display font-bold text-on-surface tabular-nums">
        {value}
        {suffix && (
          <span className="text-sm font-sans font-normal text-on-surface-variant ml-1">
            {suffix}
          </span>
        )}
      </p>
      </div>
    </div>
  );
}
