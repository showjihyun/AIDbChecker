// Spec: FS-AUTO-004 — Task Queue 목록 + 승인/거부
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/api/client';
import { Badge } from '@/components/common/Badge';

interface TaskItem {
  id: string;
  playbook_name: string;
  instance_id: string;
  trigger: string;
  status: string;
  autonomy_level: number;
  confidence_score: number | null;
  created_at: string;
  completed_at: string | null;
}

const statusVariant: Record<string, 'healthy' | 'warning' | 'critical' | 'info' | 'neutral'> = {
  queued: 'info',
  pending_approval: 'warning',
  running: 'info',
  completed: 'healthy',
  failed: 'critical',
  rejected: 'neutral',
  cancelled: 'neutral',
  blocked: 'critical',
};

export function TasksPage() {
  const { data, isLoading } = useQuery<{ items: TaskItem[]; total: number }>({
    queryKey: ['tasks'],
    queryFn: () => apiClient.get('/tasks'),
    refetchInterval: 5000,
  });

  const tasks = data?.items || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-headline font-bold text-on-surface">Task Queue</h1>
        <span className="text-xs text-on-surface-variant">{data?.total || 0} tasks</span>
      </div>

      {isLoading && (
        <div className="space-y-2">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-surface-container rounded-xl p-4 h-16 animate-pulse" />
          ))}
        </div>
      )}

      {tasks.length === 0 && !isLoading && (
        <div className="text-center py-12">
          <span className="material-symbols-outlined text-3xl text-on-surface-variant/40">task_alt</span>
          <p className="text-sm text-on-surface-variant mt-2">No tasks yet</p>
          <p className="text-xs text-on-surface-variant/60">Tasks are created when playbooks are executed</p>
        </div>
      )}

      <div className="space-y-2">
        {tasks.map(task => (
          <div
            key={task.id}
            className="bg-surface-container rounded-xl px-5 py-3 flex items-center gap-4 border border-white/5"
          >
            <Badge variant={statusVariant[task.status] || 'neutral'} dot>
              {task.status}
            </Badge>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-on-surface">{task.playbook_name}</p>
              <p className="text-[10px] text-on-surface-variant">
                L{task.autonomy_level} · {task.trigger} · {new Date(task.created_at).toLocaleString()}
              </p>
            </div>
            {task.confidence_score !== null && (
              <span className="text-xs font-mono text-on-surface-variant">
                {Math.round(task.confidence_score * 100)}%
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
