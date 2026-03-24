// Spec: WEBSOCKET_EVENTS_SPEC.md — Socket.io real-time metrics
import { useEffect, useRef } from 'react';
import { io, type Socket } from 'socket.io-client';
import { useMetricStore } from '@/stores/metricStore';

const WS_URL = import.meta.env.VITE_WS_URL ?? '';

export function useWebSocket() {
  const socketRef = useRef<Socket | null>(null);
  const setLatestMetric = useMetricStore((s) => s.setLatestMetric);
  const setWsConnected = useMetricStore((s) => s.setWsConnected);

  useEffect(() => {
    // Skip WebSocket connection if no backend URL configured
    if (!WS_URL) {
      return;
    }

    const socket = io(`${WS_URL}/ws/metrics`, {
      path: '/socket.io',
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 2_000,
      reconnectionDelayMax: 10_000,
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
