// Spec: MVP-DASH-002, MVP-COLLECT-001 — Metrics hooks (1s refetch for latest)
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/api/client';
import type { MetricSample, TimeRange } from '@/types/api';

export function useMetrics(instanceId: string | undefined, timeRange: TimeRange) {
  return useQuery({
    queryKey: ['metrics', instanceId, timeRange.from, timeRange.to],
    queryFn: async () => {
      const res = await apiClient.get<{ items: MetricSample[]; next_cursor: string | null; has_more: boolean }>(`/instances/${instanceId}/metrics`, {
        from: timeRange.from,
        to: timeRange.to,
      });
      return res.items;
    },
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

/**
 * Latest metrics response from GET /instances/{id}/metrics/latest.
 * Contains hot/warm/cold metric snapshots.
 */
interface LatestMetricsResponse {
  instance_id: string;
  hot: MetricSample | null;
  warm: MetricSample | null;
  cold: MetricSample | null;
}

/**
 * Fetch latest metrics for ALL given instance IDs via REST API polling.
 * This is the fallback when WebSocket is disconnected.
 * Polls every 5 seconds (not 1s, to reduce API load as fallback).
 */
export function useAllInstancesLatestMetrics(
  instanceIds: string[],
  wsConnected: boolean
) {
  return useQuery({
    queryKey: ['metrics', 'latest-all', ...instanceIds],
    queryFn: async () => {
      const results: Record<string, MetricSample> = {};
      await Promise.all(
        instanceIds.map(async (id) => {
          try {
            const res = await apiClient.get<LatestMetricsResponse>(
              `/instances/${id}/metrics/latest`
            );
            if (res.hot) {
              results[id] = res.hot;
            }
          } catch {
            // Skip failed instances
          }
        })
      );
      return results;
    },
    enabled: instanceIds.length > 0 && !wsConnected,
    refetchInterval: 5_000,
    staleTime: 3_000,
  });
}
