// Spec: FS-AI-LLM-001 — TanStack Query hooks for LLM provider settings
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/api/client';

// --- Types ---

export interface LLMSettingsResponse {
  provider: string;
  model: string;
  ollama_base_url: string;
  has_openai_key: boolean;
  has_anthropic_key: boolean;
  has_google_key: boolean;
}

export interface LLMSettingsUpdate {
  provider: 'ollama' | 'openai' | 'anthropic' | 'google';
  model: string;
  openai_api_key?: string | null;
  anthropic_api_key?: string | null;
  google_api_key?: string | null;
}

export interface ProviderInfo {
  name: string;
  display_name: string;
  available: boolean;
  models: string[];
}

export interface OllamaModel {
  name: string;
  size: string;
  modified_at: string;
}

export interface LLMTestRequest {
  provider: string;
  model: string;
}

export interface LLMTestResponse {
  success: boolean;
  response: string | null;
  latency_ms: number;
  error: string | null;
}

// --- Query Keys ---

const LLM_SETTINGS_KEY = ['llm-settings'] as const;
const LLM_PROVIDERS_KEY = ['llm-providers'] as const;
const OLLAMA_MODELS_KEY = ['ollama-models'] as const;

// --- Hooks ---

export function useLLMSettings() {
  return useQuery({
    queryKey: LLM_SETTINGS_KEY,
    queryFn: () => apiClient.get<LLMSettingsResponse>('/settings/llm'),
    staleTime: 60_000,
  });
}

export function useLLMProviders() {
  return useQuery({
    queryKey: LLM_PROVIDERS_KEY,
    queryFn: () => apiClient.get<ProviderInfo[]>('/settings/llm/providers'),
    staleTime: 60_000,
  });
}

export function useOllamaModels() {
  return useQuery({
    queryKey: OLLAMA_MODELS_KEY,
    queryFn: () => apiClient.get<OllamaModel[]>('/settings/llm/ollama-models'),
    staleTime: 30_000,
  });
}

export function useUpdateLLMSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: LLMSettingsUpdate) =>
      apiClient.put<LLMSettingsResponse>('/settings/llm', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: LLM_SETTINGS_KEY });
      queryClient.invalidateQueries({ queryKey: LLM_PROVIDERS_KEY });
    },
  });
}

export function useTestLLM() {
  return useMutation({
    mutationFn: (data: LLMTestRequest) =>
      apiClient.post<LLMTestResponse>('/settings/llm/test', data),
  });
}
