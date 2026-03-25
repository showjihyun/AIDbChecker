// Spec: MVP-DASH-005 — System Health status display
import { useQuery } from '@tanstack/react-query';
import { cn } from '@/lib/cn';
import { apiClient } from '@/api/client';
import { Badge } from '@/components/common/Badge';
import type { ComponentHealth } from '@/types/api';

function ComponentStatus({
  name,
  component,
}: {
  name: string;
  component: ComponentHealth;
}) {
  const variant =
    component.status === 'up'
      ? 'healthy'
      : component.status === 'degraded'
        ? 'warning'
        : 'critical';

  const statusLabel =
    component.status === 'up'
      ? 'UP'
      : component.status === 'degraded'
        ? 'DEGRADED'
        : 'DOWN';

  return (
    <div className="flex items-center justify-between py-2">
      <span className="text-xs font-medium text-on-surface-variant">{name}</span>
      <div className="flex items-center gap-2">
        {component.latency_ms != null && (
          <span className="text-[10px] font-mono text-outline tabular-nums">
            {component.latency_ms}ms
          </span>
        )}
        <Badge variant={variant} dot>
          {statusLabel}
        </Badge>
      </div>
    </div>
  );
}

/**
 * Actual API response: {"db":"up","valkey":"up","celery":"up","status":"healthy"}
 * Simple flat structure — not the nested components format.
 */
interface HealthApiResponse {
  db: string;
  valkey: string;
  celery: string;
  kafka?: string;
  status: string;
}

export function SystemHealthPanel() {
  const { data, isLoading } = useQuery({
    queryKey: ['system-health'],
    queryFn: () => apiClient.get<HealthApiResponse>('/system/health'),
    refetchInterval: 10_000,
    staleTime: 5_000,
  });

  if (isLoading) {
    return (
      <div className="bg-surface-container rounded-xl p-5">
        <h3 className="text-sm font-semibold text-on-surface mb-3">System Health</h3>
        <div className="space-y-2 animate-pulse">
          {['DB', 'Valkey', 'Celery', 'Kafka'].map((name) => (
            <div key={name} className="flex justify-between py-2">
              <div className="h-4 w-16 bg-surface-container-high rounded-sm" />
              <div className="h-5 w-12 bg-surface-container-high rounded-md" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Map flat API response to display components
  const toComponent = (status?: string): ComponentHealth => ({
    status: status === 'up' ? 'up' : status === 'degraded' ? 'degraded' : 'down',
    latency_ms: null,
    details: {},
  });

  const displayComponents: { name: string; component: ComponentHealth }[] = data
    ? [
        { name: 'Database', component: toComponent(data.db) },
        { name: 'Valkey', component: toComponent(data.valkey) },
        { name: 'Celery', component: toComponent(data.celery) },
        { name: 'Kafka', component: toComponent(data.kafka) },
      ]
    : [
        { name: 'Database', component: toComponent() },
        { name: 'Valkey', component: toComponent() },
        { name: 'Celery', component: toComponent() },
        { name: 'Kafka', component: toComponent() },
      ];

  return (
    <div className={cn('bg-surface-container rounded-xl p-5')}>
      <h3 className="text-sm font-semibold text-on-surface mb-3">System Health</h3>
      <div className="space-y-0">
        {displayComponents.map(({ name, component }) => (
          <ComponentStatus key={name} name={name} component={component} />
        ))}
      </div>
    </div>
  );
}
