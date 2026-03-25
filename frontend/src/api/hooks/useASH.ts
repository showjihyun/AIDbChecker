// Spec: MVP-DASH-003, MVP-COLLECT-004 — ASH hooks
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/api/client';
import type { ASHHeatmapData, WaitBreakdown, ActiveSession, TimeRange } from '@/types/api';

export function useASHSessions(instanceId: string | undefined, timeRange: TimeRange) {
  return useQuery({
    queryKey: ['ash', 'sessions', instanceId, timeRange.from, timeRange.to],
    queryFn: async () => {
      const res = await apiClient.get<{ items: ActiveSession[]; next_cursor: string | null; has_more: boolean }>(`/instances/${instanceId}/ash`, {
        from_ts: timeRange.from,
        to_ts: timeRange.to,
      });
      return res.items;
    },
    enabled: !!instanceId,
    staleTime: 5_000,
  });
}

/** Raw bucket from the backend API */
interface HeatmapBucket {
  bucket_start: string;
  wait_event_type: string;
  count: number;
}

interface HeatmapApiResponse {
  instance_id: string;
  buckets: HeatmapBucket[];
  bucket_interval_seconds: number;
}

/** Format timestamp to HH:MM:SS label */
function toTimeLabel(isoString: string): string {
  const t = new Date(isoString);
  return `${String(t.getHours()).padStart(2, '0')}:${String(t.getMinutes()).padStart(2, '0')}:${String(t.getSeconds()).padStart(2, '0')}`;
}

/** Transform flat bucket list into the 2D matrix format the ASHHeatmap component expects */
function transformHeatmapData(raw: HeatmapApiResponse): ASHHeatmapData {
  const timeSet = new Set<string>();
  const eventSet = new Set<string>();

  for (const b of raw.buckets) {
    timeSet.add(toTimeLabel(b.bucket_start));
    eventSet.add(b.wait_event_type);
  }

  const time_buckets = [...timeSet].sort();
  const wait_event_types = [...eventSet].sort();
  const timeIndex = new Map(time_buckets.map((t, i) => [t, i]));
  const eventIndex = new Map(wait_event_types.map((e, i) => [e, i]));

  // Initialize 2D matrix [eventType][timeBucket]
  const values: number[][] = wait_event_types.map(() => new Array(time_buckets.length).fill(0));

  for (const b of raw.buckets) {
    const xi = timeIndex.get(toTimeLabel(b.bucket_start));
    const yi = eventIndex.get(b.wait_event_type);
    if (xi != null && yi != null) {
      values[yi][xi] = b.count;
    }
  }

  return { time_buckets, wait_event_types, values };
}

export function useASHHeatmap(instanceId: string | undefined, timeRange: TimeRange) {
  return useQuery({
    queryKey: ['ash', 'heatmap', instanceId, timeRange.from, timeRange.to],
    queryFn: async () => {
      const raw = await apiClient.get<HeatmapApiResponse>(`/instances/${instanceId}/ash/heatmap`, {
        from_ts: timeRange.from,
        to_ts: timeRange.to,
      });
      return transformHeatmapData(raw);
    },
    enabled: !!instanceId,
    staleTime: 10_000,
  });
}

export function useWaitBreakdown(instanceId: string | undefined, timeRange: TimeRange) {
  return useQuery({
    queryKey: ['ash', 'wait-breakdown', instanceId, timeRange.from, timeRange.to],
    queryFn: async () => {
      const res = await apiClient.get<{ instance_id: string; total_samples: number; breakdown: WaitBreakdown[] }>(`/instances/${instanceId}/ash/wait-breakdown`, {
        from_ts: timeRange.from,
        to_ts: timeRange.to,
      });
      return res.breakdown;
    },
    enabled: !!instanceId,
    staleTime: 10_000,
  });
}
