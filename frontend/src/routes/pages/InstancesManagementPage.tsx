// Spec: MVP-DASH-001, API_SPEC.md Section 2 — Instance management page
import { useState, useCallback } from 'react';
import { cn } from '@/lib/cn';
import { useInstances } from '@/api/hooks/useInstances';
import { EmptyState } from '@/components/common/EmptyState';
import { RegisterInstanceModal } from '@/components/instances/RegisterInstanceModal';
import { InstanceListItem } from '@/components/instances/InstanceListItem';

export function InstancesManagementPage() {
  const { data: instances, isLoading } = useInstances();
  const [modalOpen, setModalOpen] = useState(false);

  const openModal = useCallback(() => setModalOpen(true), []);
  const closeModal = useCallback(() => setModalOpen(false), []);

  return (
    <div className="space-y-module-gap">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold text-on-surface tracking-tight">
            Instances
          </h1>
          <p className="text-xs text-on-surface-variant mt-1">
            Register and manage monitored PostgreSQL databases
          </p>
        </div>
        <button
          onClick={openModal}
          className={cn(
            'flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold',
            'bg-primary-container text-on-primary',
            'hover:brightness-110 transition-all duration-200 ease-out'
          )}
        >
          <span className="material-symbols-outlined text-base">add</span>
          Register Instance
        </button>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="bg-surface-container rounded-xl p-4 animate-pulse"
            >
              <div className="h-4 bg-surface-container-high rounded w-1/3 mb-3" />
              <div className="h-3 bg-surface-container-high rounded w-2/3 mb-2" />
              <div className="h-3 bg-surface-container-high rounded w-1/4" />
            </div>
          ))}
        </div>
      ) : !instances || instances.length === 0 ? (
        <EmptyState
          icon="dns"
          message="No instances registered"
          description="Register a PostgreSQL database instance to start monitoring its metrics, sessions, and performance."
          action={{ label: 'Register Instance', onClick: openModal }}
        />
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-on-surface-variant">
            {instances.length} instance{instances.length !== 1 ? 's' : ''} registered
          </p>
          {instances.map((instance) => (
            <InstanceListItem key={instance.id} instance={instance} />
          ))}
        </div>
      )}

      {/* Registration modal */}
      <RegisterInstanceModal open={modalOpen} onClose={closeModal} />
    </div>
  );
}
