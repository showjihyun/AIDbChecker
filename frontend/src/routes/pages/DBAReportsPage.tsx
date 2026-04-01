// Spec: FS-AI-REPORT-002 — DBA Report list + PDF download + manual generation
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
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

interface InstanceItem {
  id: string;
  name: string;
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

// Default dates: today and 1 day ago
function todayStr() {
  return new Date().toISOString().slice(0, 10);
}
function daysAgoStr(days: number) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

export function DBAReportsPage() {
  const queryClient = useQueryClient();
  const [periodFilter, setPeriodFilter] = useState<string>('');

  // --- Generate Report Form ---
  const [genOpen, setGenOpen] = useState(false);
  const [genInstanceId, setGenInstanceId] = useState('');
  const [genPeriod, setGenPeriod] = useState('daily');
  const [genSlack, setGenSlack] = useState(true);
  const [genFrom, setGenFrom] = useState(daysAgoStr(1));
  const [genTo, setGenTo] = useState(todayStr());
  const [genLimit, setGenLimit] = useState(10);

  // Instance list
  const { data: instancesData } = useQuery({
    queryKey: ['instances-for-report'],
    queryFn: () => apiClient.get<{ items: InstanceItem[] }>('/instances'),
    staleTime: 60_000,
  });
  const instances = instancesData?.items ?? [];

  // Report list
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

  // Generate report mutation
  const generateMutation = useMutation({
    mutationFn: () =>
      apiClient.post('/reports/dba', {
        instance_id: genInstanceId,
        period: genPeriod,
        send_slack: genSlack,
        slow_query_limit: genLimit,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dba-reports'] });
      setGenOpen(false);
    },
  });

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

  // Auto-set From date when period changes
  const handlePeriodChange = (p: string) => {
    setGenPeriod(p);
    const days = p === 'monthly' ? 30 : p === 'weekly' ? 7 : 1;
    setGenFrom(daysAgoStr(days));
    setGenTo(todayStr());
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
        <div className="flex items-center gap-3">
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
          <span className="text-xs text-on-surface-variant">총 {total}건</span>

          {/* Generate Report button */}
          <button
            onClick={() => {
              setGenOpen(!genOpen);
              if (!genInstanceId && instances.length > 0) {
                setGenInstanceId(instances[0].id);
              }
            }}
            className="flex items-center gap-1.5 bg-primary hover:bg-primary/80 text-on-primary rounded-lg px-4 py-2 text-xs font-semibold transition-colors"
          >
            <span className="material-symbols-outlined text-sm">add_chart</span>
            리포트 생성
          </button>
        </div>
      </div>

      {/* Generate Report Form (collapsible) */}
      {genOpen && (
        <div className="px-6 py-4 border-b border-white/5 bg-surface-container/50">
          <div className="flex flex-wrap items-end gap-4">
            {/* Instance */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-on-surface-variant uppercase tracking-wider font-semibold">
                인스턴스
              </label>
              <select
                value={genInstanceId}
                onChange={(e) => setGenInstanceId(e.target.value)}
                className="bg-surface-container text-on-surface text-xs rounded-lg px-3 py-2 border border-white/10 min-w-[160px]"
              >
                {instances.map((inst) => (
                  <option key={inst.id} value={inst.id}>
                    {inst.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Period */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-on-surface-variant uppercase tracking-wider font-semibold">
                유형
              </label>
              <select
                value={genPeriod}
                onChange={(e) => handlePeriodChange(e.target.value)}
                className="bg-surface-container text-on-surface text-xs rounded-lg px-3 py-2 border border-white/10"
              >
                <option value="daily">일간</option>
                <option value="weekly">주간</option>
                <option value="monthly">월간</option>
              </select>
            </div>

            {/* From date */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-on-surface-variant uppercase tracking-wider font-semibold">
                From
              </label>
              <input
                type="date"
                value={genFrom}
                onChange={(e) => setGenFrom(e.target.value)}
                className="bg-surface-container text-on-surface text-xs rounded-lg px-3 py-2 border border-white/10"
              />
            </div>

            {/* To date */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-on-surface-variant uppercase tracking-wider font-semibold">
                To
              </label>
              <input
                type="date"
                value={genTo}
                onChange={(e) => setGenTo(e.target.value)}
                className="bg-surface-container text-on-surface text-xs rounded-lg px-3 py-2 border border-white/10"
              />
            </div>

            {/* Slow Query Limit */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-on-surface-variant uppercase tracking-wider font-semibold">
                Slow Query Top
              </label>
              <input
                type="number"
                value={genLimit}
                onChange={(e) => setGenLimit(Number(e.target.value))}
                min={1}
                max={50}
                className="bg-surface-container text-on-surface text-xs rounded-lg px-3 py-2 border border-white/10 w-20"
              />
            </div>

            {/* Slack toggle */}
            <label className="flex items-center gap-2 text-xs text-on-surface-variant cursor-pointer">
              <input
                type="checkbox"
                checked={genSlack}
                onChange={(e) => setGenSlack(e.target.checked)}
                className="rounded"
              />
              Slack 발송
            </label>

            {/* Submit */}
            <button
              onClick={() => generateMutation.mutate()}
              disabled={!genInstanceId || generateMutation.isPending}
              className="flex items-center gap-1.5 bg-green-600 hover:bg-green-500 disabled:opacity-30 text-white rounded-lg px-4 py-2 text-xs font-semibold transition-colors"
            >
              {generateMutation.isPending ? (
                <>
                  <span className="animate-spin material-symbols-outlined text-sm">progress_activity</span>
                  생성 중...
                </>
              ) : (
                <>
                  <span className="material-symbols-outlined text-sm">play_arrow</span>
                  생성
                </>
              )}
            </button>
          </div>

          {generateMutation.isError && (
            <p className="mt-2 text-xs text-red-400">
              생성 실패: {(generateMutation.error as { detail?: string })?.detail ?? 'Unknown error'}
            </p>
          )}
          {generateMutation.isSuccess && (
            <p className="mt-2 text-xs text-green-400">리포트가 생성되었습니다.</p>
          )}
        </div>
      )}

      {/* Report list */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {isLoading ? (
          <div className="flex items-center justify-center h-40">
            <div className="animate-pulse text-on-surface-variant text-sm">Loading...</div>
          </div>
        ) : reports.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 text-on-surface-variant">
            <span className="material-symbols-outlined text-4xl mb-2 opacity-30">summarize</span>
            <p className="text-sm">리포트가 없습니다</p>
            <p className="text-xs opacity-60">
              상단의 "리포트 생성" 버튼으로 수동 생성하거나, Celery Beat 스케줄로 자동 생성됩니다
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
                      <span>{r.start_at?.slice(0, 10)} ~ {r.end_at?.slice(0, 10)}</span>
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
