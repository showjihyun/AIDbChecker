// Spec: MVP-DASH-002, FS-KPI-001 §4.5 — ECharts time-series for metrics
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

// Spec: FS-KPI-001 §4.5 — X축 시간 정책 (해상도 표시)
const timePresets: TimePreset[] = [
  { label: '5분 (1초)', value: '5m', getFrom: () => subMinutes(new Date(), 5) },
  { label: '15분 (1초)', value: '15m', getFrom: () => subMinutes(new Date(), 15) },
  { label: '1시간 (10초)', value: '1h', getFrom: () => subHours(new Date(), 1) },
  { label: '6시간 (1분)', value: '6h', getFrom: () => subHours(new Date(), 6) },
  { label: '24시간 (20분)', value: '24h', getFrom: () => subDays(new Date(), 1) },
  { label: '7일 (2시간)', value: '7d', getFrom: () => subDays(new Date(), 7) },
];

// Spec: FS-KPI-001 §4.5 — 프리셋별 차트 설정
interface ChartConfig {
  maxPoints: number;
  format: string;
  rotate: number;
}

function getChartConfig(preset: string): ChartConfig {
  switch (preset) {
    case '5m':  return { maxPoints: 60,  format: 'HH:mm:ss', rotate: 0  };
    case '15m': return { maxPoints: 90,  format: 'HH:mm:ss', rotate: 0  };
    case '1h':  return { maxPoints: 120, format: 'HH:mm',    rotate: 0  };
    case '6h':  return { maxPoints: 72,  format: 'HH:mm',    rotate: 0  };
    case '24h': return { maxPoints: 72,  format: 'HH:mm',    rotate: 35 };
    case '7d':  return { maxPoints: 84,  format: 'MM/dd HH', rotate: 35 };
    default:    return { maxPoints: 120, format: 'HH:mm',    rotate: 0  };
  }
}

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

/**
 * TPS 계산 — 튀는 값(spike) 방지:
 * 1. timeDiff가 0이면 skip
 * 2. delta가 음수면 counter reset → skip
 * 3. TPS가 비정상적으로 높으면 (이전 값의 10배 초과) → 이전 값으로 클램핑
 */
function computeTPS(sorted: MetricSample[]): (number | null)[] {
  const tps: (number | null)[] = [null]; // 첫 포인트는 delta 계산 불가
  let prevValidTPS: number | null = null;

  for (let i = 1; i < sorted.length; i++) {
    const curr = sorted[i];
    const prev = sorted[i - 1];

    const currCommit = curr.metrics.xact_commit ?? curr.metrics.tps ?? null;
    const prevCommit = prev.metrics.xact_commit ?? prev.metrics.tps ?? null;

    // 값이 없으면 null (gap 없이 이전 값 연결)
    if (currCommit === null || prevCommit === null) {
      tps.push(prevValidTPS); // 끊김 방지: 이전 유효값 유지
      continue;
    }

    const delta = currCommit - prevCommit;
    const timeDiffSec =
      (new Date(curr.sampled_at).getTime() - new Date(prev.sampled_at).getTime()) / 1000;

    // 비정상 케이스
    if (timeDiffSec <= 0 || delta < 0) {
      tps.push(prevValidTPS); // counter reset → 이전 값 유지
      continue;
    }

    let value = Math.round(delta / timeDiffSec);

    // Spike 방지: 이전 유효값의 10배 초과 시 클램핑
    if (prevValidTPS !== null && prevValidTPS > 0 && value > prevValidTPS * 10) {
      value = prevValidTPS; // 비정상 spike → 이전 값으로
    }

    prevValidTPS = value;
    tps.push(value);
  }

  return tps;
}

/**
 * Connection 계산 — null gap 방지:
 * 값이 없으면 이전 유효값을 유지 (끊김 방지)
 */
function computeConnections(sorted: MetricSample[]): (number | null)[] {
  let lastValid: number | null = null;

  return sorted.map((d) => {
    const value = d.metrics.numbackends ?? d.metrics.active_connections ?? null;
    if (value !== null) {
      lastValid = value;
      return value;
    }
    return lastValid; // 값 없으면 이전 값 유지 (gap 방지)
  });
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

    const chartConfig = getChartConfig(activePreset);

    // 시간 기반 균등 다운샘플링 (불균일 간격 방지)
    const sorted = downsample(rawSorted, chartConfig.maxPoints);

    const timestamps = sorted.map((d) => format(new Date(d.sampled_at), chartConfig.format));

    // X축 레이블 간격: 데이터 수 기반으로 ~12개 레이블 목표
    const labelInterval = Math.max(1, Math.floor(sorted.length / 12) - 1);

    // Connections (gauge — gap 방지)
    const connData = computeConnections(sorted);

    // TPS (delta/sec — spike 방지 + gap 방지)
    const tpsData = computeTPS(sorted);

    // Buffer Hit Ratio (delta-based)
    const hitRatioData = sorted.map((d, i) => {
      if (i === 0) return null;
      const prev = sorted[i - 1];
      const deltaHit = (d.metrics.blks_hit ?? 0) - (prev.metrics.blks_hit ?? 0);
      const deltaRead = (d.metrics.blks_read ?? 0) - (prev.metrics.blks_read ?? 0);
      const total = deltaHit + deltaRead;
      if (total <= 0) return 100;
      return Math.round((deltaHit / total) * 10000) / 100;
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
        bottom: chartConfig.rotate > 0 ? 48 : 24,
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
          interval: labelInterval,
          rotate: chartConfig.rotate,
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
          data: hitRatioData,
          smooth: true,
          symbol: 'none',
          connectNulls: true,
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
          connectNulls: true, // null이 있어도 선 이어짐
          lineStyle: { width: 2, color: '#f59e0b' },
        },
        {
          name: 'TPS/s',
          type: 'line' as const,
          yAxisIndex: 1,
          data: tpsData,
          smooth: true,
          symbol: 'none',
          connectNulls: true, // null이 있어도 선 이어짐
          lineStyle: { width: 2, color: '#4edea3' },
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
