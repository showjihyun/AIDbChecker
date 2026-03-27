// Spec: FS-AI-TRACE-001
// ReAct Trace — collapsible AI reasoning process viewer
// Default: collapsed. Click to expand step-by-step reasoning.

import { useState } from 'react';
import { cn } from '@/lib/cn';

interface TraceStep {
  step_type: 'thought' | 'action' | 'observation' | 'result' | 'error';
  content: string;
  timestamp_ms: number;
  metadata?: Record<string, unknown>;
}

interface ReActTraceData {
  agent: string;
  steps: TraceStep[];
  total_duration_ms: number;
  status: 'running' | 'completed' | 'failed';
}

interface ReActTracePanelProps {
  trace: ReActTraceData;
  /** Default collapsed */
  defaultExpanded?: boolean;
}

const stepConfig: Record<string, { icon: string; color: string; label: string }> = {
  thought: { icon: '💭', color: 'text-secondary', label: 'Thought' },
  action: { icon: '🔍', color: 'text-primary', label: 'Action' },
  observation: { icon: '📊', color: 'text-tertiary', label: 'Observation' },
  result: { icon: '✅', color: 'text-tertiary', label: 'Result' },
  error: { icon: '❌', color: 'text-error', label: 'Error' },
};

const agentLabels: Record<string, string> = {
  mtl_rca: 'MTL RCA (4-Head)',
  copilot: 'DB Copilot (ToT)',
  nl2sql: 'NL2SQL',
  report: 'AIGC Report',
};

const statusStyles: Record<string, string> = {
  running: 'text-amber-500 animate-pulse',
  completed: 'text-tertiary',
  failed: 'text-error',
};

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function ReActTracePanel({
  trace,
  defaultExpanded = false,
}: ReActTracePanelProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  const agentLabel = agentLabels[trace.agent] || trace.agent;
  const statusStyle = statusStyles[trace.status] || 'text-on-surface-variant';

  return (
    <div className="bg-surface-container rounded-xl border border-white/5 overflow-hidden">
      {/* Header — always visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-2.5 flex items-center justify-between cursor-pointer hover:bg-surface-container-high transition-colors"
        aria-expanded={isExpanded}
        aria-controls="react-trace-content"
      >
        <div className="flex items-center gap-2">
          <span className={cn('text-xs font-mono font-bold', statusStyle)}>
            {trace.status === 'running' ? '⟳ Analyzing...' : `${agentLabel}`}
          </span>
          <span className="text-[10px] text-on-surface-variant">
            {trace.steps.length} steps · {formatDuration(trace.total_duration_ms)}
          </span>
        </div>

        <span
          className={cn(
            'material-symbols-outlined text-on-surface-variant text-sm transition-transform',
            isExpanded && 'rotate-180'
          )}
          aria-hidden="true"
        >
          expand_more
        </span>
      </button>

      {/* Steps — collapsed by default */}
      {isExpanded && (
        <div
          id="react-trace-content"
          className="px-4 pb-3 border-t border-white/5"
        >
          <div className="space-y-1.5 mt-2">
            {trace.steps.map((step, i) => {
              const config = stepConfig[step.step_type] || stepConfig.thought;

              return (
                <div
                  key={i}
                  className="flex items-start gap-2 text-xs"
                >
                  {/* Icon */}
                  <span className="shrink-0 w-5 text-center" title={config.label}>
                    {config.icon}
                  </span>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <span className={cn('font-medium', config.color)}>
                      {config.label}:
                    </span>{' '}
                    <span className="text-on-surface-variant">
                      {step.content}
                    </span>
                  </div>

                  {/* Timestamp */}
                  <span className="shrink-0 text-[10px] font-mono text-on-surface-variant/50">
                    +{formatDuration(step.timestamp_ms)}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Footer */}
          <div className="mt-2 pt-2 border-t border-white/5 flex items-center justify-between">
            <span className="text-[10px] text-on-surface-variant">
              Agent: {agentLabel}
            </span>
            <span className={cn('text-[10px] font-bold', statusStyle)}>
              {trace.status.toUpperCase()}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
