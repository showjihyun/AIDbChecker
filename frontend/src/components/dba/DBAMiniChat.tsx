// Spec: FS-DBA-002 AC-11~13 — DBA Agent mini chat widget (bottom-right)
import { useState, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { cn } from '@/lib/cn';
import { apiClient } from '@/api/client';

// ── Types ────────────────────────────────────────────────

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
  analyze: 'speed', diagnose: 'troubleshoot', execute: 'play_arrow',
  query: 'table_chart', status: 'monitor_heart',
};

const INTENT_COLORS: Record<string, string> = {
  analyze: 'text-blue-400', diagnose: 'text-orange-400', execute: 'text-red-400',
  query: 'text-green-400', status: 'text-cyan-400',
};

const RISK_COLORS: Record<string, string> = {
  safe: 'bg-green-500/20 text-green-400', warning: 'bg-yellow-500/20 text-yellow-400',
  dangerous: 'bg-red-500/20 text-red-400', critical: 'bg-red-700/30 text-red-300',
};

// ── Component ────────────────────────────────────────────

export function DBAMiniChat() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedInstanceId, setSelectedInstanceId] = useState<string>('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Spec: AC-12 — fetch instance list for dropdown
  const { data: instancesData } = useQuery({
    queryKey: ['instances-mini'],
    queryFn: () => apiClient.get<{ items: Array<{ id: string; name: string }> }>('/instances'),
    staleTime: 60_000,
  });
  const instances = instancesData?.items ?? [];

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

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
    if (!q || isLoading || !selectedInstanceId) return;

    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: 'user', content: q };
    const loadingMsg: ChatMessage = { id: crypto.randomUUID(), role: 'agent', content: '', isLoading: true };
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
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? {
                ...m,
                isLoading: false,
                content: res.answer,
                intent: res.intent,
                actions: res.actions ?? undefined,
                data: res.data as QueryData | null,
                model: res.model,
                time_ms: res.processing_time_ms,
              }
            : m
        )
      );
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : 'Error';
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id ? { ...m, isLoading: false, content: errMsg, error: errMsg } : m
        )
      );
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  // ── Collapsed: floating button ──
  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-50 bg-primary hover:bg-primary/80 text-on-primary rounded-full w-14 h-14 flex items-center justify-center shadow-lg transition-transform hover:scale-105"
        aria-label="Open DBA Agent"
      >
        <span className="material-symbols-outlined text-2xl">smart_toy</span>
      </button>
    );
  }

  // ── Expanded: mini chat ──
  return (
    <div className="fixed bottom-6 right-6 z-50 w-[400px] h-[520px] bg-[#0f1729] border border-white/10 rounded-2xl shadow-2xl flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 bg-surface-container">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-primary text-lg">smart_toy</span>
          <span className="text-sm font-semibold text-on-surface">DBA Agent</span>
        </div>
        <button onClick={() => setIsOpen(false)} className="text-on-surface-variant hover:text-on-surface">
          <span className="material-symbols-outlined text-lg">close</span>
        </button>
      </div>

      {/* Instance selector — Spec: AC-12 */}
      <div className="px-4 py-2 border-b border-white/5">
        <select
          value={selectedInstanceId}
          onChange={(e) => setSelectedInstanceId(e.target.value)}
          className="w-full bg-surface-container-high text-on-surface text-xs rounded-lg px-3 py-2 outline-none"
        >
          <option value="">Select DB Instance...</option>
          {instances.map((inst) => (
            <option key={inst.id} value={inst.id}>{inst.name}</option>
          ))}
        </select>
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 text-sm">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-on-surface-variant opacity-50">
            <span className="material-symbols-outlined text-3xl mb-2">smart_toy</span>
            <p className="text-xs">Ask anything about your database</p>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={cn('flex gap-2', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
            {msg.role === 'agent' && (
              <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="material-symbols-outlined text-xs text-primary">smart_toy</span>
              </div>
            )}
            <div className={cn(
              'max-w-[80%] rounded-lg px-3 py-2 text-xs',
              msg.role === 'user' ? 'bg-primary/20' : 'bg-surface-container'
            )}>
              {msg.isLoading ? (
                <div className="flex items-center gap-1.5 text-on-surface-variant">
                  <div className="animate-pulse flex gap-0.5">
                    <div className="w-1 h-1 rounded-full bg-primary animate-bounce" />
                    <div className="w-1 h-1 rounded-full bg-primary animate-bounce [animation-delay:0.1s]" />
                    <div className="w-1 h-1 rounded-full bg-primary animate-bounce [animation-delay:0.2s]" />
                  </div>
                </div>
              ) : (
                <>
                  {msg.intent && (
                    <div className="flex items-center gap-1 mb-1">
                      <span className={cn('material-symbols-outlined text-xs', INTENT_COLORS[msg.intent] ?? '')}>
                        {INTENT_ICONS[msg.intent] ?? 'chat'}
                      </span>
                      <span className="text-[9px] uppercase tracking-wider font-semibold text-on-surface-variant">
                        {msg.intent}
                      </span>
                    </div>
                  )}
                  {msg.error && <p className="text-[10px] text-error mb-0.5">{msg.error}</p>}
                  <pre className="whitespace-pre-wrap font-sans leading-relaxed">{msg.content}</pre>

                  {/* Actions */}
                  {msg.actions && msg.actions.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {msg.actions.map((a: ActionSummary, i: number) => (
                        <div key={i} className="bg-surface-container-high rounded p-2">
                          <div className="flex items-center gap-1">
                            <span className={cn('px-1 py-0.5 rounded text-[8px] font-bold', RISK_COLORS[a.risk_level] ?? '')}>
                              {a.risk_level.toUpperCase()}
                            </span>
                            <span className="font-semibold text-[10px]">{a.action_type}</span>
                          </div>
                          <code className="block mt-1 text-[9px] text-primary/70 bg-black/20 rounded px-1 py-0.5">{a.sql}</code>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Query results table */}
                  {msg.data?.columns && (msg.data.columns as string[]).length > 0 && (
                    <div className="mt-2 overflow-x-auto">
                      {msg.data.sql && (
                        <code className="block text-[9px] text-primary/70 bg-black/20 rounded px-1 py-0.5 mb-1">{msg.data.sql as string}</code>
                      )}
                      <table className="w-full text-[10px] border-collapse">
                        <thead>
                          <tr className="border-b border-white/10">
                            {(msg.data.columns as string[]).map((col: string) => (
                              <th key={col} className="text-left px-1 py-0.5 text-on-surface-variant font-semibold">{col}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {((msg.data.rows as unknown[][]) ?? []).slice(0, 10).map((row: unknown[], ri: number) => (
                            <tr key={ri} className="border-b border-white/5">
                              {row.map((cell: unknown, ci: number) => (
                                <td key={ci} className="px-1 py-0.5 font-mono">{cell == null ? '—' : String(cell)}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* AC-19: Feedback buttons + meta */}
                  {msg.role === 'agent' && !msg.isLoading && !msg.error && (
                    <div className="flex items-center gap-2 mt-1">
                      <button
                        onClick={() => handleFeedback(msg.id, 'positive', msg.content, msg.intent)}
                        disabled={!!msg.feedback}
                        className={cn(
                          'transition-colors',
                          msg.feedback === 'positive' ? 'text-green-400' : 'text-on-surface-variant/30 hover:text-green-400'
                        )}
                        title="Good answer"
                      >
                        <span className="material-symbols-outlined text-xs">thumb_up</span>
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
                        <span className="material-symbols-outlined text-xs">thumb_down</span>
                      </button>
                      {msg.model && (
                        <span className="text-[8px] text-on-surface-variant/40 ml-auto">
                          {msg.model} · {msg.time_ms}ms
                        </span>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>

      {/* Input — Spec: AC-13: disabled when no instance */}
      <div className="px-4 py-3 border-t border-white/5">
        {!selectedInstanceId ? (
          <p className="text-xs text-on-surface-variant/50 text-center py-1">
            Select a DB instance to start chatting
          </p>
        ) : (
          <div className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Ask the DBA Agent..."
              disabled={isLoading}
              className="flex-1 bg-surface-container rounded-lg px-3 py-2 text-xs text-on-surface placeholder:text-on-surface-variant/40 outline-none focus:ring-1 focus:ring-primary/50"
            />
            <button
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
              className="bg-primary hover:bg-primary/80 disabled:opacity-30 text-on-primary rounded-lg px-3 py-2 transition-colors"
            >
              <span className="material-symbols-outlined text-sm">send</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
