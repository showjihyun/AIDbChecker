// Spec: MVP-DASH-003 — ASH Explorer page with heatmap and session table
import { useState, useCallback } from 'react';
import { subMinutes } from 'date-fns';
import { useASHHeatmap, useASHSessions } from '@/api/hooks/useASH';
import { ASHHeatmap } from '@/components/ash/ASHHeatmap';
import { SessionTable } from '@/components/ash/SessionTable';
import { EmptyState } from '@/components/common/EmptyState';
import { useInstances } from '@/api/hooks/useInstances';
import { useMetricStore } from '@/stores/metricStore';
import { cn } from '@/lib/cn';
import type { TimeRange } from '@/types/api';

export function ASHExplorerPage() {
  const { data: instances } = useInstances();
  const selectedInstanceId = useMetricStore((s) => s.selectedInstanceId);
  const setSelectedInstanceId = useMetricStore((s) => s.setSelectedInstanceId);

  const [timeRange, setTimeRange] = useState<TimeRange>(() => ({
    from: subMinutes(new Date(), 30).toISOString(),
    to: new Date().toISOString(),
  }));

  const { data: heatmapData, isLoading: heatmapLoading } = useASHHeatmap(
    selectedInstanceId ?? undefined,
    timeRange
  );

  const { data: sessions, isLoading: sessionsLoading } = useASHSessions(
    selectedInstanceId ?? undefined,
    timeRange
  );

  const handleTimeRangeChange = useCallback((from: string, to: string) => {
    setTimeRange({ from, to });
  }, []);

  return (
    <div className="space-y-module-gap">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold text-on-surface tracking-tight">
            ASH Explorer
          </h1>
          <p className="text-xs text-on-surface-variant mt-1">
            Active Session History - 1-second granularity wait event analysis
          </p>
        </div>

        {/* Instance selector */}
        {instances && instances.length > 0 && (
          <div className="flex gap-2">
            {instances.map((inst) => (
              <button
                key={inst.id}
                onClick={() => setSelectedInstanceId(inst.id)}
                className={cn(
                  'px-3 py-1.5 rounded-md text-xs font-medium transition-colors duration-200 ease-out',
                  selectedInstanceId === inst.id
                    ? 'bg-primary-container text-on-primary'
                    : 'bg-surface-container text-on-surface-variant hover:bg-surface-container-high'
                )}
              >
                {inst.name}
              </button>
            ))}
          </div>
        )}
      </div>

      {!selectedInstanceId ? (
        <EmptyState
          icon="analytics"
          message="인스턴스를 선택하세요"
          description="분석할 데이터베이스 인스턴스를 선택하면 Wait Event 히트맵과 세션 정보를 확인할 수 있습니다."
        />
      ) : (
        <div className="space-y-6">
          <ASHHeatmap
            data={heatmapData}
            isLoading={heatmapLoading}
            onTimeRangeChange={handleTimeRangeChange}
          />
          <SessionTable
            sessions={sessions}
            isLoading={sessionsLoading}
          />
        </div>
      )}
    </div>
  );
}
