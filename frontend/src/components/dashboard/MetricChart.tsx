// Spec: MVP-DASH-002, FS-KPI-001 §4.5 — ECharts time-series for metrics
import { useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { subMinutes, subHours, subDays } from 'date-fns';
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

// Spec: FS-KPI-001 §4.5 — 프리셋 라벨은 시간 범위만 표시 (CloudWatch 스타일)
const timePresets: TimePreset[] = [
  { label: '5분', value: '5m', getFrom: () => subMinutes(new Date(), 5) },
  { label: '15분', value: '15m', getFrom: () => subMinutes(new Date(), 15) },
  { label: '1시간', value: '1h', getFrom: () => subHours(new Date(), 1) },
  { label: '6시간', value: '6h', getFrom: () => subHours(new Date(), 6) },
  { label: '24시간', value: '24h', getFrom: () => subDays(new Date(), 1) },
  { label: '7일', value: '7d', getFrom: () => subDays(new Date(), 7) },
];

/**
 * 균등 다운샘플링 — 시간 간격이 일정하게 유지되도록 추출.
 * 기존 filter(_, i % step) 대신 시간 기반 버킷팅.
 */
function downsample(sorted: MetricSample[], maxPoints: number): MetricSample[] {
  if (sorted.length <= maxPoints) return sorted;

  const first = new Date(sorted[0].sampled_at).getTime();
  const last = new Date(sorted[sorted.length - 1].sampled_at).getTime();
  const bucketSize = (last - first) / maxPoints;

  const result: MetricSample[] = [];
  let nextBucket = first;

  for (const sample of sorted) {
    const t = new Date(sample.sampled_at).getTime();
    if (t >= nextBucket) {
      result.push(sample);
      nextBucket = t + bucketSize;
    }
  }

  return result;
}

export function MetricChart({ data, isLoading, onTimeRangeChange }: MetricChartProps) {
  const [activePreset, setActivePreset] = useState('1h');

  const handlePresetClick = (preset: TimePreset) => {
    setActivePreset(preset.value);
    const from = preset.getFrom();
    onTimeRangeChange(from.toISOString(), new Date().toISOString());
  };

  const option = useMemo(() => {
    if (!data || data.length === 0) return null;

    const rawSorted = [...data].sort(
      (a, b) => new Date(a.sampled_at).getTime() - new Date(b.sampled_at).getTime()
    );

    // Spec: FS-KPI-001 §4.5 — CloudWatch 스타일: xAxis type='time'
    const maxPoints = (() => {
      switch (activePreset) {
        case '5m': return 60;
        case '15m': return 90;
        case '1h': return 120;
        case '6h': return 72;
        case '24h': return 72;
        case '7d': return 84;
        default: return 120;
      }
    })();

    const sorted = downsample(rawSorted, maxPoints);

    // time 타입 → [ISO timestamp, value] 쌍
    // Connections (gauge — gap 방지)
    let lastConn: number | null = null;
    const connData: [string, number | null][] = sorted.map((d) => {
      const v = d.metrics.numbackends ?? d.metrics.active_connections ?? null;
      if (v !== null) lastConn = v;
      return [d.sampled_at, lastConn];
    });

    // TPS (delta/sec — spike 방지 + gap 방지)
    const tpsData: [string, number | null][] = [[sorted[0].sampled_at, null]];
    let prevTPS: number | null = null;
    for (let i = 1; i < sorted.length; i++) {
      const curr = sorted[i];
      const prev = sorted[i - 1];
      const cVal = curr.metrics.xact_commit ?? curr.metrics.tps ?? null;
      const pVal = prev.metrics.xact_commit ?? prev.metrics.tps ?? null;

      if (cVal === null || pVal === null) {
        tpsData.push([curr.sampled_at, prevTPS]);
        continue;
      }
      const delta = cVal - pVal;
      const sec = (new Date(curr.sampled_at).getTime() - new Date(prev.sampled_at).getTime()) / 1000;
      if (sec <= 0 || delta < 0) {
        tpsData.push([curr.sampled_at, prevTPS]);
        continue;
      }
      let v = Math.round(delta / sec);
      if (prevTPS !== null && prevTPS > 0 && v > prevTPS * 10) v = prevTPS;
      prevTPS = v;
      tpsData.push([curr.sampled_at, v]);
    }

    // Buffer Hit Ratio (delta-based)
    const hitData: [string, number | null][] = [[sorted[0].sampled_at, null]];
    for (let i = 1; i < sorted.length; i++) {
      const d = sorted[i];
      const p = sorted[i - 1];
      const dHit = (d.metrics.blks_hit ?? 0) - (p.metrics.blks_hit ?? 0);
      const dRead = (d.metrics.blks_read ?? 0) - (p.metrics.blks_read ?? 0);
      const total = dHit + dRead;
      hitData.push([d.sampled_at, total <= 0 ? 100 : Math.round((dHit / total) * 10000) / 100]);
    }

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
        data: ['Hit Ratio', 'Connections', 'TPS/s'],
        textStyle: { color: '#bec8d2', fontSize: 11, fontFamily: 'Inter' },
        top: 0,
        right: 0,
        itemGap: 16,
      },
      grid: {
        left: 48,
        right: 16,
        top: 36,
        bottom: 28,
      },
      // CloudWatch 스타일: type='time' → ECharts가 범위에 맞춰 자동 레이블
      xAxis: {
        type: 'time' as const,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: '#88929b',
          fontSize: 10,
          fontFamily: 'JetBrains Mono',
          hideOverlap: true,
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
          axisLabel: { color: '#88929b', fontSize: 10, fontFamily: 'JetBrains Mono' },
          splitLine: { lineStyle: { color: 'rgba(62, 72, 80, 0.15)', type: 'dashed' as const } },
        },
        {
          type: 'value' as const,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { color: '#88929b', fontSize: 10, fontFamily: 'JetBrains Mono' },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: 'Hit Ratio',
          type: 'line' as const,
          data: hitData,
          smooth: true,
          symbol: 'none',
          connectNulls: true,
          itemStyle: { color: '#0ea5e9' },
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
          connectNulls: true,
          itemStyle: { color: '#f59e0b' },
          lineStyle: { width: 2, color: '#f59e0b' },
          areaStyle: {
            color: {
              type: 'linear' as const,
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(245, 158, 11, 0.12)' },
                { offset: 1, color: 'rgba(245, 158, 11, 0)' },
              ],
            },
          },
        },
        {
          name: 'TPS/s',
          type: 'line' as const,
          yAxisIndex: 1,
          data: tpsData,
          smooth: true,
          symbol: 'none',
          connectNulls: true,
          itemStyle: { color: '#4edea3' },
          lineStyle: { width: 2, color: '#4edea3' },
          areaStyle: {
            color: {
              type: 'linear' as const,
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(78, 222, 163, 0.12)' },
                { offset: 1, color: 'rgba(78, 222, 163, 0)' },
              ],
            },
          },
        },
      ],
    };
  }, [data, activePreset]);

  return (
    <div className="bg-surface-container rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-on-surface">
          Metrics Timeline
        </h3>
        <div className="flex gap-1.5 flex-wrap" role="group" aria-label="Time range selection">
          {timePresets.map((preset) => (
            <button
              key={preset.value}
              onClick={() => handlePresetClick(preset)}
              className={cn(
                'px-3 py-1.5 rounded-lg text-[11px] font-medium transition-colors duration-200 ease-out whitespace-nowrap',
                activePreset === preset.value
                  ? 'bg-primary text-on-primary shadow-sm'
                  : 'bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest'
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
