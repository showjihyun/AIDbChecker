// Spec: FS-AI-TUNE-001 — Tuning Agent UI page
import { useState, useCallback, useRef } from 'react';
import { cn } from '@/lib/cn';
import { useInstances } from '@/api/hooks/useInstances';
import {
  useTuningAnalyze,
  useTuningHistory,
  type TuningResponse,
  type TuningAction,
} from '@/api/hooks/useTuning';
import { format } from 'date-fns';

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function TuningPage() {
  const { data: instances, isLoading: instancesLoading } = useInstances();
  const [selectedInstanceId, setSelectedInstanceId] = useState<string>('');
  const [question, setQuestion] = useState('');
  const [currentResult, setCurrentResult] = useState<TuningResponse | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const analyzeMutation = useTuningAnalyze();
  const { data: history, isLoading: historyLoading } = useTuningHistory(
    selectedInstanceId || undefined
  );

  const handleAnalyze = useCallback(async () => {
    if (!selectedInstanceId || !question.trim()) return;

    try {
      const result = await analyzeMutation.mutateAsync({
        instance_id: selectedInstanceId,
        question: question.trim(),
      });
      setCurrentResult(result);
    } catch {
      // Error is available via analyzeMutation.error
    }
  }, [selectedInstanceId, question, analyzeMutation]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleAnalyze();
    }
  };

  const handleHistoryClick = useCallback(
    (item: { question: string; analysis: string; actions: TuningAction[]; tools_used: string[]; model_used: string; duration_ms: number }) => {
      setCurrentResult({
        instance_id: selectedInstanceId,
        question: item.question,
        analysis: item.analysis,
        actions: item.actions,
        tools_used: item.tools_used,
        model_used: item.model_used,
        duration_ms: item.duration_ms,
        iterations: 0,
      });
    },
    [selectedInstanceId]
  );

  return (
    <div className="space-y-module-gap">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-display font-bold text-on-surface tracking-tight">
          Tuning Agent
        </h1>
        <p className="text-xs text-on-surface-variant mt-1">
          AI-powered PostgreSQL performance analysis and tuning recommendations
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Input + Results */}
        <div className="lg:col-span-8 space-y-6">
          {/* Input area */}
          <div className="bg-surface-container rounded-xl p-5 space-y-4">
            {/* Instance selector */}
            <div>
              <label
                htmlFor="tuning-instance-select"
                className="text-[10px] font-semibold tracking-wider uppercase text-on-surface-variant block mb-1.5"
              >
                Target Instance
              </label>
              <select
                id="tuning-instance-select"
                value={selectedInstanceId}
                onChange={(e) => setSelectedInstanceId(e.target.value)}
                className={cn(
                  'w-full bg-surface-container-high rounded-lg',
                  'px-3 py-2 text-sm text-on-surface',
                  'outline-none focus:ring-1 focus:ring-primary/50',
                  'transition-shadow duration-200 ease-out',
                  'appearance-none cursor-pointer'
                )}
                disabled={instancesLoading}
              >
                <option value="">
                  {instancesLoading ? 'Loading instances...' : 'Select an instance'}
                </option>
                {instances?.map((inst) => (
                  <option key={inst.id} value={inst.id}>
                    {inst.name} ({inst.host}:{inst.port})
                  </option>
                ))}
              </select>
            </div>

            {/* Question input */}
            <div>
              <label
                htmlFor="tuning-question"
                className="text-[10px] font-semibold tracking-wider uppercase text-on-surface-variant block mb-1.5"
              >
                Question
              </label>
              <textarea
                id="tuning-question"
                ref={textareaRef}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={3}
                placeholder="e.g. 이 DB가 느린 이유를 분석해줘 / Why are queries slow?"
                className={cn(
                  'w-full bg-surface-container-high rounded-lg',
                  'px-3 py-2 text-sm text-on-surface',
                  'placeholder:text-outline',
                  'outline-none focus:ring-1 focus:ring-primary/50',
                  'transition-shadow duration-200 ease-out',
                  'resize-none'
                )}
              />
              <p className="text-[10px] text-outline mt-1">
                Ctrl+Enter to submit
              </p>
            </div>

            {/* Analyze button */}
            <button
              onClick={handleAnalyze}
              disabled={!selectedInstanceId || !question.trim() || analyzeMutation.isPending}
              className={cn(
                'w-full py-2.5 rounded-lg text-sm font-semibold',
                'bg-primary text-on-primary',
                'disabled:opacity-30 disabled:cursor-not-allowed',
                'hover:opacity-90 active:scale-[0.99]',
                'transition-all duration-200 ease-out',
                'flex items-center justify-center gap-2'
              )}
            >
              {analyzeMutation.isPending ? (
                <>
                  <span className="material-symbols-outlined text-lg animate-spin">
                    progress_activity
                  </span>
                  Analyzing...
                </>
              ) : (
                <>
                  <span className="material-symbols-outlined text-lg">tune</span>
                  Analyze
                </>
              )}
            </button>
          </div>

          {/* Loading state */}
          {analyzeMutation.isPending && <LoadingPanel />}

          {/* Error state */}
          {analyzeMutation.isError && (
            <div className="bg-error/10 rounded-xl p-4 flex items-start gap-3">
              <span className="material-symbols-outlined text-error text-xl shrink-0">
                error
              </span>
              <div>
                <p className="text-sm font-medium text-error">Analysis Failed</p>
                <p className="text-xs text-error/80 mt-1">
                  {(analyzeMutation.error as { detail?: string })?.detail ??
                    'An unexpected error occurred. Please try again.'}
                </p>
              </div>
            </div>
          )}

          {/* Results */}
          {currentResult && !analyzeMutation.isPending && (
            <ResultPanel result={currentResult} />
          )}
        </div>

        {/* Right: History */}
        <div className="lg:col-span-4">
          <HistoryPanel
            history={history ?? []}
            isLoading={historyLoading}
            instanceSelected={!!selectedInstanceId}
            onItemClick={handleHistoryClick}
          />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading Panel
// ---------------------------------------------------------------------------

function LoadingPanel() {
  return (
    <div className="bg-surface-container rounded-xl p-6 space-y-4">
      <div className="flex items-center gap-3">
        <span className="material-symbols-outlined text-2xl text-primary animate-spin">
          progress_activity
        </span>
        <div>
          <p className="text-sm font-semibold text-on-surface">
            Agent analyzing...
          </p>
          <p className="text-xs text-on-surface-variant mt-0.5">
            Running diagnostic tools on the target instance
          </p>
        </div>
      </div>

      {/* Simulated tool progress */}
      <div className="space-y-2 pl-9">
        {[
          'Checking slow queries...',
          'Analyzing index usage...',
          'Evaluating parameters...',
        ].map((step, i) => (
          <div
            key={i}
            className="flex items-center gap-2 text-xs text-on-surface-variant animate-pulse"
            style={{ animationDelay: `${i * 600}ms` }}
          >
            <span className="material-symbols-outlined text-sm text-primary/60">
              build
            </span>
            {step}
          </div>
        ))}
      </div>

      <p className="text-[10px] text-outline pl-9">
        Estimated time: 10-30 seconds
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Result Panel
// ---------------------------------------------------------------------------

function ResultPanel({ result }: { result: TuningResponse }) {
  return (
    <div className="space-y-4">
      {/* Analysis summary */}
      <div className="bg-surface-container rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-lg text-primary">
            psychology
          </span>
          <h2 className="text-sm font-semibold text-on-surface">
            Analysis Summary
          </h2>
        </div>
        <div className="text-sm text-on-surface leading-relaxed whitespace-pre-wrap">
          {result.analysis}
        </div>
      </div>

      {/* Actions table */}
      {result.actions.length > 0 && (
        <div className="bg-surface-container rounded-xl overflow-hidden">
          <div className="px-5 py-3 flex items-center gap-2">
            <span className="material-symbols-outlined text-lg text-primary">
              checklist
            </span>
            <h2 className="text-sm font-semibold text-on-surface">
              Recommended Actions
            </h2>
            <span className="text-[10px] text-on-surface-variant ml-auto tabular-nums">
              {result.actions.length} action{result.actions.length !== 1 ? 's' : ''}
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-surface-container-high">
                  <th className="px-4 py-2 text-left font-semibold text-on-surface-variant whitespace-nowrap">
                    Type
                  </th>
                  <th className="px-4 py-2 text-left font-semibold text-on-surface-variant">
                    Description
                  </th>
                  <th className="px-4 py-2 text-left font-semibold text-on-surface-variant whitespace-nowrap">
                    Risk
                  </th>
                  <th className="px-4 py-2 text-left font-semibold text-on-surface-variant">
                    Impact
                  </th>
                </tr>
              </thead>
              <tbody>
                {result.actions.map((action, i) => (
                  <ActionRow key={i} action={action} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Meta info: tools, duration, model */}
      <div className="bg-surface-container rounded-xl p-5">
        <div className="flex flex-wrap gap-4">
          <MetaItem icon="build" label="Tools Used">
            <div className="flex flex-wrap gap-1 mt-1">
              {result.tools_used.map((tool) => (
                <span
                  key={tool}
                  className="px-2 py-0.5 rounded bg-primary/10 text-primary text-[10px] font-medium"
                >
                  {tool}
                </span>
              ))}
            </div>
          </MetaItem>
          <MetaItem icon="timer" label="Duration">
            <span className="text-sm font-semibold text-on-surface tabular-nums">
              {(result.duration_ms / 1000).toFixed(1)}s
            </span>
          </MetaItem>
          <MetaItem icon="smart_toy" label="Model">
            <span className="text-sm font-medium text-on-surface">
              {result.model_used}
            </span>
          </MetaItem>
          {result.iterations > 0 && (
            <MetaItem icon="repeat" label="Iterations">
              <span className="text-sm font-semibold text-on-surface tabular-nums">
                {result.iterations}
              </span>
            </MetaItem>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Action Row
// ---------------------------------------------------------------------------

function ActionRow({ action }: { action: TuningAction }) {
  const [sqlExpanded, setSqlExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    if (!action.sql) return;
    try {
      await navigator.clipboard.writeText(action.sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard API may not be available
    }
  }, [action.sql]);

  return (
    <>
      <tr className="hover:bg-surface-container-high/50 transition-colors">
        <td className="px-4 py-2.5 whitespace-nowrap">
          <div className="flex items-center gap-1.5">
            {action.risk_level === 'high' && (
              <span
                className="material-symbols-outlined text-sm text-error"
                title="High risk action"
              >
                warning
              </span>
            )}
            <span className="font-mono font-medium text-on-surface">
              {action.action_type}
            </span>
          </div>
        </td>
        <td className="px-4 py-2.5 text-on-surface">
          <div>
            {action.description}
            {action.sql && (
              <button
                onClick={() => setSqlExpanded((prev) => !prev)}
                className="ml-2 text-primary hover:underline text-[10px] font-medium"
              >
                {sqlExpanded ? 'Hide SQL' : 'Show SQL'}
              </button>
            )}
          </div>
        </td>
        <td className="px-4 py-2.5 whitespace-nowrap">
          <RiskBadge level={action.risk_level} />
        </td>
        <td className="px-4 py-2.5 text-on-surface-variant">
          {action.estimated_impact}
        </td>
      </tr>

      {/* Expandable SQL block */}
      {sqlExpanded && action.sql && (
        <tr>
          <td colSpan={4} className="px-4 pb-3 pt-0">
            <div className="relative bg-surface-container-highest rounded-lg overflow-hidden">
              <div className="flex items-center justify-between px-3 py-1.5">
                <span className="text-[10px] font-semibold text-on-surface-variant tracking-wider uppercase">
                  SQL
                </span>
                <button
                  onClick={handleCopy}
                  className={cn(
                    'flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium',
                    'hover:bg-surface-container-high transition-colors duration-200 ease-out',
                    copied ? 'text-tertiary' : 'text-on-surface-variant'
                  )}
                >
                  <span className="material-symbols-outlined text-xs">
                    {copied ? 'check' : 'content_copy'}
                  </span>
                  {copied ? 'Copied' : 'Copy'}
                </button>
              </div>
              <pre className="px-3 pb-3 text-[11px] text-on-surface font-mono whitespace-pre-wrap break-all leading-relaxed overflow-x-auto">
                {action.sql}
              </pre>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Risk Badge
// ---------------------------------------------------------------------------

function RiskBadge({ level }: { level: 'low' | 'medium' | 'high' }) {
  const config = {
    low: {
      bg: 'bg-tertiary/15',
      text: 'text-tertiary',
      label: 'Low',
    },
    medium: {
      bg: 'bg-warning/15',
      text: 'text-warning',
      label: 'Medium',
    },
    high: {
      bg: 'bg-error/15',
      text: 'text-error',
      label: 'High',
    },
  }[level];

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold',
        config.bg,
        config.text
      )}
    >
      {level === 'high' && (
        <span className="material-symbols-outlined text-xs">warning</span>
      )}
      {config.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Meta Item
// ---------------------------------------------------------------------------

function MetaItem({
  icon,
  label,
  children,
}: {
  icon: string;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-w-[100px]">
      <div className="flex items-center gap-1 mb-0.5">
        <span className="material-symbols-outlined text-xs text-on-surface-variant">
          {icon}
        </span>
        <span className="text-[10px] font-semibold tracking-wider uppercase text-on-surface-variant">
          {label}
        </span>
      </div>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// History Panel
// ---------------------------------------------------------------------------

interface HistoryPanelProps {
  history: Array<{
    id: string;
    question: string;
    analysis: string;
    actions: TuningAction[];
    tools_used: string[];
    model_used: string;
    duration_ms: number;
    created_at: string;
  }>;
  isLoading: boolean;
  instanceSelected: boolean;
  onItemClick: (item: {
    question: string;
    analysis: string;
    actions: TuningAction[];
    tools_used: string[];
    model_used: string;
    duration_ms: number;
  }) => void;
}

function HistoryPanel({
  history,
  isLoading,
  instanceSelected,
  onItemClick,
}: HistoryPanelProps) {
  return (
    <div className="bg-surface-container rounded-xl overflow-hidden">
      <div className="px-5 py-3 flex items-center gap-2">
        <span className="material-symbols-outlined text-lg text-on-surface-variant">
          history
        </span>
        <h2 className="text-sm font-semibold text-on-surface">
          Analysis History
        </h2>
      </div>

      <div className="h-px bg-outline-variant mx-4" />

      <div className="max-h-[600px] overflow-y-auto">
        {!instanceSelected && (
          <div className="px-5 py-8 text-center">
            <span className="material-symbols-outlined text-3xl text-outline block mb-2">
              database
            </span>
            <p className="text-xs text-on-surface-variant">
              Select an instance to view analysis history
            </p>
          </div>
        )}

        {instanceSelected && isLoading && (
          <div className="px-5 py-8 text-center">
            <span className="material-symbols-outlined text-2xl text-primary animate-spin block mb-2">
              progress_activity
            </span>
            <p className="text-xs text-on-surface-variant">
              Loading history...
            </p>
          </div>
        )}

        {instanceSelected && !isLoading && history.length === 0 && (
          <div className="px-5 py-8 text-center">
            <span className="material-symbols-outlined text-3xl text-outline block mb-2">
              search_off
            </span>
            <p className="text-xs text-on-surface-variant">
              No analyses yet for this instance
            </p>
          </div>
        )}

        {history.map((item) => (
          <button
            key={item.id}
            onClick={() => onItemClick(item)}
            className={cn(
              'w-full text-left px-5 py-3 space-y-1',
              'hover:bg-surface-container-high transition-colors duration-200 ease-out',
              'focus:outline-none focus:bg-surface-container-high'
            )}
          >
            <p className="text-xs text-on-surface font-medium line-clamp-2">
              {item.question}
            </p>
            <div className="flex items-center gap-3 text-[10px] text-on-surface-variant">
              <span className="tabular-nums">
                {format(new Date(item.created_at), 'MMM d, HH:mm')}
              </span>
              <span>{(item.duration_ms / 1000).toFixed(1)}s</span>
              <span>{item.tools_used.length} tools</span>
              <span>{item.actions.length} actions</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
