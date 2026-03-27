// Spec: FS-AI-013 AC-6, FE-COMP-001
// AI Health dashboard panel — LLM pipeline metrics visualization

import { useQuery } from '@tanstack/react-query';
import { ConfidenceBadge } from './ConfidenceBadge';
import { cn } from '@/lib/cn';
import { apiClient } from '@/api/client';

interface LLMSummary {
  total_calls: number;
  total_tokens: number;
  avg_latency_ms: number;
  total_cost: number;
  hallucination_rate: number;
  period_from: string | null;
  period_to: string | null;
}

interface DriftResult {
  drift_score: number;
  is_drifting: boolean;
  details: string;
}

function MetricCard({
  label,
  value,
  unit,
  variant = 'neutral',
}: {
  label: string;
  value: string | number;
  unit?: string;
  variant?: 'good' | 'warning' | 'critical' | 'neutral';
}) {
  const colors = {
    good: 'border-tertiary/30 text-tertiary',
    warning: 'border-amber-500/30 text-amber-500',
    critical: 'border-error/30 text-error',
    neutral: 'border-white/5 text-on-surface',
  };

  return (
    <div className={cn('bg-surface-container rounded-xl p-4 border', colors[variant])}>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-on-surface-variant">
        {label}
      </p>
      <p className="text-2xl font-headline font-bold mt-1">
        {value}
        {unit && <span className="text-xs font-normal text-on-surface-variant ml-1">{unit}</span>}
      </p>
    </div>
  );
}

export function LLMObservabilityPanel() {
  const { data: summary, isLoading: summaryLoading } = useQuery<LLMSummary>({
    queryKey: ['llm-observability', 'summary'],
    queryFn: () => apiClient.get('/llm-observability/summary'),
    refetchInterval: 30_000,
  });

  const { data: drift } = useQuery<DriftResult>({
    queryKey: ['llm-observability', 'drift'],
    queryFn: () => apiClient.get('/llm-observability/drift'),
    refetchInterval: 60_000,
  });

  if (summaryLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 animate-pulse">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-surface-container rounded-xl p-4 h-20" />
        ))}
      </div>
    );
  }

  const hallucinationVariant =
    (summary?.hallucination_rate ?? 0) > 0.15
      ? 'critical'
      : (summary?.hallucination_rate ?? 0) > 0.05
        ? 'warning'
        : 'good';

  const latencyVariant =
    (summary?.avg_latency_ms ?? 0) > 10000
      ? 'critical'
      : (summary?.avg_latency_ms ?? 0) > 5000
        ? 'warning'
        : 'good';

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-headline font-semibold text-secondary">
          AI Pipeline Health
        </h3>
        {drift?.is_drifting && (
          <span className="text-[10px] font-bold text-error bg-error/10 px-2 py-0.5 rounded-full">
            Model Drift Detected
          </span>
        )}
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard
          label="Total Calls"
          value={summary?.total_calls ?? 0}
        />
        <MetricCard
          label="Total Tokens"
          value={((summary?.total_tokens ?? 0) / 1000).toFixed(1)}
          unit="K"
        />
        <MetricCard
          label="Avg Latency"
          value={Math.round(summary?.avg_latency_ms ?? 0)}
          unit="ms"
          variant={latencyVariant}
        />
        <MetricCard
          label="Cost"
          value={`$${(summary?.total_cost ?? 0).toFixed(4)}`}
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <MetricCard
          label="Hallucination Rate"
          value={((summary?.hallucination_rate ?? 0) * 100).toFixed(1)}
          unit="%"
          variant={hallucinationVariant}
        />
        {drift && (
          <MetricCard
            label="Drift Score"
            value={drift.drift_score.toFixed(3)}
            variant={drift.is_drifting ? 'critical' : 'good'}
          />
        )}
      </div>
    </div>
  );
}
