// Spec: MVP-DASH-003, MVP-COLLECT-004 — ASH hooks
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/api/client';
import type { ASHHeatmapData, WaitBreakdown, ActiveSession, TimeRange } from '@/types/api';

export function useASHSessions(instanceId: string | undefined, timeRange: TimeRange) {
  return useQuery({
    queryKey: ['ash', 'sessions', instanceId, timeRange.from, timeRange.to],
    queryFn: async () => {
      const res = await apiClient.get<{ items: ActiveSession[]; next_cursor: string | null; has_more: boolean }>(`/instances/${instanceId}/ash`, {
        from: timeRange.from,
        to: timeRange.to,
      });
      return res.items;
    },
    enabled: !!instanceId,
    staleTime: 5_000,
  });
}

export function useASHHeatmap(instanceId: string | undefined, timeRange: TimeRange) {
  return useQuery({
    queryKey: ['ash', 'heatmap', instanceId, timeRange.from, timeRange.to],
    queryFn: () =>
      apiClient.get<ASHHeatmapData>(`/instances/${instanceId}/ash/heatmap`, {
        from: timeRange.from,
        to: timeRange.to,
      }),
    enabled: !!instanceId,
    staleTime: 10_000,
  });
}

export function useWaitBreakdown(instanceId: string | undefined, timeRange: TimeRange) {
  return useQuery({
    queryKey: ['ash', 'wait-breakdown', instanceId, timeRange.from, timeRange.to],
    queryFn: () =>
      apiClient.get<WaitBreakdown[]>(`/instances/${instanceId}/ash/wait-breakdown`, {
        from: timeRange.from,
        to: timeRange.to,
      }),
    enabled: !!instanceId,
    staleTime: 10_000,
  });
}
