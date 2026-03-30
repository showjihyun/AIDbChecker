// Spec: FS-DBA-002 — DBA Agent Chat UI
import { useState, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { cn } from '@/lib/cn';
import { apiClient } from '@/api/client';
import { useMetricStore } from '@/stores/metricStore';

interface ActionSummary {
  action_id: string | null;
  action_type: string;
  sql: string;
  risk_level: string;
  status: string;
  description: string;
}

interface DBAResponse {
  session_id: string;
  intent: string;
  answer: string;
  data: Record<string, unknown> | null;
  actions: ActionSummary[] | null;
  model: string;
  processing_time_ms: number;
}

interface QueryData {
  sql?: string;
  columns?: string[];
  rows?: unknown[][];
}

interface ChatMessage {
  id: string;
  role: 'user' | 'agent';
  content: string;
  intent?: string;
  actions?: ActionSummary[];
  data?: QueryData | null;
  model?: string;
  time_ms?: number;
  isLoading?: boolean;
  error?: string;
  feedback?: 'positive' | 'negative';
}

const INTENT_ICONS: Record<string, string> = {
  analyze: 'speed',
  diagnose: 'troubleshoot',
  execute: 'play_arrow',
  query: 'table_chart',
  status: 'monitor_heart',
};

const INTENT_COLORS: Record<string, string> = {
  analyze: 'text-blue-400',
  diagnose: 'text-orange-400',
  execute: 'text-red-400',
  query: 'text-green-400',
  status: 'text-cyan-400',
};

const RISK_COLORS: Record<string, string> = {
  safe: 'bg-green-500/20 text-green-400',
  warning: 'bg-yellow-500/20 text-yellow-400',
  dangerous: 'bg-red-500/20 text-red-400',
  critical: 'bg-red-700/30 text-red-300',
};

export function DBAAgentPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const selectedInstanceId = useMetricStore((s) => s.selectedInstanceId);
  const { data: instancesData } = useQuery({
    queryKey: ['instances-list'],
    queryFn: () => apiClient.get<{ items: Array<{ id: string; name: string }> }>('/instances'),
    staleTime: 60_000,
  });
  const instances = instancesData?.items ?? [];

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // AC-19: Submit feedback on agent response
  const handleFeedback = async (messageId: string, feedback: 'positive' | 'negative', content?: string, intent?: string) => {
    if (!sessionId) return;
    try {
      await apiClient.post('/dba/feedback', {
        session_id: sessionId,
        message_id: messageId,
        feedback,
        question: content,
        intent,
      });
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId ? { ...m, feedback } : m
        )
      );
    } catch {
      // Silent fail — feedback is non-critical
    }
  };

  const handleSend = async () => {
    const q = input.trim();
    if (!q || isLoading) return;
    if (!selectedInstanceId) {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'agent',
          content: 'Please select a DB instance first.',
          error: 'No instance selected',
        },
      ]);
      return;
    }

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: q,
    };
    const loadingMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'agent',
      content: '',
      isLoading: true,
    };

    setMessages((prev) => [...prev, userMsg, loadingMsg]);
    setInput('');
    setIsLoading(true);

    try {
      const res = await apiClient.post<DBAResponse>('/dba/ask', {
        question: q,
        instance_id: selectedInstanceId,
        session_id: sessionId,
      });
      setSessionId(res.session_id);

      const agentMsg: ChatMessage = {
        id: loadingMsg.id,
        role: 'agent',
        content: res.answer,
        intent: res.intent,
        actions: res.actions ?? undefined,
        data: res.data as QueryData | null,
        model: res.model,
        time_ms: res.processing_time_ms,
      };

      setMessages((prev) =>
        prev.map((m) => (m.id === loadingMsg.id ? agentMsg : m))
      );
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : 'Unknown error';
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? { ...m, isLoading: false, content: errMsg, error: errMsg }
            : m
        )
      );
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
        <div>
          <h1 className="text-lg font-semibold text-on-surface">DBA Agent</h1>
          <p className="text-xs text-on-surface-variant">
            AI-powered database administration assistant
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-on-surface-variant">
          <span className="material-symbols-outlined text-sm">dns</span>
          <span>
            {instances.find((i) => i.id === selectedInstanceId)?.name ??
              'No instance selected'}
          </span>
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-on-surface-variant">
            <span className="material-symbols-outlined text-5xl mb-3 opacity-30">
              smart_toy
            </span>
            <p className="text-sm font-medium mb-1">DBA Agent Ready</p>
            <p className="text-xs opacity-60 text-center max-w-md">
              Ask about performance, diagnose issues, execute operations, or
              query your database. Examples:
            </p>
            <div className="mt-3 space-y-1 text-xs opacity-50">
              <p>&quot;Why are queries slow?&quot;</p>
              <p>&quot;Show recent incidents&quot;</p>
              <p>&quot;Create index on orders(user_id)&quot;</p>
              <p>&quot;System health check&quot;</p>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={cn(
              'flex gap-3',
              msg.role === 'user' ? 'justify-end' : 'justify-start'
            )}
          >
            {msg.role === 'agent' && (
              <div className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-1">
                <span className="material-symbols-outlined text-sm text-primary">
                  smart_toy
                </span>
              </div>
            )}

            <div
              className={cn(
                'max-w-[75%] rounded-xl px-4 py-3',
                msg.role === 'user'
                  ? 'bg-primary/20 text-on-surface'
                  : 'bg-surface-container text-on-surface'
              )}
            >
              {msg.isLoading ? (
                <div className="flex items-center gap-2 text-on-surface-variant">
                  <div className="animate-pulse flex gap-1">
                    <div className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" />
                    <div className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce [animation-delay:0.1s]" />
                    <div className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce [animation-delay:0.2s]" />
                  </div>
                  <span className="text-xs">Analyzing...</span>
                </div>
              ) : (
                <>
                  {/* Intent badge */}
                  {msg.intent && (
                    <div className="flex items-center gap-1.5 mb-2">
                      <span
                        className={cn(
                          'material-symbols-outlined text-sm',
                          INTENT_COLORS[msg.intent] ?? 'text-on-surface-variant'
                        )}
                      >
                        {INTENT_ICONS[msg.intent] ?? 'chat'}
                      </span>
                      <span className="text-[10px] uppercase tracking-wider font-semibold text-on-surface-variant">
                        {msg.intent}
                      </span>
                    </div>
                  )}

                  {/* Error */}
                  {msg.error && (
                    <p className="text-xs text-error mb-1">{msg.error}</p>
                  )}

                  {/* Content */}
                  <pre className="text-sm whitespace-pre-wrap font-sans leading-relaxed">
                    {msg.content}
                  </pre>

                  {/* Actions */}
                  {msg.actions && msg.actions.length > 0 && (
                    <div className="mt-3 space-y-2">
                      <p className="text-[10px] uppercase tracking-wider text-on-surface-variant font-semibold">
                        Actions
                      </p>
                      {msg.actions.map((action: ActionSummary, i: number) => (
                        <div
                          key={i}
                          className="bg-surface-container-high rounded-lg p-3 text-xs"
                        >
                          <div className="flex items-center gap-2 mb-1">
                            <span
                              className={cn(
                                'px-1.5 py-0.5 rounded text-[10px] font-bold',
                                RISK_COLORS[action.risk_level] ??
                                  'bg-white/10 text-white/60'
                              )}
                            >
                              {action.risk_level.toUpperCase()}
                            </span>
                            <span className="font-semibold">
                              {action.action_type}
                            </span>
                            <span
                              className={cn(
                                'ml-auto text-[10px]',
                                action.status === 'executed'
                                  ? 'text-green-400'
                                  : action.status === 'pending'
                                    ? 'text-yellow-400'
                                    : 'text-on-surface-variant'
                              )}
                            >
                              {action.status}
                            </span>
                          </div>
                          <p className="text-on-surface-variant">
                            {action.description}
                          </p>
                          <code className="block mt-1 text-[11px] text-primary/80 bg-black/20 rounded px-2 py-1">
                            {action.sql}
                          </code>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Query result table (intent=query) */}
                  {msg.data?.columns && msg.data.columns.length > 0 && (
                    <div className="mt-3 overflow-x-auto">
                      {msg.data.sql && (
                        <code className="block text-[11px] text-primary/80 bg-black/20 rounded px-2 py-1 mb-2">
                          {msg.data.sql}
                        </code>
                      )}
                      <table className="w-full text-xs border-collapse">
                        <thead>
                          <tr className="border-b border-white/10">
                            {msg.data.columns.map((col: string) => (
                              <th
                                key={col}
                                className="text-left px-2 py-1 text-on-surface-variant font-semibold"
                              >
                                {col}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {(msg.data.rows ?? []).slice(0, 20).map((row: unknown[], ri: number) => (
                            <tr key={ri} className="border-b border-white/5">
                              {row.map((cell: unknown, ci: number) => (
                                <td key={ci} className="px-2 py-1 text-on-surface/80 font-mono">
                                  {cell == null ? '—' : String(cell)}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {(msg.data.rows?.length ?? 0) > 20 && (
                        <p className="text-[10px] text-on-surface-variant/50 mt-1">
                          Showing 20 of {msg.data.rows?.length} rows
                        </p>
                      )}
                    </div>
                  )}

                  {/* AC-19: Feedback + meta */}
                  {msg.role === 'agent' && !msg.isLoading && !msg.error && (
                    <div className="flex items-center gap-3 mt-2">
                      <button
                        onClick={() => handleFeedback(msg.id, 'positive', msg.content, msg.intent)}
                        disabled={!!msg.feedback}
                        className={cn(
                          'transition-colors',
                          msg.feedback === 'positive' ? 'text-green-400' : 'text-on-surface-variant/30 hover:text-green-400'
                        )}
                        title="Good answer"
                      >
                        <span className="material-symbols-outlined text-sm">thumb_up</span>
                      </button>
                      <button
                        onClick={() => handleFeedback(msg.id, 'negative', msg.content, msg.intent)}
                        disabled={!!msg.feedback}
                        className={cn(
                          'transition-colors',
                          msg.feedback === 'negative' ? 'text-red-400' : 'text-on-surface-variant/30 hover:text-red-400'
                        )}
                        title="Bad answer"
                      >
                        <span className="material-symbols-outlined text-sm">thumb_down</span>
                      </button>
                      {msg.model && (
                        <span className="text-[10px] text-on-surface-variant/50 ml-auto">
                          {msg.model}{msg.time_ms ? ` · ${msg.time_ms}ms` : ''}
                        </span>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>

            {msg.role === 'user' && (
              <div className="w-7 h-7 rounded-full bg-surface-container-high flex items-center justify-center flex-shrink-0 mt-1">
                <span className="material-symbols-outlined text-sm text-on-surface-variant">
                  person
                </span>
              </div>
            )}
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>

      {/* Input */}
      <div className="px-6 py-4 border-t border-white/5">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Ask the DBA Agent..."
            disabled={isLoading}
            className="flex-1 bg-surface-container rounded-xl px-4 py-3 text-sm text-on-surface placeholder:text-on-surface-variant/40 outline-none focus:ring-1 focus:ring-primary/50"
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className="bg-primary hover:bg-primary/80 disabled:opacity-30 text-on-primary rounded-xl px-4 py-3 transition-colors"
          >
            <span className="material-symbols-outlined text-sm">send</span>
          </button>
        </div>
      </div>
    </div>
  );
}
