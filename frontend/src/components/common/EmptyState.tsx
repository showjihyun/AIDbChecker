// Spec: FRONTEND_DESIGN.md — Reusable empty state component
import { cn } from '@/lib/cn';

interface EmptyStateProps {
  icon?: string;
  message: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
}

export function EmptyState({
  icon = 'inbox',
  message,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center py-16 px-6',
        className
      )}
    >
      <span
        className="material-symbols-outlined text-5xl text-outline mb-4"
        aria-hidden="true"
      >
        {icon}
      </span>
      <p className="text-on-surface text-sm font-medium mb-1">{message}</p>
      {description && (
        <p className="text-on-surface-variant text-xs max-w-sm text-center">
          {description}
        </p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          className={cn(
            'mt-4 px-4 py-2 rounded-md text-sm font-medium',
            'bg-primary-container text-on-primary',
            'hover:brightness-110 transition-all duration-200 ease-out'
          )}
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
