// Spec: MVP-DASH-001, API_SPEC.md Section 2 — Instance list row component
import { useState, useCallback } from 'react';
import { cn } from '@/lib/cn';
import { Badge } from '@/components/common/Badge';
import { useDeleteInstance, useTestConnection } from '@/api/hooks/useInstances';
import type { Instance } from '@/types/api';

interface InstanceListItemProps {
  instance: Instance;
}

const envBadgeVariant: Record<string, 'critical' | 'warning' | 'info'> = {
  production: 'critical',
  staging: 'warning',
  development: 'info',
};

export function InstanceListItem({ instance }: InstanceListItemProps) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);

  const deleteInstance = useDeleteInstance();
  const testConnection = useTestConnection();

  const handleTestConnection = useCallback(() => {
    setTestResult(null);
    testConnection.mutate(
      {
        id: instance.id,
        data: {
          host: instance.host,
          port: instance.port,
          database_name: instance.database_name,
        },
      },
      {
        onSuccess: (res) => {
          setTestResult({
            success: res.success,
            message: res.success
              ? `Connected (${res.latency_ms}ms, ${res.version ?? 'unknown'})`
              : res.error ?? 'Connection failed.',
          });
        },
        onError: (err: unknown) => {
          const detail = (err as { detail?: string })?.detail ?? 'Connection test failed.';
          setTestResult({ success: false, message: detail });
        },
      }
    );
  }, [instance, testConnection]);

  const handleDelete = useCallback(() => {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    deleteInstance.mutate(instance.id, {
      onSettled: () => setConfirmDelete(false),
    });
  }, [confirmDelete, instance.id, deleteInstance]);

  const handleCancelDelete = useCallback(() => {
    setConfirmDelete(false);
  }, []);

  return (
    <div
      className={cn(
        'bg-surface-container rounded-xl p-4',
        'hover:bg-surface-container-high transition-colors duration-200 ease-out'
      )}
    >
      {/* Top row: name + badges */}
      <div className="flex items-center justify-between gap-3 mb-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="material-symbols-outlined text-lg text-on-surface-variant shrink-0">
            database
          </span>
          <h3 className="text-sm font-semibold text-on-surface truncate">
            {instance.name}
          </h3>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Badge variant={envBadgeVariant[instance.environment] ?? 'neutral'}>
            {instance.environment}
          </Badge>
          <Badge variant={instance.is_active ? 'healthy' : 'neutral'} dot>
            {instance.is_active ? 'Active' : 'Inactive'}
          </Badge>
        </div>
      </div>

      {/* Details row */}
      <div className="flex items-center gap-4 text-xs text-on-surface-variant mb-3">
        <span className="flex items-center gap-1">
          <span className="material-symbols-outlined text-sm">link</span>
          {instance.host}:{instance.port}
        </span>
        <span className="flex items-center gap-1">
          <span className="material-symbols-outlined text-sm">storage</span>
          {instance.database_name}
        </span>
        <span className="uppercase text-[10px] font-semibold tracking-wider">
          {instance.db_type}
        </span>
      </div>

      {/* Test result feedback */}
      {testResult && (
        <div
          className={cn(
            'rounded-lg px-3 py-2 text-xs font-medium mb-3',
            testResult.success ? 'bg-tertiary/10 text-tertiary' : 'bg-error/10 text-error'
          )}
        >
          {testResult.message}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={handleTestConnection}
          disabled={testConnection.isPending}
          className={cn(
            'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium',
            'bg-primary-container/10 text-primary-container',
            'hover:bg-primary-container/20 transition-colors duration-200 ease-out',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          {testConnection.isPending ? (
            <span className="material-symbols-outlined text-sm animate-spin">progress_activity</span>
          ) : (
            <span className="material-symbols-outlined text-sm">cable</span>
          )}
          Test Connection
        </button>

        <div className="flex-1" />

        {confirmDelete ? (
          <div className="flex items-center gap-2">
            <span className="text-xs text-on-surface-variant">Delete?</span>
            <button
              onClick={handleDelete}
              disabled={deleteInstance.isPending}
              className={cn(
                'px-3 py-1.5 rounded-lg text-xs font-medium',
                'bg-error/15 text-error hover:bg-error/25',
                'transition-colors duration-200 ease-out',
                'disabled:opacity-50'
              )}
            >
              {deleteInstance.isPending ? 'Deleting...' : 'Confirm'}
            </button>
            <button
              onClick={handleCancelDelete}
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-on-surface-variant hover:bg-surface-container-high transition-colors duration-200 ease-out"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={handleDelete}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium',
              'text-on-surface-variant hover:text-error hover:bg-error/10',
              'transition-colors duration-200 ease-out'
            )}
          >
            <span className="material-symbols-outlined text-sm">delete</span>
            Delete
          </button>
        )}
      </div>
    </div>
  );
}
