// Spec: FS-AI-TUNE-001 — Tuning Agent TanStack Query hooks
import { useQuery, useMutation } from '@tanstack/react-query';
import { apiClient } from '@/api/client';

// --- Types matching backend TuningResponse / TuningAction ---

export interface TuningAction {
  action_type: string;
  description: string;
  sql: string | null;
  risk_level: 'low' | 'medium' | 'high';
  estimated_impact: string;
}

export interface TuningResponse {
  instance_id: string;
  question: string;
  analysis: string;
  actions: TuningAction[];
  tools_used: string[];
  iterations: number;
  model_used: string;
  duration_ms: number;
}

export interface TuningRequest {
  instance_id: string;
  question: string;
  max_iterations?: number;
}

export interface TuningHistoryItem {
  id: string;
  instance_id: string;
  question: string;
  analysis: string;
  actions: TuningAction[];
  tools_used: string[];
  model_used: string;
  duration_ms: number;
  created_at: string;
}

// --- Keys ---

const TUNING_HISTORY_KEY = ['tuning', 'history'] as const;

// --- Hooks ---

/** POST /api/v1/tuning/analyze — run tuning agent analysis */
export function useTuningAnalyze() {
  return useMutation({
    mutationFn: (data: TuningRequest) =>
      apiClient.post<TuningResponse>('/tuning/analyze', data),
  });
}

/** GET /api/v1/tuning/history — fetch past analyses for an instance */
export function useTuningHistory(instanceId: string | undefined, limit = 20) {
  return useQuery({
    queryKey: [...TUNING_HISTORY_KEY, instanceId, limit],
    queryFn: () =>
      apiClient.get<{ items: TuningHistoryItem[]; total: number }>(
        '/tuning/history',
        {
          instance_id: instanceId!,
          limit: String(limit),
        }
      ),
    enabled: !!instanceId,
    staleTime: 60_000,
    select: (data) => data.items,
  });
}
