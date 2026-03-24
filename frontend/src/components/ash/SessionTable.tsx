// Spec: MVP-DASH-003 — Active sessions table sorted by duration
import { cn } from '@/lib/cn';
import { Badge } from '@/components/common/Badge';
import { EmptyState } from '@/components/common/EmptyState';
import type { ActiveSession } from '@/types/api';

interface SessionTableProps {
  sessions: ActiveSession[] | undefined;
  isLoading: boolean;
}

function truncateQuery(query: string | null, maxLen = 80): string {
  if (!query) return '--';
  if (query.length <= maxLen) return query;
  return query.slice(0, maxLen) + '...';
}

function formatDuration(ms: number | null): string {
  if (ms == null) return '--';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60_000).toFixed(1)}m`;
}

function getStateBadgeVariant(
  state: ActiveSession['state']
): 'healthy' | 'warning' | 'critical' {
  switch (state) {
    case 'active':
      return 'healthy';
    case 'idle in transaction':
      return 'warning';
    case 'locked':
      return 'critical';
    default:
      return 'healthy';
  }
}

export function SessionTable({ sessions, isLoading }: SessionTableProps) {
  const sortedSessions = sessions
    ? [...sessions].sort(
        (a, b) => (b.duration_ms ?? 0) - (a.duration_ms ?? 0)
      )
    : [];

  return (
    <div className="bg-surface-container rounded-xl p-5">
      <h3 className="text-sm font-semibold text-on-surface mb-4">
        Active Sessions
      </h3>

      {isLoading ? (
        <div className="space-y-2 animate-pulse">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-10 bg-surface-container-high rounded-sm" />
          ))}
        </div>
      ) : sortedSessions.length === 0 ? (
        <EmptyState
          icon="person_off"
          message="활성 세션 없음"
          description="현재 활성 세션이 없습니다."
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs" role="table">
            <thead>
              <tr className="text-left text-on-surface-variant">
                <th className="pb-2 pr-4 font-semibold tracking-wider uppercase text-[10px]">
                  PID
                </th>
                <th className="pb-2 pr-4 font-semibold tracking-wider uppercase text-[10px]">
                  Query
                </th>
                <th className="pb-2 pr-4 font-semibold tracking-wider uppercase text-[10px]">
                  State
                </th>
                <th className="pb-2 pr-4 font-semibold tracking-wider uppercase text-[10px]">
                  Wait Event
                </th>
                <th className="pb-2 font-semibold tracking-wider uppercase text-[10px] text-right">
                  Duration
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedSessions.map((session) => (
                <tr
                  key={session.id}
                  className={cn(
                    'hover:bg-surface-container-high/50 transition-colors duration-150 ease-out',
                    session.state === 'locked' && 'bg-error/5'
                  )}
                >
                  <td className="py-2 pr-4 font-mono text-on-surface tabular-nums">
                    {session.pid}
                  </td>
                  <td className="py-2 pr-4 max-w-sm">
                    <span
                      className="font-mono text-on-surface-variant block truncate"
                      title={session.query ?? undefined}
                    >
                      {truncateQuery(session.query)}
                    </span>
                  </td>
                  <td className="py-2 pr-4">
                    <Badge variant={getStateBadgeVariant(session.state)}>
                      {session.state}
                    </Badge>
                  </td>
                  <td className="py-2 pr-4 text-on-surface-variant">
                    {session.wait_event_type && session.wait_event ? (
                      <span>
                        <span className="text-on-surface">
                          {session.wait_event_type}
                        </span>
                        {' / '}
                        {session.wait_event}
                      </span>
                    ) : (
                      <span className="text-outline">CPU</span>
                    )}
                  </td>
                  <td
                    className={cn(
                      'py-2 text-right font-mono tabular-nums',
                      (session.duration_ms ?? 0) > 10_000
                        ? 'text-error'
                        : (session.duration_ms ?? 0) > 1_000
                          ? 'text-warning'
                          : 'text-on-surface'
                    )}
                  >
                    {formatDuration(session.duration_ms)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
