// Spec: MVP-DASH-002, MVP-COLLECT-001 — Metrics hooks (1s refetch for latest)
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/api/client';
import type { MetricSample, TimeRange } from '@/types/api';

export function useMetrics(instanceId: string | undefined, timeRange: TimeRange) {
  return useQuery({
    queryKey: ['metrics', instanceId, timeRange.from, timeRange.to],
    queryFn: () =>
      apiClient.get<MetricSample[]>(`/instances/${instanceId}/metrics`, {
        from: timeRange.from,
        to: timeRange.to,
      }),
    enabled: !!instanceId,
    staleTime: 5_000,
  });
}

export function useLatestMetrics(instanceId: string | undefined) {
  return useQuery({
    queryKey: ['metrics', 'latest', instanceId],
    queryFn: () =>
      apiClient.get<MetricSample>(`/instances/${instanceId}/metrics/latest`),
    enabled: !!instanceId,
    refetchInterval: 1_000,
    refetchIntervalInBackground: false,
    staleTime: 0,
  });
}
