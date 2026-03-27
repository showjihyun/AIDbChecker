// Spec: FS-AI-005 — AIGC Report 생성 페이지
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/api/client';
import { ConfidenceBadge } from '@/components/ai/ConfidenceBadge';
import { ReActTracePanel } from '@/components/ai/ReActTracePanel';

interface ReportResponse {
  report_id: string;
  title: string;
  executive_summary: string;
  sections: { title: string; content: string; severity: string | null }[];
  recommendations: { priority: string; title: string; description: string; action: string | null; confidence: number }[];
  confidence: number;
  generation_time_ms: number;
  ai_model: string;
  status: string;
  trace?: { agent: string; steps: { step_type: 'thought' | 'action' | 'observation' | 'result' | 'error'; content: string; timestamp_ms: number }[]; total_duration_ms: number; status: 'running' | 'completed' | 'failed' };
}

const severityColors: Record<string, string> = {
  good: 'border-l-tertiary',
  warning: 'border-l-amber-500',
  critical: 'border-l-error',
};

export function ReportsPage() {
  const [period, setPeriod] = useState('7d');

  const generate = useMutation<ReportResponse>({
    mutationFn: () =>
      apiClient.post('/reports/generate', {
        period,
        report_type: 'health',
        language: 'ko',
      }),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-headline font-bold text-on-surface">AIGC Reports</h1>
        <div className="flex items-center gap-2">
          <select
            value={period}
            onChange={e => setPeriod(e.target.value)}
            className="bg-surface-container text-xs text-on-surface rounded-lg px-3 py-1.5 border border-white/10"
          >
            <option value="1d">1일</option>
            <option value="7d">7일</option>
            <option value="30d">30일</option>
          </select>
          <button
            onClick={() => generate.mutate()}
            disabled={generate.isPending}
            className="bg-primary text-on-primary text-xs font-semibold px-4 py-1.5 rounded-lg hover:bg-primary/80 transition-colors disabled:opacity-50"
          >
            {generate.isPending ? 'Generating...' : 'Generate Report'}
          </button>
        </div>
      </div>

      {/* Error */}
      {generate.isError && (
        <div className="bg-error/10 text-error text-xs rounded-xl p-4">
          Report generation failed. Check LLM configuration.
        </div>
      )}

      {/* Report result */}
      {generate.data && (
        <div className="space-y-4">
          {/* Header */}
          <div className="bg-surface-container rounded-xl p-5 border border-secondary/20">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-sm font-headline font-bold text-on-surface">
                {generate.data.title}
              </h2>
              <ConfidenceBadge confidence={generate.data.confidence} />
            </div>
            <p className="text-xs text-on-surface-variant">{generate.data.executive_summary}</p>
            <div className="flex items-center gap-3 mt-2 text-[10px] text-on-surface-variant">
              <span>{generate.data.ai_model}</span>
              <span>·</span>
              <span>{generate.data.generation_time_ms}ms</span>
            </div>
          </div>

          {/* Trace */}
          {generate.data.trace && (
            <ReActTracePanel trace={generate.data.trace} />
          )}

          {/* Sections */}
          {generate.data.sections.map((section, i) => (
            <div
              key={i}
              className={`bg-surface-container rounded-xl p-5 border-l-4 ${
                severityColors[section.severity || 'good'] || 'border-l-white/10'
              }`}
            >
              <h3 className="text-sm font-semibold text-on-surface">{section.title}</h3>
              <div className="text-xs text-on-surface-variant mt-2 whitespace-pre-wrap">
                {section.content}
              </div>
            </div>
          ))}

          {/* Recommendations */}
          {generate.data.recommendations.length > 0 && (
            <div className="bg-surface-container rounded-xl p-5 border border-white/5">
              <h3 className="text-sm font-headline font-semibold text-secondary mb-3">
                AI Recommendations
              </h3>
              {generate.data.recommendations.map((rec, i) => (
                <div key={i} className="bg-surface-container-high rounded-lg px-4 py-3 mb-2">
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-bold uppercase ${
                      rec.priority === 'high' ? 'text-error' :
                      rec.priority === 'medium' ? 'text-amber-500' : 'text-tertiary'
                    }`}>
                      {rec.priority}
                    </span>
                    <span className="text-xs font-medium text-on-surface">{rec.title}</span>
                  </div>
                  <p className="text-xs text-on-surface-variant mt-1">{rec.description}</p>
                  {rec.action && (
                    <pre className="text-[10px] font-mono text-secondary mt-1">{rec.action}</pre>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {!generate.data && !generate.isPending && (
        <div className="text-center py-16">
          <span className="material-symbols-outlined text-4xl text-on-surface-variant/40">summarize</span>
          <p className="text-sm text-on-surface-variant mt-3">AI 리포트를 생성하세요</p>
          <p className="text-xs text-on-surface-variant/60 mt-1">
            메트릭, 인시던트, ASH 데이터를 분석하여 건강 리포트를 자동 생성합니다
          </p>
        </div>
      )}
    </div>
  );
}
