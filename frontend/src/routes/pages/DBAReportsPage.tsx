// Spec: FS-AI-REPORT-002 — DBA Report list + PDF download
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/api/client';

interface ReportSummary {
  id: string;
  instance_name: string;
  period: string;
  start_at: string;
  end_at: string;
  incident_count: number;
  slow_query_count: number;
  slack_sent: boolean;
  created_at: string;
}

const PERIOD_LABEL: Record<string, string> = {
  daily: '일간',
  weekly: '주간',
  monthly: '월간',
};

const PERIOD_COLOR: Record<string, string> = {
  daily: 'bg-blue-500/20 text-blue-400',
  weekly: 'bg-purple-500/20 text-purple-400',
  monthly: 'bg-amber-500/20 text-amber-400',
};

export function DBAReportsPage() {
  const [periodFilter, setPeriodFilter] = useState<string>('');

  // Fetch report list
  const { data, isLoading } = useQuery({
    queryKey: ['dba-reports', periodFilter],
    queryFn: () => {
      const params: Record<string, string> = { limit: '50' };
      if (periodFilter) params.period = periodFilter;
      return apiClient.get<{ items: ReportSummary[]; total: number }>(
        '/reports/dba/list',
        params
      );
    },
    staleTime: 30_000,
  });

  const reports = data?.items ?? [];
  const total = data?.total ?? 0;

  // Download PDF
  const handleDownloadPdf = async (reportId: string, filename: string) => {
    try {
      const token = localStorage.getItem('neuraldb_token');
      const resp = await fetch(
        `${import.meta.env.VITE_API_BASE_URL ?? '/api/v1'}/reports/dba/${reportId}/pdf`,
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );
      if (!resp.ok) throw new Error('PDF download failed');
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('PDF download error:', err);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
        <div>
          <h1 className="text-lg font-semibold text-on-surface">DBA Reports</h1>
          <p className="text-xs text-on-surface-variant">
            일간/주간/월간 DBA 리포트 목록 및 PDF 다운로드
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Period filter */}
          <select
            value={periodFilter}
            onChange={(e) => setPeriodFilter(e.target.value)}
            className="bg-surface-container text-on-surface text-xs rounded-lg px-3 py-2 border border-white/10"
          >
            <option value="">전체</option>
            <option value="daily">일간</option>
            <option value="weekly">주간</option>
            <option value="monthly">월간</option>
          </select>
          <span className="text-xs text-on-surface-variant">
            총 {total}건
          </span>
        </div>
      </div>

      {/* Report list */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {isLoading ? (
          <div className="flex items-center justify-center h-40">
            <div className="animate-pulse text-on-surface-variant text-sm">Loading...</div>
          </div>
        ) : reports.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 text-on-surface-variant">
            <span className="material-symbols-outlined text-4xl mb-2 opacity-30">
              summarize
            </span>
            <p className="text-sm">리포트가 없습니다</p>
            <p className="text-xs opacity-60">
              Celery Beat 스케줄 또는 수동 생성으로 리포트를 생성하세요
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {reports.map((r) => (
              <div
                key={r.id}
                className="bg-surface-container rounded-xl p-4 border border-white/5 hover:border-primary/20 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${PERIOD_COLOR[r.period] ?? 'bg-white/10 text-white/60'}`}
                      >
                        {PERIOD_LABEL[r.period] ?? r.period}
                      </span>
                      <span className="text-sm font-semibold text-on-surface">
                        {r.instance_name}
                      </span>
                      {r.slack_sent && (
                        <span className="text-[10px] text-green-400/60" title="Slack 발송됨">
                          Slack
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-4 text-xs text-on-surface-variant">
                      <span>
                        {r.start_at?.slice(0, 10)} ~ {r.end_at?.slice(0, 10)}
                      </span>
                      <span>
                        인시던트: <strong className="text-on-surface">{r.incident_count}</strong>
                      </span>
                      <span>
                        Slow Query: <strong className="text-on-surface">{r.slow_query_count}</strong>
                      </span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 ml-4">
                    <button
                      onClick={() =>
                        handleDownloadPdf(
                          r.id,
                          `neuraldb-${r.period}-${r.instance_name}-${r.created_at?.slice(0, 10)}.pdf`
                        )
                      }
                      className="flex items-center gap-1 bg-primary/20 hover:bg-primary/30 text-primary rounded-lg px-3 py-1.5 text-xs transition-colors"
                      title="PDF 다운로드"
                    >
                      <span className="material-symbols-outlined text-sm">download</span>
                      PDF
                    </button>
                  </div>
                </div>

                <div className="text-[10px] text-on-surface-variant/40 mt-2">
                  생성: {r.created_at?.slice(0, 19)?.replace('T', ' ')}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
