// Spec: FS-AI-011, FS-AI-010, FE-COMP-001 §3.11
// Expandable panel showing AI reasoning steps and evidence links

import { cn } from '@/lib/cn';

interface ReasoningStep {
  step: number;
  title: string;
  description: string;
  evidence_ids?: string[];
  confidence_contribution?: number;
}

interface EvidenceLink {
  id: string;
  type: 'metric' | 'log' | 'schema_change' | 'similar_incident' | 'baseline';
  label: string;
  summary: string;
  source_url?: string;
  relevance_score: number;
}

interface ReasoningChainPanelProps {
  /** Reasoning steps from AI */
  steps: ReasoningStep[];
  /** Evidence links */
  evidenceLinks: EvidenceLink[];
  /** Panel expanded state */
  isExpanded: boolean;
  /** Toggle handler */
  onToggle: () => void;
}

const evidenceTypeColors: Record<string, string> = {
  metric: 'bg-primary/15 text-primary',
  log: 'bg-amber-500/15 text-amber-500',
  schema_change: 'bg-error/15 text-error',
  similar_incident: 'bg-secondary/15 text-secondary',
  baseline: 'bg-tertiary/15 text-tertiary',
};

export function ReasoningChainPanel({
  steps,
  evidenceLinks,
  isExpanded,
  onToggle,
}: ReasoningChainPanelProps) {
  if (steps.length === 0) {
    return (
      <div className="bg-surface-container rounded-xl border border-white/5 px-5 py-3">
        <p className="text-xs text-on-surface-variant">추론 데이터 없음</p>
      </div>
    );
  }

  return (
    <div className="bg-surface-container rounded-xl border border-white/5">
      {/* Header */}
      <button
        onClick={onToggle}
        className="w-full px-5 py-3 flex justify-between items-center cursor-pointer hover:bg-surface-container-high transition-colors rounded-xl"
        aria-expanded={isExpanded}
        aria-controls="reasoning-chain-content"
      >
        <span className="text-sm font-medium text-secondary">
          AI 추론 과정 ({steps.length}단계)
        </span>
        <span
          className={cn(
            'material-symbols-outlined text-on-surface-variant text-lg transition-transform',
            isExpanded && 'rotate-180'
          )}
          aria-hidden="true"
        >
          expand_more
        </span>
      </button>

      {/* Content */}
      {isExpanded && (
        <div id="reasoning-chain-content" className="px-5 pb-4">
          {/* Steps timeline */}
          <div className="ml-6 border-l-2 border-secondary/30 pl-4 space-y-4">
            {steps.map((step) => (
              <div key={step.step} className="relative">
                {/* Timeline dot */}
                <span
                  className="w-3 h-3 rounded-full bg-secondary absolute -left-[23px] top-1"
                  aria-hidden="true"
                />
                <div>
                  <p className="text-xs font-semibold text-on-surface">
                    Step {step.step}: {step.title}
                  </p>
                  <p className="text-xs text-on-surface-variant mt-0.5">
                    {step.description}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* Evidence links */}
          {evidenceLinks.length > 0 && (
            <div className="mt-4 pt-3 border-t border-white/5">
              <p className="text-[10px] font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
                Evidence
              </p>
              <div className="flex flex-wrap gap-1.5">
                {evidenceLinks.map((link) => (
                  <span
                    key={link.id}
                    className={cn(
                      'px-2 py-0.5 rounded text-[10px] font-medium',
                      evidenceTypeColors[link.type] || 'bg-surface-container-high text-on-surface-variant'
                    )}
                    title={link.summary}
                  >
                    {link.label}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
