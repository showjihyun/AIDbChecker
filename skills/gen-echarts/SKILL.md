---
name: gen-echarts
description: Generate Apache ECharts chart components for the NeuralDB dashboard. Creates time-series charts, topology graphs, ASH heatmaps, resource bar charts, and wait event visualizations with the NeuralDB dark theme design tokens.
argument-hint: "[chart-type: timeseries|topology|heatmap|bar|pie|gauge]"
allowed-tools: Read, Write, Glob, Grep, Edit
---

# Generate ECharts Component

## Arguments
- Chart type: $ARGUMENTS

## Reference
- Read `docs/FRONTEND_DESIGN.md` for color tokens and design rules
- Read `docs/screen3_ash.html` for ASH heatmap reference
- Read `docs/screen1_topology.html` for topology map reference

## Output File
```
frontend/src/components/{category}/{ChartName}/{ChartName}.tsx
```

## NeuralDB ECharts Theme
```typescript
const neuralDBTheme = {
  backgroundColor: '#0b1326',
  textStyle: { color: '#dae2fd', fontFamily: 'Inter' },
  title: { textStyle: { fontFamily: 'Space Grotesk', color: '#dae2fd' } },
  color: ['#89ceff', '#d0bcff', '#4edea3', '#f59e0b', '#ffb4ab'],
  categoryAxis: {
    axisLine: { lineStyle: { color: '#3e4850' } },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
  },
  valueAxis: {
    axisLine: { lineStyle: { color: '#3e4850' } },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
  },
};
```

## Chart Types

### Time-Series (Metrics)
- Line/Area chart with zoom slider
- Auto-refresh via WebSocket
- Anomaly markers (vertical lines + annotation)
- Schema change events overlay

### Topology (ECharts Graph)
- Force-directed or custom layout
- Node types: App(token), LB(alt_route), DB(database), Infra(cloud)
- Edge colors by status (healthy=tertiary, warning=amber, error=error)
- Hover tooltip with latency/status details

### ASH Heatmap
- Grid heatmap: X=time, Y=wait category
- Color scale: surface-variant → sky → orange → error
- Click drill-down to session list

### Resource Bar
- Vertical bar chart with AI baseline overlay (dashed line)
- Spike highlight with tooltip

## Component Pattern
```tsx
import { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';

export function {ChartName}({ data, ...props }: {ChartName}Props) {
  const chartRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!chartRef.current) return;
    instanceRef.current = echarts.init(chartRef.current, neuralDBTheme);
    return () => instanceRef.current?.dispose();
  }, []);

  useEffect(() => {
    instanceRef.current?.setOption(buildOption(data));
  }, [data]);

  return <div ref={chartRef} className="w-full h-full" />;
}
```

## Rules
- Use tree-shakeable ECharts imports (`echarts/core`)
- Dispose chart instance on unmount
- Handle window resize with ResizeObserver
- Use design token colors, never hardcode
- Tooltips match glass-panel style (dark bg + blur)
- All transitions `ease-out`
