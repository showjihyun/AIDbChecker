// Spec: FS-AUTO-003 — Playbook Lite 목록 + 상세 페이지
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/api/client';
import { Badge } from '@/components/common/Badge';

interface PlaybookSummary {
  name: string;
  version: string;
  description: string;
  risk_level: string;
  min_autonomy_level: number;
  tags: string[];
  trigger_type: string;
  steps_count: number;
}

interface PlaybookDetail {
  metadata: { name: string; description: string; risk_level: string; min_autonomy_level: number };
  trigger: { type: string; metric?: string; threshold?: number };
  steps: { name: string; type: string; query: string }[];
  yaml_content: string;
}

const riskVariant: Record<string, 'healthy' | 'warning' | 'critical'> = {
  low: 'healthy',
  medium: 'warning',
  high: 'critical',
  critical: 'critical',
};

export function PlaybooksPage() {
  const [selected, setSelected] = useState<string | null>(null);

  const { data: playbooks = [], isLoading } = useQuery<PlaybookSummary[]>({
    queryKey: ['playbooks'],
    queryFn: () => apiClient.get('/playbooks'),
  });

  const { data: detail } = useQuery<PlaybookDetail>({
    queryKey: ['playbooks', selected],
    queryFn: () => apiClient.get(`/playbooks/${selected}`),
    enabled: !!selected,
  });

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-headline font-bold text-on-surface">Playbooks</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {isLoading && [1, 2, 3].map(i => (
          <div key={i} className="bg-surface-container rounded-xl p-5 h-32 animate-pulse" />
        ))}

        {playbooks.map(pb => (
          <button
            key={pb.name}
            onClick={() => setSelected(pb.name)}
            className={`bg-surface-container rounded-xl p-5 text-left border transition-colors hover:bg-surface-container-high ${
              selected === pb.name ? 'border-primary/50' : 'border-white/5'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-semibold text-on-surface">{pb.name}</span>
              <Badge variant={riskVariant[pb.risk_level] || 'warning'}>{pb.risk_level}</Badge>
            </div>
            <p className="text-xs text-on-surface-variant line-clamp-2">{pb.description}</p>
            <div className="flex items-center gap-2 mt-3 text-[10px] text-on-surface-variant">
              <span>L{pb.min_autonomy_level}+</span>
              <span>·</span>
              <span>{pb.steps_count} steps</span>
              <span>·</span>
              <span>{pb.trigger_type}</span>
            </div>
          </button>
        ))}
      </div>

      {/* Detail panel */}
      {detail && (
        <div className="bg-surface-container rounded-xl p-5 border border-white/5">
          <h2 className="text-sm font-headline font-bold text-on-surface mb-3">
            {detail.metadata.name}
          </h2>
          <div className="space-y-3">
            <div>
              <p className="text-[10px] font-bold text-on-surface-variant uppercase">Steps</p>
              {detail.steps.map((step, i) => (
                <div key={i} className="mt-1 bg-surface-container-high rounded-lg px-3 py-2">
                  <span className="text-xs font-medium text-on-surface">{step.name}</span>
                  <pre className="text-[10px] text-on-surface-variant font-mono mt-1 truncate">
                    {step.query}
                  </pre>
                </div>
              ))}
            </div>
            <details>
              <summary className="text-[10px] text-secondary cursor-pointer">YAML 보기</summary>
              <pre className="text-[10px] font-mono text-on-surface-variant bg-surface-container-lowest p-3 rounded-lg mt-2 overflow-x-auto max-h-64">
                {detail.yaml_content}
              </pre>
            </details>
          </div>
        </div>
      )}
    </div>
  );
}
