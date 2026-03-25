// Spec: FS-DASH-004 — Incidents list page
import { useState, useCallback } from 'react';
import { cn } from '@/lib/cn';
import { useIncidents, useUpdateIncidentStatus } from '@/api/hooks/useIncidents';
import { IncidentRow } from '@/components/incidents/IncidentRow';
import type { IncidentSeverity } from '@/types/api';

// Spec: FS-DASH-004 Section 3.1 — severity filter tabs
const SEVERITY_TABS: Array<{ label: string; value: IncidentSeverity | undefined }> = [
  { label: 'ALL', value: undefined },
  { label: 'CRITICAL', value: 'critical' },
  { label: 'WARNING', value: 'warning' },
  { label: 'NOTICE', value: 'notice' },
  { label: 'INFO', value: 'info' },
];

export function IncidentsPage() {
  const [activeSeverity, setActiveSeverity] = useState<IncidentSeverity | undefined>(
    undefined
  );

  const { data, isLoading } = useIncidents({
    severity: activeSeverity,
    limit: 100,
  });
  const updateStatus = useUpdateIncidentStatus();

  const handleAcknowledge = useCallback(
    (id: string) => {
      updateStatus.mutate({ id, status: 'acknowledged' });
    },
    [updateStatus]
  );

  const handleResolve = useCallback(
    (id: string) => {
      updateStatus.mutate({ id, status: 'resolved' });
    },
    [updateStatus]
  );

  const incidents = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="space-y-module-gap">
      {/* Header */}
      <div>
        <h1 className="text-xl font-display font-bold text-on-surface">
          Incidents
        </h1>
        <p className="text-sm text-on-surface-variant mt-1">
          Active incidents across all monitored instances
          {total > 0 && (
            <span className="ml-2 text-xs text-outline">
              ({total} total)
            </span>
          )}
        </p>
      </div>

      {/* Severity filter tabs */}
      <div className="flex gap-1">
        {SEVERITY_TABS.map((tab) => (
          <button
            key={tab.label}
            onClick={() => setActiveSeverity(tab.value)}
            className={cn(
              'px-4 py-2 text-xs font-semibold tracking-wider uppercase rounded-lg',
              'transition-colors duration-200 ease-out',
              activeSeverity === tab.value
                ? 'bg-primary-container text-on-primary-container'
                : 'text-on-surface-variant hover:bg-surface-container-high'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Incident list */}
      <div className="space-y-2">
        {isLoading ? (
          <IncidentSkeleton count={5} />
        ) : incidents.length === 0 ? (
          <EmptyState />
        ) : (
          incidents.map((incident) => (
            <IncidentRow
              key={incident.id}
              incident={incident}
              onAcknowledge={handleAcknowledge}
              onResolve={handleResolve}
              isUpdating={updateStatus.isPending}
            />
          ))
        )}
      </div>
    </div>
  );
}

// Spec: FS-DASH-004 — AC-4: EmptyState
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <span className="material-symbols-outlined text-5xl text-outline mb-4">
        check_circle
      </span>
      <p className="text-sm font-medium text-on-surface-variant">
        No incidents found
      </p>
      <p className="text-xs text-outline mt-1">
        All monitored instances are running normally
      </p>
    </div>
  );
}

function IncidentSkeleton({ count }: { count: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-4 px-4 py-3 rounded-lg bg-surface-container animate-pulse"
        >
          <div className="w-8 h-8 rounded-lg bg-surface-container-high" />
          <div className="w-16 h-3 rounded bg-surface-container-high" />
          <div className="w-28 h-3 rounded bg-surface-container-high" />
          <div className="flex-1 h-3 rounded bg-surface-container-high" />
          <div className="w-24 h-3 rounded bg-surface-container-high" />
        </div>
      ))}
    </>
  );
}
