// Spec: MVP-DASH-001, API_SPEC.md — Instance CRUD hooks
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/api/client';
import type {
  Instance,
  CreateInstanceRequest,
  TestConnectionRequest,
  TestConnectionResponse,
} from '@/types/api';

const INSTANCES_KEY = ['instances'] as const;

export function useInstances() {
  return useQuery({
    queryKey: INSTANCES_KEY,
    queryFn: () => apiClient.get<Instance[]>('/instances'),
    staleTime: 30_000,
  });
}

export function useInstance(id: string | undefined) {
  return useQuery({
    queryKey: [...INSTANCES_KEY, id],
    queryFn: () => apiClient.get<Instance>(`/instances/${id}`),
    enabled: !!id,
    staleTime: 30_000,
  });
}

export function useCreateInstance() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateInstanceRequest) =>
      apiClient.post<Instance>('/instances', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: INSTANCES_KEY });
    },
  });
}

export function useUpdateInstance() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<CreateInstanceRequest> }) =>
      apiClient.put<Instance>(`/instances/${id}`, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: [...INSTANCES_KEY, variables.id] });
      queryClient.invalidateQueries({ queryKey: INSTANCES_KEY });
    },
  });
}

export function useDeleteInstance() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/instances/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: INSTANCES_KEY });
    },
  });
}

export function useTestConnection() {
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: TestConnectionRequest }) =>
      apiClient.post<TestConnectionResponse>(
        `/instances/${id}/test-connection`,
        data
      ),
  });
}
