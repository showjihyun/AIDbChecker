// Spec: MVP-DASH, MVP.md §4.6 — NL2SQL floating chat widget
import { useState, useRef, useEffect, useCallback } from 'react';
import { cn } from '@/lib/cn';
import { apiClient } from '@/api/client';
import { useMetricStore } from '@/stores/metricStore';

/** Matches backend NL2SQLQueryResponse schema exactly */
interface NL2SQLApiResponse {
  sql: string;
  result_rows: unknown[][];
  result_columns: string[];
  execution_time_ms: number;
  ai_model: string;
  warning: string | null;
}

/** Internal display format */
interface NL2SQLResult {
  generated_sql: string;
  execution_result: {
    columns: string[];
    rows: unknown[][];
  } | null;
  execution_time_ms: number;
  ai_model: string;
  warning: string | null;
}

interface ChatEntry {
  id: string;
  query: string;
  result: NL2SQLResult | null;
  isLoading: boolean;
  error: string | null;
}

const MAX_HISTORY = 5;

export function NL2SQLChat() {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState('');
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const selectedInstanceId = useMetricStore((s) => s.selectedInstanceId);

  // Auto-scroll to bottom on new entries
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [entries]);

  // Focus input when panel opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  const handleSubmit = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed) return;

    const entryId = crypto.randomUUID();
    const newEntry: ChatEntry = {
      id: entryId,
      query: trimmed,
      result: null,
      isLoading: true,
      error: null,
    };

    setEntries((prev) => [...prev.slice(-(MAX_HISTORY - 1)), newEntry]);
    setInput('');

    try {
      if (!selectedInstanceId) {
        throw { detail: '인스턴스를 먼저 선택하세요. 대시보드에서 인스턴스를 클릭한 후 질의하세요.' };
      }

      const apiResponse = await apiClient.post<NL2SQLApiResponse>('/nl2sql/query', {
        question: trimmed,
        instance_id: selectedInstanceId,
      });

      // Transform backend response to display format
      const result: NL2SQLResult = {
        generated_sql: apiResponse.sql,
        execution_result:
          apiResponse.result_columns.length > 0
            ? { columns: apiResponse.result_columns, rows: apiResponse.result_rows }
            : null,
        execution_time_ms: apiResponse.execution_time_ms,
        ai_model: apiResponse.ai_model,
        warning: apiResponse.warning,
      };

      setEntries((prev) =>
        prev.map((e) =>
          e.id === entryId ? { ...e, result, isLoading: false } : e
        )
      );
    } catch (err) {
      const raw = (err as { detail?: string | object })?.detail;
      const message = typeof raw === 'string' ? raw : 'Failed to process query.';
      setEntries((prev) =>
        prev.map((e) =>
          e.id === entryId ? { ...e, error: message, isLoading: false } : e
        )
      );
    }
  }, [input, selectedInstanceId]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <>
      {/* Floating toggle button */}
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        className={cn(
          'fixed bottom-6 right-6 z-50',
          'w-14 h-14 rounded-full',
          'bg-primary text-on-primary',
          'flex items-center justify-center',
          'shadow-neural-glow hover:shadow-lg',
          'transition-all duration-200 ease-out',
          'hover:scale-105 active:scale-95'
        )}
        aria-label={isOpen ? 'Close NL2SQL chat' : 'Open NL2SQL chat'}
      >
        <span className="material-symbols-outlined text-2xl">
          {isOpen ? 'close' : 'chat'}
        </span>
      </button>

      {/* Chat panel */}
      {isOpen && (
        <div
          className={cn(
            'fixed bottom-24 right-6 z-50',
            'w-[400px] max-h-[520px]',
            'bg-surface-container rounded-2xl',
            'shadow-neural-glow',
            'flex flex-col',
            'overflow-hidden'
          )}
        >
          {/* Header */}
          <div className="px-4 py-3 flex items-center gap-2 shrink-0">
            <span className="material-symbols-outlined text-lg text-primary">
              database
            </span>
            <h3 className="text-sm font-semibold text-on-surface">
              NL2SQL Query
            </h3>
            <span className="text-[10px] text-on-surface-variant ml-auto tracking-wider uppercase">
              Natural Language
            </span>
          </div>

          <div className="h-px bg-outline-variant mx-3" />

          {/* Chat history */}
          <div
            ref={scrollRef}
            className="flex-1 overflow-y-auto px-4 py-3 space-y-4 min-h-0"
          >
            {entries.length === 0 && (
              <div className="text-center py-8">
                <span className="material-symbols-outlined text-4xl text-outline mb-2 block">
                  psychology
                </span>
                <p className="text-xs text-on-surface-variant">
                  Ask a question about your databases in natural language.
                </p>
                <p className="text-[10px] text-outline mt-1">
                  e.g. "Show the top 5 slowest queries"
                </p>
              </div>
            )}

            {entries.map((entry) => (
              <div key={entry.id} className="space-y-2">
                {/* User query */}
                <div className="flex justify-end">
                  <div className="bg-primary/10 text-on-surface text-xs rounded-xl rounded-br-sm px-3 py-2 max-w-[85%]">
                    {entry.query}
                  </div>
                </div>

                {/* Response */}
                {entry.isLoading && (
                  <div className="flex items-center gap-2 text-on-surface-variant">
                    <LoadingDots />
                    <span className="text-xs">Generating SQL...</span>
                  </div>
                )}

                {entry.error && (
                  <div className="bg-error/10 text-error text-xs rounded-xl rounded-bl-sm px-3 py-2">
                    {entry.error}
                  </div>
                )}

                {entry.result && (
                  <div className="space-y-2">
                    {/* Generated SQL */}
                    <div className="bg-surface-container-high rounded-lg overflow-hidden">
                      <div className="px-3 py-1.5 flex items-center justify-between">
                        <div className="flex items-center gap-1.5">
                          <span className="material-symbols-outlined text-xs text-primary">
                            code
                          </span>
                          <span className="text-[10px] font-semibold text-on-surface-variant tracking-wider uppercase">
                            Generated SQL
                          </span>
                        </div>
                        <span className="text-[9px] text-outline">
                          {entry.result.ai_model} · {entry.result.execution_time_ms}ms
                        </span>
                      </div>
                      <pre className="px-3 pb-2 text-[11px] text-on-surface font-mono whitespace-pre-wrap break-all leading-relaxed">
                        {entry.result.generated_sql}
                      </pre>
                    </div>

                    {/* Warning */}
                    {entry.result.warning && (
                      <div className="bg-warning/10 text-warning text-xs rounded-lg px-3 py-2">
                        {entry.result.warning}
                      </div>
                    )}

                    {/* Result table */}
                    {entry.result.execution_result && (
                      <ResultTable data={entry.result.execution_result} />
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="h-px bg-outline-variant mx-3" />

          {/* Input */}
          <div className="px-3 py-3 flex items-center gap-2 shrink-0">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={selectedInstanceId ? "Ask about your database..." : "인스턴스를 먼저 선택하세요"}
              className={cn(
                'flex-1 bg-surface-container-high rounded-lg',
                'px-3 py-2 text-xs text-on-surface',
                'placeholder:text-outline',
                'outline-none focus:ring-1 focus:ring-primary/50',
                'transition-shadow duration-200 ease-out'
              )}
            />
            <button
              onClick={handleSubmit}
              disabled={!input.trim()}
              className={cn(
                'w-8 h-8 rounded-lg flex items-center justify-center',
                'bg-primary text-on-primary',
                'disabled:opacity-30 disabled:cursor-not-allowed',
                'hover:opacity-90 active:scale-95',
                'transition-all duration-200 ease-out'
              )}
              aria-label="Send query"
            >
              <span className="material-symbols-outlined text-lg">send</span>
            </button>
          </div>
        </div>
      )}
    </>
  );
}

/** Compact result table for NL2SQL query output. */
function ResultTable({
  data,
}: {
  data: { columns: string[]; rows: unknown[][] };
}) {
  if (!data.columns.length || !data.rows.length) {
    return (
      <p className="text-[10px] text-on-surface-variant italic px-1">
        Query returned no rows.
      </p>
    );
  }

  const displayRows = data.rows.slice(0, 20);

  return (
    <div className="rounded-lg overflow-hidden bg-surface-container-high">
      <div className="overflow-x-auto max-h-[160px] overflow-y-auto">
        <table className="w-full text-[10px]">
          <thead>
            <tr className="bg-surface-container-highest">
              {data.columns.map((col) => (
                <th
                  key={col}
                  className="px-2 py-1.5 text-left font-semibold text-on-surface-variant whitespace-nowrap"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayRows.map((row, i) => (
              <tr
                key={i}
                className="hover:bg-surface-container-highest/50 transition-colors"
              >
                {row.map((cell, j) => (
                  <td
                    key={j}
                    className="px-2 py-1 text-on-surface whitespace-nowrap max-w-[150px] truncate"
                    title={String(cell ?? '')}
                  >
                    {cell === null ? (
                      <span className="text-outline italic">NULL</span>
                    ) : (
                      String(cell)
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.rows.length > 20 && (
        <p className="px-2 py-1 text-[10px] text-on-surface-variant text-center">
          Showing 20 of {data.rows.length} rows
        </p>
      )}
    </div>
  );
}

/** Simple loading dots animation. */
function LoadingDots() {
  return (
    <div className="flex gap-1">
      <span className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce [animation-delay:0ms]" />
      <span className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce [animation-delay:150ms]" />
      <span className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce [animation-delay:300ms]" />
    </div>
  );
}
