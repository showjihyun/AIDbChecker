// Spec: MVP-DASH-002 — ECharts time-series for CPU, Connections, TPS
import { useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { format, subMinutes, subHours, subDays } from 'date-fns';
import { cn } from '@/lib/cn';
import { EmptyState } from '@/components/common/EmptyState';
import type { MetricSample } from '@/types/api';

interface MetricChartProps {
  data: MetricSample[] | undefined;
  isLoading: boolean;
  onTimeRangeChange: (from: string, to: string) => void;
}

interface TimePreset {
  label: string;
  value: string;
  getFrom: () => Date;
}

const timePresets: TimePreset[] = [
  { label: '15m', value: '15m', getFrom: () => subMinutes(new Date(), 15) },
  { label: '1h', value: '1h', getFrom: () => subHours(new Date(), 1) },
  { label: '6h', value: '6h', getFrom: () => subHours(new Date(), 6) },
  { label: '24h', value: '24h', getFrom: () => subDays(new Date(), 1) },
  { label: '7d', value: '7d', getFrom: () => subDays(new Date(), 7) },
];

export function MetricChart({ data, isLoading, onTimeRangeChange }: MetricChartProps) {
  const [activePreset, setActivePreset] = useState('1h');

  const handlePresetClick = (preset: TimePreset) => {
    setActivePreset(preset.value);
    const from = preset.getFrom();
    onTimeRangeChange(from.toISOString(), new Date().toISOString());
  };

  const option = useMemo(() => {
    if (!data || data.length === 0) return null;

    // Sort by time ascending for delta calculation
    const sorted = [...data].sort(
      (a, b) => new Date(a.sampled_at).getTime() - new Date(b.sampled_at).getTime()
    );

    const timestamps = sorted.map((d) => format(new Date(d.sampled_at), 'HH:mm:ss'));

    // Connections: numbackends is a gauge (current value), not a counter
    const connData = sorted.map((d) => d.metrics.numbackends ?? d.metrics.active_connections ?? null);

    // TPS: xact_commit is a cumulative counter — compute delta per second
    const tpsData = sorted.map((d, i) => {
      if (i === 0) return null; // no previous sample to diff
      const prev = sorted[i - 1];
      const currCommit = d.metrics.xact_commit ?? d.metrics.tps ?? 0;
      const prevCommit = prev.metrics.xact_commit ?? prev.metrics.tps ?? 0;
      const timeDiffSec =
        (new Date(d.sampled_at).getTime() - new Date(prev.sampled_at).getTime()) / 1000;
      if (timeDiffSec <= 0) return null;
      return Math.round((currCommit - prevCommit) / timeDiffSec);
    });

    // Buffer Hit Ratio: blks_hit / (blks_hit + blks_read) * 100 — gauge per sample
    const hitRatioData = sorted.map((d) => {
      const hit = d.metrics.blks_hit ?? 0;
      const read = d.metrics.blks_read ?? 0;
      if (hit + read === 0) return null;
      return Math.round((hit / (hit + read)) * 10000) / 100; // 2 decimal places
    });

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis' as const,
        backgroundColor: '#171f33',
        borderColor: 'rgba(62, 72, 80, 0.15)',
        borderWidth: 1,
        textStyle: { color: '#dae2fd', fontSize: 12, fontFamily: 'Inter' },
        axisPointer: { type: 'cross' as const, lineStyle: { color: '#3e4850' } },
      },
      legend: {
        data: ['Hit Ratio %', 'Connections', 'TPS/s'],
        textStyle: { color: '#bec8d2', fontSize: 11, fontFamily: 'Inter' },
        top: 0,
        right: 0,
        itemGap: 16,
      },
      grid: {
        left: 48,
        right: 16,
        top: 36,
        bottom: 24,
      },
      xAxis: {
        type: 'category' as const,
        data: timestamps,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: '#88929b',
          fontSize: 10,
          fontFamily: 'JetBrains Mono',
        },
        splitLine: { show: false },
      },
      yAxis: [
        {
          type: 'value' as const,
          name: '%',
          nameTextStyle: { color: '#88929b', fontSize: 10 },
          max: 100,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: {
            color: '#88929b',
            fontSize: 10,
            fontFamily: 'JetBrains Mono',
          },
          splitLine: {
            lineStyle: { color: 'rgba(62, 72, 80, 0.15)', type: 'dashed' as const },
          },
        },
        {
          type: 'value' as const,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: {
            color: '#88929b',
            fontSize: 10,
            fontFamily: 'JetBrains Mono',
          },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: 'Hit Ratio %',
          type: 'line' as const,
          data: hitRatioData,
          smooth: true,
          symbol: 'none',
          lineStyle: { width: 2, color: '#0ea5e9' },
          areaStyle: {
            color: {
              type: 'linear' as const,
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(14, 165, 233, 0.15)' },
                { offset: 1, color: 'rgba(14, 165, 233, 0)' },
              ],
            },
          },
        },
        {
          name: 'Connections',
          type: 'line' as const,
          yAxisIndex: 1,
          data: connData,
          smooth: true,
          symbol: 'none',
          lineStyle: { width: 2, color: '#f59e0b' },
        },
        {
          name: 'TPS/s',
          type: 'line' as const,
          yAxisIndex: 1,
          data: tpsData,
          smooth: true,
          symbol: 'none',
          lineStyle: { width: 2, color: '#4edea3' },
        },
      ],
    };
  }, [data]);

  return (
    <div className="bg-surface-container rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-on-surface">
          Metrics Timeline
        </h3>
        <div className="flex gap-1" role="group" aria-label="Time range selection">
          {timePresets.map((preset) => (
            <button
              key={preset.value}
              onClick={() => handlePresetClick(preset)}
              className={cn(
                'px-2.5 py-1 rounded-md text-xs font-medium transition-colors duration-200 ease-out',
                activePreset === preset.value
                  ? 'bg-primary-container text-on-primary'
                  : 'text-on-surface-variant hover:bg-surface-container-high'
              )}
              aria-pressed={activePreset === preset.value}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="h-[300px] bg-surface-container-high rounded-md animate-pulse" />
      ) : option ? (
        <ReactECharts
          option={option}
          style={{ height: 300 }}
          opts={{ renderer: 'canvas' }}
          theme="dark"
        />
      ) : (
        <div className="h-[300px] flex items-center justify-center rounded-md bg-surface-container-high/30">
          <EmptyState
            icon="show_chart"
            message="수집 대기 중..."
            description="인스턴스를 선택하면 실시간 메트릭 차트가 표시됩니다."
          />
        </div>
      )}
    </div>
  );
}
