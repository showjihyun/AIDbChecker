// Spec: WEBSOCKET_EVENTS_SPEC.md — Socket.io real-time metrics
import { useEffect, useRef } from 'react';
import { io, type Socket } from 'socket.io-client';
import { useMetricStore } from '@/stores/metricStore';
import type { MetricSample } from '@/types/api';

const WS_URL = import.meta.env.VITE_WS_URL ?? '';

export function useWebSocket() {
  const socketRef = useRef<Socket | null>(null);
  const setLatestMetric = useMetricStore((s) => s.setLatestMetric);
  const setWsConnected = useMetricStore((s) => s.setWsConnected);

  useEffect(() => {
    const socket = io(WS_URL, {
      path: '/socket.io',
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 1_000,
      reconnectionDelayMax: 5_000,
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      setWsConnected(true);
    });

    socket.on('disconnect', () => {
      setWsConnected(false);
    });

    socket.on('metric:update', (data: MetricSample) => {
      setLatestMetric(data.instance_id, data);
    });

    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
  }, [setLatestMetric, setWsConnected]);

  return socketRef;
}
