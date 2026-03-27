// Spec: FS-AI-011, FE-COMP-001 §3.10
// Confidence Score badge with 4-tier color coding
// >= 0.85 → HIGH (tertiary), >= 0.65 → MEDIUM (primary),
// >= 0.40 → LOW (amber), < 0.40 → VERY_LOW (error)

import { cn } from '@/lib/cn';

type ConfidenceGrade = 'HIGH' | 'MEDIUM' | 'LOW' | 'VERY_LOW';
type BadgeSize = 'sm' | 'md' | 'lg';

interface ConfidenceBadgeProps {
  /** Confidence score 0.0 ~ 1.0 */
  confidence: number;
  /** Size variant */
  size?: BadgeSize;
  /** Additional CSS classes */
  className?: string;
}

function getGrade(confidence: number): ConfidenceGrade {
  if (confidence >= 0.85) return 'HIGH';
  if (confidence >= 0.65) return 'MEDIUM';
  if (confidence >= 0.40) return 'LOW';
  return 'VERY_LOW';
}

const gradeStyles: Record<ConfidenceGrade, string> = {
  HIGH: 'bg-tertiary/20 text-tertiary',
  MEDIUM: 'bg-primary/20 text-primary',
  LOW: 'bg-amber-500/20 text-amber-500',
  VERY_LOW: 'bg-error/20 text-error',
};

const gradeLabels: Record<ConfidenceGrade, string> = {
  HIGH: 'High',
  MEDIUM: 'Medium',
  LOW: 'Low',
  VERY_LOW: 'Very Low',
};

const sizeStyles: Record<BadgeSize, string> = {
  sm: 'text-[10px] px-1.5 py-0.5',
  md: 'text-xs px-2 py-1',
  lg: 'text-sm px-3 py-1.5',
};

export function ConfidenceBadge({
  confidence,
  size = 'md',
  className,
}: ConfidenceBadgeProps) {
  const clamped = Math.max(0, Math.min(1, confidence));
  const grade = getGrade(clamped);
  const pct = Math.round(clamped * 100);

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full font-mono font-bold',
        gradeStyles[grade],
        sizeStyles[size],
        className
      )}
      title={`신뢰도: ${pct}% (${gradeLabels[grade]})`}
      role="status"
      aria-label={`Confidence ${pct}% ${gradeLabels[grade]}`}
    >
      {pct}%
    </span>
  );
}
