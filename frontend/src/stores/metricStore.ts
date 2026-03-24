// Spec: MVP-DASH-002 — Real-time metric state via WebSocket
import { create } from 'zustand';
import type { MetricSample } from '@/types/api';

interface MetricState {
  latestMetrics: Record<string, MetricSample>;
  wsConnected: boolean;
  selectedInstanceId: string | null;
  setLatestMetric: (instanceId: string, metric: MetricSample) => void;
  setWsConnected: (connected: boolean) => void;
  setSelectedInstanceId: (id: string | null) => void;
}

export const useMetricStore = create<MetricState>((set) => ({
  latestMetrics: {},
  wsConnected: false,
  selectedInstanceId: null,

  setLatestMetric: (instanceId, metric) =>
    set((state) => ({
      latestMetrics: {
        ...state.latestMetrics,
        [instanceId]: metric,
      },
    })),

  setWsConnected: (connected) => set({ wsConnected: connected }),

  setSelectedInstanceId: (id) => set({ selectedInstanceId: id }),
}));
