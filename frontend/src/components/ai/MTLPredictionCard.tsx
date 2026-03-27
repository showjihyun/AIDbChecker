// Spec: FS-AI-010, FS-AI-011, FE-COMP-001 §3.12
// MTL RCA prediction card with confidence badge and feedback buttons

import { useState } from 'react';
import { cn } from '@/lib/cn';
import { ConfidenceBadge } from './ConfidenceBadge';

interface Recommendation {
  action: string;
  description: string;
  risk_level: 'low' | 'medium' | 'high';
  sql?: string;
}

interface MTLPrediction {
  id: string;
  anomaly_type: string;
  root_cause: string;
  confidence: number;
  severity_score: number;
  suggested_actions: Recommendation[];
  reasoning_chain: string[];
  ai_model: string;
  created_at: string;
  feedback: 'positive' | 'negative' | null;
}

interface MTLPredictionCardProps {
  /** MTL prediction result */
  prediction: MTLPrediction;
  /** Feedback handler */
  onFeedback: (predictionId: string, feedback: 'positive' | 'negative') => void;
}

const riskColors: Record<string, string> = {
  low: 'text-tertiary',
  medium: 'text-amber-500',
  high: 'text-error',
};

export function MTLPredictionCard({ prediction, onFeedback }: MTLPredictionCardProps) {
  const [feedbackGiven, setFeedbackGiven] = useState(prediction.feedback);

  const handleFeedback = (fb: 'positive' | 'negative') => {
    setFeedbackGiven(fb);
    onFeedback(prediction.id, fb);
  };

  return (
    <div className="bg-surface-container rounded-xl p-5 border border-secondary/20">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <p className="text-sm font-medium text-on-surface">
            {prediction.anomaly_type.replace(/_/g, ' ')}
          </p>
          <p className="text-xs text-on-surface-variant mt-1">
            {prediction.root_cause}
          </p>
        </div>
        <ConfidenceBadge confidence={prediction.confidence} size="md" />
      </div>

      {/* Suggested Actions */}
      {prediction.suggested_actions.length > 0 && (
        <div className="space-y-2 mb-3">
          <p className="text-[10px] font-semibold text-on-surface-variant uppercase tracking-wider">
            Recommended Actions
          </p>
          {prediction.suggested_actions.map((action, i) => (
            <div
              key={i}
              className="bg-surface-container-high rounded-lg px-3 py-2"
            >
              <div className="flex items-center gap-2">
                <span className={cn('text-[10px] font-bold uppercase', riskColors[action.risk_level])}>
                  {action.risk_level}
                </span>
                <span className="text-xs text-on-surface">{action.description}</span>
              </div>
              {action.sql && (
                <pre className="font-mono text-[10px] text-on-surface-variant mt-1 truncate">
                  {action.sql}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}

      {/* AI Model + Feedback */}
      <div className="flex items-center justify-between pt-3 border-t border-white/5">
        <span className="text-[10px] text-on-surface-variant font-mono">
          {prediction.ai_model}
        </span>

        <div className="flex gap-2">
          <button
            onClick={() => handleFeedback('positive')}
            disabled={feedbackGiven !== null}
            className={cn(
              'rounded-lg px-3 py-1 text-xs font-medium transition-colors',
              feedbackGiven === 'positive'
                ? 'bg-tertiary/20 text-tertiary'
                : 'bg-tertiary/10 text-tertiary hover:bg-tertiary/20',
              feedbackGiven !== null && feedbackGiven !== 'positive' && 'opacity-40'
            )}
            aria-label="Positive feedback"
          >
            👍
          </button>
          <button
            onClick={() => handleFeedback('negative')}
            disabled={feedbackGiven !== null}
            className={cn(
              'rounded-lg px-3 py-1 text-xs font-medium transition-colors',
              feedbackGiven === 'negative'
                ? 'bg-error/20 text-error'
                : 'bg-error/10 text-error hover:bg-error/20',
              feedbackGiven !== null && feedbackGiven !== 'negative' && 'opacity-40'
            )}
            aria-label="Negative feedback"
          >
            👎
          </button>
        </div>
      </div>
    </div>
  );
}
