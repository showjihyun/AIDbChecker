// Spec: FRONTEND_DESIGN.md — Status badge with design token colors
import { cn } from '@/lib/cn';

type BadgeVariant = 'healthy' | 'critical' | 'warning' | 'ai' | 'info' | 'neutral';

interface BadgeProps {
  variant: BadgeVariant;
  children: React.ReactNode;
  className?: string;
  dot?: boolean;
}

const variantStyles: Record<BadgeVariant, string> = {
  healthy: 'bg-tertiary/15 text-tertiary',
  critical: 'bg-error/15 text-error',
  warning: 'bg-warning/15 text-warning',
  ai: 'bg-secondary/15 text-secondary',
  info: 'bg-primary/15 text-primary',
  neutral: 'bg-surface-variant text-on-surface-variant',
};

const dotColors: Record<BadgeVariant, string> = {
  healthy: 'bg-tertiary',
  critical: 'bg-error',
  warning: 'bg-warning',
  ai: 'bg-secondary',
  info: 'bg-primary',
  neutral: 'bg-outline',
};

export function Badge({ variant, children, className, dot = false }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold tracking-wide',
        variantStyles[variant],
        className
      )}
    >
      {dot && (
        <span
          className={cn('w-1.5 h-1.5 rounded-full shrink-0', dotColors[variant])}
          aria-hidden="true"
        />
      )}
      {children}
    </span>
  );
}
