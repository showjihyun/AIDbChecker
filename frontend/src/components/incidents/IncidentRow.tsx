// Spec: FS-DASH-004 — Individual incident row component
import { formatDistanceToNow } from 'date-fns';
import { cn } from '@/lib/cn';
import type { Incident, IncidentSeverity } from '@/types/api';

// Spec: FS-DASH-004 Section 3.3 — severity design tokens
const SEVERITY_CONFIG: Record<
  IncidentSeverity,
  { text: string; bg: string; icon: string }
> = {
  critical: { text: 'text-error', bg: 'bg-error-container', icon: 'error' },
  warning: { text: 'text-warning', bg: 'bg-warning-container', icon: 'warning' },
  notice: { text: 'text-tertiary', bg: 'bg-tertiary-container', icon: 'info' },
  info: { text: 'text-on-surface-variant', bg: 'bg-surface-container-high', icon: 'info' },
};

interface IncidentRowProps {
  incident: Incident;
  onAcknowledge: (id: string) => void;
  onResolve: (id: string) => void;
  isUpdating: boolean;
}

export function IncidentRow({
  incident,
  onAcknowledge,
  onResolve,
  isUpdating,
}: IncidentRowProps) {
  const config = SEVERITY_CONFIG[incident.severity] ?? SEVERITY_CONFIG.info;
  const timeAgo = formatDistanceToNow(new Date(incident.detected_at), {
    addSuffix: true,
  });

  const canAcknowledge = incident.status === 'open';
  const canResolve =
    incident.status === 'acknowledged' || incident.status === 'in_progress';

  return (
    <div
      className={cn(
        'flex items-center gap-4 px-4 py-3 rounded-lg',
        'bg-surface-container hover:bg-surface-container-high',
        'transition-colors duration-200 ease-out'
      )}
    >
      {/* Severity badge */}
      <div
        className={cn(
          'flex items-center justify-center w-8 h-8 rounded-lg shrink-0',
          config.bg
        )}
      >
        <span className={cn('material-symbols-outlined text-lg', config.text)}>
          {config.icon}
        </span>
      </div>

      {/* Severity label */}
      <span
        className={cn(
          'text-[10px] font-semibold tracking-wider uppercase w-16 shrink-0',
          config.text
        )}
      >
        {incident.severity}
      </span>

      {/* Instance name */}
      <span className="text-xs text-on-surface-variant font-medium w-28 truncate shrink-0">
        {incident.instance_name ?? 'Unknown'}
      </span>

      {/* Title */}
      <span className="text-sm text-on-surface flex-1 truncate">
        {incident.title}
      </span>

      {/* Time ago */}
      <span className="text-xs text-outline shrink-0 w-24 text-right">
        {timeAgo}
      </span>

      {/* Action buttons */}
      <div className="flex gap-2 shrink-0">
        {canAcknowledge && (
          <button
            onClick={() => onAcknowledge(incident.id)}
            disabled={isUpdating}
            className={cn(
              'px-3 py-1.5 text-xs font-medium rounded-lg',
              'bg-primary-container text-on-primary-container',
              'hover:bg-primary hover:text-on-primary',
              'transition-colors duration-200 ease-out',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
          >
            ACK
          </button>
        )}
        {canResolve && (
          <button
            onClick={() => onResolve(incident.id)}
            disabled={isUpdating}
            className={cn(
              'px-3 py-1.5 text-xs font-medium rounded-lg',
              'bg-tertiary-container text-on-tertiary-container',
              'hover:bg-tertiary hover:text-on-tertiary',
              'transition-colors duration-200 ease-out',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
          >
            Resolve
          </button>
        )}
        {incident.status === 'resolved' && (
          <span className="px-3 py-1.5 text-xs font-medium text-on-surface-variant">
            Resolved
          </span>
        )}
      </div>
    </div>
  );
}
