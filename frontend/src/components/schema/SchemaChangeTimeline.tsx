// Spec: FE-COMP-001 §3.18, FS-SCHEMA-001
// Timeline visualization of DDL changes (CREATE/ALTER/DROP/RENAME)

import { cn } from '@/lib/cn';

interface SchemaChange {
  id: string;
  instance_id: string;
  change_type: 'CREATE' | 'ALTER' | 'DROP' | 'REINDEX' | 'PARAM_CHANGE';
  object_type: string;
  object_name: string;
  ddl_command?: string;
  executed_by?: string;
  detected_at: string;
}

interface SchemaChangeTimelineProps {
  /** Schema change history */
  changes: SchemaChange[];
  /** Loading state */
  isLoading?: boolean;
}

const changeTypeColors: Record<string, string> = {
  CREATE: 'bg-tertiary',
  ALTER: 'bg-primary',
  DROP: 'bg-error',
  REINDEX: 'bg-amber-500',
  PARAM_CHANGE: 'bg-secondary',
};

const changeTypeLabels: Record<string, string> = {
  CREATE: 'Created',
  ALTER: 'Altered',
  DROP: 'Dropped',
  REINDEX: 'Reindexed',
  PARAM_CHANGE: 'Parameter Changed',
};

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString('ko-KR', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

export function SchemaChangeTimeline({
  changes,
  isLoading = false,
}: SchemaChangeTimelineProps) {
  if (isLoading) {
    return (
      <div className="relative ml-4 border-l-2 border-outline-variant/30 pl-4 space-y-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="relative animate-pulse">
            <span className="w-3 h-3 rounded-full bg-surface-variant absolute -left-[23px] top-1" />
            <div className="h-3 bg-surface-variant rounded w-3/4 mb-2" />
            <div className="h-2 bg-surface-variant rounded w-1/2" />
          </div>
        ))}
      </div>
    );
  }

  if (changes.length === 0) {
    return (
      <div className="text-center py-8">
        <span className="material-symbols-outlined text-3xl text-on-surface-variant/40 mb-2 block">
          schema
        </span>
        <p className="text-sm text-on-surface-variant">DDL 변경 이력이 없습니다</p>
      </div>
    );
  }

  return (
    <div className="relative ml-4 border-l-2 border-outline-variant/30 pl-4 space-y-4">
      {changes.map((change) => {
        const dotColor = changeTypeColors[change.change_type] || 'bg-outline';
        const label = changeTypeLabels[change.change_type] || change.change_type;

        return (
          <div key={change.id} className="relative">
            {/* Timeline dot */}
            <span
              className={cn('w-3 h-3 rounded-full absolute -left-[23px] top-1', dotColor)}
              aria-hidden="true"
            />

            <div>
              {/* Change type + object */}
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    'text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded',
                    dotColor + '/20',
                    'text-on-surface'
                  )}
                >
                  {label}
                </span>
                <span className="text-xs font-medium text-on-surface">
                  {change.object_type} {change.object_name}
                </span>
              </div>

              {/* DDL command */}
              {change.ddl_command && (
                <pre className="font-mono text-xs bg-surface-container-lowest p-2 rounded-lg mt-1.5 overflow-x-auto text-on-surface-variant">
                  {change.ddl_command}
                </pre>
              )}

              {/* Metadata */}
              <div className="flex items-center gap-3 mt-1">
                <span className="text-[10px] text-on-surface-variant">
                  {formatTimestamp(change.detected_at)}
                </span>
                {change.executed_by && (
                  <span className="text-[10px] text-on-surface-variant">
                    by {change.executed_by}
                  </span>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
