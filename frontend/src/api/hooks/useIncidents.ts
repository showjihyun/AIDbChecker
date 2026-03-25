// Spec: FS-DASH-004 — Incident CRUD hooks
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/api/client';
import type {
  Incident,
  IncidentListResponse,
  IncidentFilters,
  IncidentStatus,
} from '@/types/api';

const INCIDENTS_KEY = ['incidents'] as const;

export function useIncidents(filters?: IncidentFilters) {
  return useQuery({
    queryKey: [...INCIDENTS_KEY, filters],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (filters?.severity) params.severity = filters.severity;
      if (filters?.status) params.status = filters.status;
      if (filters?.instance_id) params.instance_id = filters.instance_id;
      if (filters?.limit) params.limit = String(filters.limit);
      if (filters?.cursor) params.cursor = filters.cursor;

      const res = await apiClient.get<IncidentListResponse>('/incidents', params);
      return res;
    },
    staleTime: 10_000,
    refetchInterval: 15_000,
  });
}

export function useIncident(id: string | undefined) {
  return useQuery({
    queryKey: [...INCIDENTS_KEY, id],
    queryFn: () => apiClient.get<Incident>(`/incidents/${id}`),
    enabled: !!id,
    staleTime: 10_000,
  });
}

export function useUpdateIncidentStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: IncidentStatus }) =>
      apiClient.put<Incident>(`/incidents/${id}/status`, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: INCIDENTS_KEY });
    },
  });
}
