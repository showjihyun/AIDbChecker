// Spec: FS-KPI-001 -- TanStack Query hook for DB KPI data
import { useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/api/client';
import type { KPIResponse, KPIAdvisory } from '@/types/kpi';
import { useNotificationStore } from '@/stores/notificationStore';
import { useToastStore } from '@/components/common/Toast';

/**
 * Fetch 12 KPIs for a single instance.
 * Polls every 5 seconds for near-real-time updates.
 * Processes advisories into notifications and toasts.
 */
export function useInstanceKPI(
  instanceId: string | undefined,
  instanceName?: string
) {
  const addNotification = useNotificationStore((s) => s.addNotification);
  const addToast = useToastStore((s) => s.addToast);
  // Track advisories already shown as toasts to avoid repeats across polls
  const shownAdvisoriesRef = useRef<Set<string>>(new Set());

  const query = useQuery({
    queryKey: ['kpi', instanceId],
    queryFn: () =>
      apiClient.get<KPIResponse>(`/instances/${instanceId}/kpi`),
    enabled: !!instanceId,
    refetchInterval: 5_000,
    refetchIntervalInBackground: false,
    staleTime: 4_000,
  });

  useEffect(() => {
    const advisories = query.data?.advisories;
    if (!advisories || advisories.length === 0) return;

    advisories.forEach((advisory: KPIAdvisory) => {
      // Add to notification store (deduplication handled inside)
      const isNew = addNotification({
        level: advisory.level,
        title: advisory.title,
        message: advisory.message,
        action: advisory.action ?? undefined,
        instanceName,
      });

      // Show toast only if it was actually added (not a duplicate)
      const toastKey = `${advisory.title}:${instanceName ?? ''}`;
      if (isNew && !shownAdvisoriesRef.current.has(toastKey)) {
        shownAdvisoriesRef.current.add(toastKey);
        addToast({
          level: advisory.level,
          title: advisory.title,
          message: advisory.message,
        });
      }
    });
  }, [query.data?.advisories, addNotification, addToast, instanceName]);

  return query;
}
