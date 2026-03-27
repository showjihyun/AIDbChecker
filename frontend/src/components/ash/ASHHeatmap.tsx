// Spec: MVP-DASH-003 — ASH Wait Event heatmap (ECharts)
import { useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { subMinutes, subHours } from 'date-fns';
import { cn } from '@/lib/cn';
import { EmptyState } from '@/components/common/EmptyState';
import type { ASHHeatmapData } from '@/types/api';

interface ASHHeatmapProps {
  data: ASHHeatmapData | undefined;
  isLoading: boolean;
  onTimeRangeChange: (from: string, to: string) => void;
}

interface HeatmapPreset {
  label: string;
  value: string;
  getFrom: () => Date;
}

// Spec: FS-KPI-001 §4.5 — X축 시간 정책 (Metrics Timeline과 동일)
const heatmapPresets: HeatmapPreset[] = [
  { label: '5분 (1초)', value: '5m', getFrom: () => subMinutes(new Date(), 5) },
  { label: '15분 (1초)', value: '15m', getFrom: () => subMinutes(new Date(), 15) },
  { label: '30분 (1초)', value: '30m', getFrom: () => subMinutes(new Date(), 30) },
  { label: '1시간 (10초)', value: '1h', getFrom: () => subHours(new Date(), 1) },
  { label: '6시간 (1분)', value: '6h', getFrom: () => subHours(new Date(), 6) },
];

export function ASHHeatmap({ data, isLoading, onTimeRangeChange }: ASHHeatmapProps) {
  const [activePreset, setActivePreset] = useState('30m');

  const handlePresetClick = (preset: HeatmapPreset) => {
    setActivePreset(preset.value);
    const from = preset.getFrom();
    onTimeRangeChange(from.toISOString(), new Date().toISOString());
  };

  const option = useMemo(() => {
    if (!data || data.values.length === 0) return null;

    const heatmapData: [number, number, number][] = [];
    for (let yIdx = 0; yIdx < data.wait_event_types.length; yIdx++) {
      for (let xIdx = 0; xIdx < data.time_buckets.length; xIdx++) {
        const value = data.values[yIdx]?.[xIdx] ?? 0;
        if (value > 0) {
          heatmapData.push([xIdx, yIdx, value]);
        }
      }
    }

    const maxValue = heatmapData.reduce((max, d) => Math.max(max, d[2]), 1);

    return {
      backgroundColor: 'transparent',
      tooltip: {
        position: 'top' as const,
        backgroundColor: '#171f33',
        borderColor: 'rgba(62, 72, 80, 0.15)',
        borderWidth: 1,
        textStyle: { color: '#dae2fd', fontSize: 11, fontFamily: 'Inter' },
        formatter: (params: { value: [number, number, number] }) => {
          const [xIdx, yIdx, value] = params.value;
          const time = data.time_buckets[xIdx] ?? '';
          const eventType = data.wait_event_types[yIdx] ?? '';
          return `${eventType}<br/>${time}<br/>Sessions: <b>${value}</b>`;
        },
      },
      grid: {
        left: 120,
        right: 60,
        top: 8,
        bottom: 24,
      },
      xAxis: {
        type: 'category' as const,
        data: data.time_buckets,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: '#88929b',
          fontSize: 9,
          fontFamily: 'JetBrains Mono',
          interval: 'auto' as const,
        },
        splitArea: { show: false },
      },
      yAxis: {
        type: 'category' as const,
        data: data.wait_event_types,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: '#bec8d2',
          fontSize: 10,
          fontFamily: 'Inter',
        },
      },
      visualMap: {
        min: 0,
        max: maxValue,
        calculable: false,
        orient: 'vertical' as const,
        right: 0,
        top: 'center',
        itemWidth: 10,
        itemHeight: 80,
        textStyle: { color: '#88929b', fontSize: 9 },
        inRange: {
          // 어두운 배경에서 선명하게 보이는 그라데이션
          color: ['#1e293b', '#06b6d4', '#3b82f6', '#8b5cf6', '#ec4899'],
        },
      },
      series: [
        {
          type: 'heatmap' as const,
          data: heatmapData,
          emphasis: {
            itemStyle: {
              borderColor: '#89ceff',
              borderWidth: 1,
            },
          },
          itemStyle: {
            borderRadius: 2,
          },
        },
      ],
    };
  }, [data]);

  return (
    <div className="bg-surface-container rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-on-surface">
          ASH Wait Event Heatmap
        </h3>
        <div className="flex gap-1.5 flex-wrap" role="group" aria-label="Heatmap time range">
          {heatmapPresets.map((preset) => (
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
        <div className="h-[280px] bg-surface-container-high rounded-md animate-pulse" />
      ) : option ? (
        <ReactECharts
          option={option}
          style={{ height: 280 }}
          opts={{ renderer: 'canvas' }}
        />
      ) : (
        <div className="h-[280px] flex items-center justify-center rounded-md bg-surface-container-high/30">
          <EmptyState
            icon="grid_view"
            message="세션 데이터 없음"
            description="선택한 시간 범위에 활성 세션 데이터가 없습니다."
          />
        </div>
      )}
    </div>
  );
}
