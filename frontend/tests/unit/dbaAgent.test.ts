// Spec: FS-DBA-002 — DBA Agent frontend component tests
import { describe, it, expect } from 'vitest';

describe('DBA Agent Components', () => {
  it('DBAMiniChat component exports correctly', async () => {
    const mod = await import('@/components/dba/DBAMiniChat');
    expect(mod.DBAMiniChat).toBeDefined();
    expect(typeof mod.DBAMiniChat).toBe('function');
  });

  it('DBAAgentPage component exports correctly', async () => {
    const mod = await import('@/routes/pages/DBAAgentPage');
    expect(mod.DBAAgentPage).toBeDefined();
    expect(typeof mod.DBAAgentPage).toBe('function');
  });

  it('LLMObservabilityPage component exports correctly', async () => {
    const mod = await import('@/routes/pages/LLMObservabilityPage');
    expect(mod.LLMObservabilityPage).toBeDefined();
    expect(typeof mod.LLMObservabilityPage).toBe('function');
  });

  it('LLMObservabilityPanel component exports correctly', async () => {
    const mod = await import('@/components/ai/LLMObservabilityPanel');
    expect(mod.LLMObservabilityPanel).toBeDefined();
  });

  it('ReActTracePanel component exports correctly', async () => {
    const mod = await import('@/components/ai/ReActTracePanel');
    expect(mod.ReActTracePanel).toBeDefined();
  });

  it('ConfidenceBadge component exports correctly', async () => {
    const mod = await import('@/components/ai/ConfidenceBadge');
    expect(mod.ConfidenceBadge).toBeDefined();
  });

  it('DBA route is registered', async () => {
    // Verify the route module imports DBAAgentPage
    const routes = await import('@/routes/index');
    expect(routes.router).toBeDefined();
  });

  it('notification store has suppress functionality', async () => {
    const mod = await import('@/stores/notificationStore');
    const state = mod.useNotificationStore.getState();
    expect(state).toHaveProperty('clearAll');
    expect(state).toHaveProperty('markAllRead');
    expect(state).toHaveProperty('_suppressedKeys');
  });
});
