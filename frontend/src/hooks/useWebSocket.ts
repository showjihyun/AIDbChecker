// Spec: WEBSOCKET_EVENTS_SPEC.md — Socket.io real-time metrics
import { useEffect, useRef } from 'react';
import { io, type Socket } from 'socket.io-client';
import { useMetricStore } from '@/stores/metricStore';

// When VITE_WS_URL is empty, connect to the current host (works with nginx proxy).
// Only truly skip if explicitly set to "disabled".
const WS_URL = import.meta.env.VITE_WS_URL ?? '';

export function useWebSocket() {
  const socketRef = useRef<Socket | null>(null);
  const setLatestMetric = useMetricStore((s) => s.setLatestMetric);
  const setWsConnected = useMetricStore((s) => s.setWsConnected);

  useEffect(() => {
    if (WS_URL === 'disabled') {
      return;
    }

    // Empty string = connect to current origin (relative path via nginx proxy)
    const baseUrl = WS_URL || undefined;
    const socket = io(baseUrl ? `${baseUrl}/ws/metrics` : '/ws/metrics', {
      path: '/socket.io',
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 2_000,
      reconnectionDelayMax: 15_000,
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      setWsConnected(true);
    });

    socket.on('disconnect', () => {
      setWsConnected(false);
    });

    socket.on('metric:update', (data: unknown) => {
      // Fix #5: Validate incoming data before updating store
      if (
        data &&
        typeof data === 'object' &&
        'instance_id' in data &&
        'metrics' in data
      ) {
        const metric = data as { instance_id: string; [key: string]: unknown };
        setLatestMetric(metric.instance_id, data as import('@/types/api').MetricSample);
      }
    });

    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
  }, [setLatestMetric, setWsConnected]);

  return socketRef;
}
