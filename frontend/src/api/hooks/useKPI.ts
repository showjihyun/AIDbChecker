// Spec: FS-KPI-001 -- TanStack Query hook for DB KPI data
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/api/client';
import type { KPIResponse } from '@/types/kpi';

/**
 * Fetch 12 KPIs for a single instance.
 * Polls every 5 seconds for near-real-time updates.
 */
export function useInstanceKPI(instanceId: string | undefined) {
  return useQuery({
    queryKey: ['kpi', instanceId],
    queryFn: () =>
      apiClient.get<KPIResponse>(`/instances/${instanceId}/kpi`),
    enabled: !!instanceId,
    refetchInterval: 5_000,
    refetchIntervalInBackground: false,
    staleTime: 4_000,
  });
}
