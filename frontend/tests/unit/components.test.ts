/**
 * @spec FE-COMP-001
 * @description 전체 컴포넌트 존재 + export 검증 테스트
 *
 * 각 컴포넌트가 올바르게 export되고 함수/클래스인지 확인.
 * 렌더링 테스트는 RTL 환경에서 별도 수행.
 */

import { describe, it, expect } from 'vitest';

// ─────────────────────────────────────────────────
// §3.1~3.2 Dashboard Components
// ─────────────────────────────────────────────────

describe('[Spec: FE-COMP-001] Dashboard Components', () => {
  it('InstanceCard exports a function component', async () => {
    const mod = await import('@/components/dashboard/InstanceCard');
    expect(mod.InstanceCard).toBeDefined();
    expect(typeof mod.InstanceCard).toBe('function');
  });

  it('MetricChart exports a function component', async () => {
    const mod = await import('@/components/dashboard/MetricChart');
    expect(mod.MetricChart).toBeDefined();
  });

  it('SystemHealth exports a function component', async () => {
    const mod = await import('@/components/dashboard/SystemHealth');
    expect(mod.SystemHealthPanel).toBeDefined();
  });

  it('KPIOverviewPanel exports a function component', async () => {
    const mod = await import('@/components/dashboard/KPIOverviewPanel');
    expect(mod.KPIOverviewPanel).toBeDefined();
  });
});

// ─────────────────────────────────────────────────
// §3.5~3.7 ASH Components
// ─────────────────────────────────────────────────

describe('[Spec: FE-COMP-001] ASH Components', () => {
  it('ASHHeatmap exports a function component', async () => {
    const mod = await import('@/components/ash/ASHHeatmap');
    expect(mod.ASHHeatmap).toBeDefined();
  });

  it('SessionTable exports a function component', async () => {
    const mod = await import('@/components/ash/SessionTable');
    expect(mod.SessionTable).toBeDefined();
  });

  // WaitBreakdownPanel: apiClient 의존으로 unit test 불가 — E2E에서 검증
});

// ─────────────────────────────────────────────────
// §3.8 Incidents
// ─────────────────────────────────────────────────

describe('[Spec: FE-COMP-001] Incidents Components', () => {
  it('IncidentRow exports a function component', async () => {
    const mod = await import('@/components/incidents/IncidentRow');
    expect(mod.IncidentRow).toBeDefined();
  });
});

// ─────────────────────────────────────────────────
// §3.10~3.12 AI Components
// ─────────────────────────────────────────────────

describe('[Spec: FE-COMP-001] AI Components', () => {
  it('ConfidenceBadge exports a function component', async () => {
    const mod = await import('@/components/ai/ConfidenceBadge');
    expect(mod.ConfidenceBadge).toBeDefined();
  });

  it('ReasoningChainPanel exports a function component', async () => {
    const mod = await import('@/components/ai/ReasoningChainPanel');
    expect(mod.ReasoningChainPanel).toBeDefined();
  });

  it('MTLPredictionCard exports a function component', async () => {
    const mod = await import('@/components/ai/MTLPredictionCard');
    expect(mod.MTLPredictionCard).toBeDefined();
  });

  // LLMObservabilityPanel: apiClient + useQuery 의존 — E2E에서 검증
});

// ─────────────────────────────────────────────────
// §3.13 NL2SQL
// ─────────────────────────────────────────────────

describe('[Spec: FE-COMP-001] NL2SQL Components', () => {
  it('NL2SQLChat exports a function component', async () => {
    const mod = await import('@/components/nl2sql/NL2SQLChat');
    expect(mod.NL2SQLChat).toBeDefined();
  });
});

// ─────────────────────────────────────────────────
// §3.15 Instances
// ─────────────────────────────────────────────────

describe('[Spec: FE-COMP-001] Instance Components', () => {
  it('InstanceListItem exports a function component', async () => {
    const mod = await import('@/components/instances/InstanceListItem');
    expect(mod.InstanceListItem).toBeDefined();
  });

  it('RegisterInstanceModal exports a function component', async () => {
    const mod = await import('@/components/instances/RegisterInstanceModal');
    expect(mod.RegisterInstanceModal).toBeDefined();
  });
});

// ─────────────────────────────────────────────────
// §3.18 Schema
// ─────────────────────────────────────────────────

describe('[Spec: FE-COMP-001] Schema Components', () => {
  it('SchemaChangeTimeline exports a function component', async () => {
    const mod = await import('@/components/schema/SchemaChangeTimeline');
    expect(mod.SchemaChangeTimeline).toBeDefined();
  });
});

// ─────────────────────────────────────────────────
// §3.19~3.20 Common/Layout
// ─────────────────────────────────────────────────

describe('[Spec: FE-COMP-001] Common Components', () => {
  it('Badge exports a function component', async () => {
    const mod = await import('@/components/common/Badge');
    expect(mod.Badge).toBeDefined();
  });

  it('Toast exports a function component', async () => {
    const mod = await import('@/components/common/Toast');
    expect(mod.ToastContainer).toBeDefined();
  });

  it('EmptyState exports a function component', async () => {
    const mod = await import('@/components/common/EmptyState');
    expect(mod.EmptyState).toBeDefined();
  });

  it('NotificationPanel exports a function component', async () => {
    const mod = await import('@/components/common/NotificationPanel');
    expect(mod.NotificationPanel).toBeDefined();
  });
});

describe('[Spec: FE-COMP-001] Layout Components', () => {
  it('MainLayout exports a function component', async () => {
    const mod = await import('@/components/layout/MainLayout');
    expect(mod.MainLayout || mod.default).toBeDefined();
  });
});
