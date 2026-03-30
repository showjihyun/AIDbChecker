// Spec: FS-AI-013 — LLM Observability Dashboard Page
import { LLMObservabilityPanel } from '@/components/ai/LLMObservabilityPanel';

export function LLMObservabilityPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-on-surface">
          LLM Observability
        </h1>
        <p className="text-xs text-on-surface-variant mt-1">
          AI pipeline metrics — token usage, latency, cost, hallucination rate,
          model drift detection
        </p>
      </div>
      <LLMObservabilityPanel />
    </div>
  );
}
