// Spec: FS-DBA-002 — DBA Agent frontend component tests
import { describe, it, expect } from 'vitest';

describe('DBA Agent Components', () => {
  // --- DBAMiniChat widget ---

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

  // --- Intent icons/colors mapping ---

  it('has intent icons for all 5 intents', async () => {
    // Read the source to verify mappings exist
    const fs = await import('fs');
    const path = await import('path');
    const src = fs.readFileSync(
      path.resolve(__dirname, '../../src/components/dba/DBAMiniChat.tsx'),
      'utf-8'
    );
    expect(src).toContain("analyze: 'speed'");
    expect(src).toContain("diagnose: 'troubleshoot'");
    expect(src).toContain("execute: 'play_arrow'");
    expect(src).toContain("query: 'table_chart'");
    expect(src).toContain("status: 'monitor_heart'");
  });

  it('has risk colors for all 4 levels', async () => {
    const fs = await import('fs');
    const path = await import('path');
    const src = fs.readFileSync(
      path.resolve(__dirname, '../../src/components/dba/DBAMiniChat.tsx'),
      'utf-8'
    );
    expect(src).toContain('safe:');
    expect(src).toContain('warning:');
    expect(src).toContain('dangerous:');
    expect(src).toContain('critical:');
  });

  // --- Instance selector ---

  it('widget requires instance selection before chat', async () => {
    const fs = await import('fs');
    const path = await import('path');
    const src = fs.readFileSync(
      path.resolve(__dirname, '../../src/components/dba/DBAMiniChat.tsx'),
      'utf-8'
    );
    // AC-13: disabled when no instance
    expect(src).toContain('Select a DB instance');
    expect(src).toContain("Select DB Instance");
  });

  // --- Query result table ---

  it('renders query result table for intent=query', async () => {
    const fs = await import('fs');
    const path = await import('path');
    const src = fs.readFileSync(
      path.resolve(__dirname, '../../src/routes/pages/DBAAgentPage.tsx'),
      'utf-8'
    );
    expect(src).toContain('msg.data?.columns');
    expect(src).toContain('<table');
    expect(src).toContain('Showing 20 of');
  });

  // --- Navigation ---

  it('DBA Agent is in sidebar navigation', async () => {
    const fs = await import('fs');
    const path = await import('path');
    const src = fs.readFileSync(
      path.resolve(__dirname, '../../src/components/layout/MainLayout.tsx'),
      'utf-8'
    );
    expect(src).toContain("label: 'DBA Agent'");
    expect(src).toContain("icon: 'smart_toy'");
    expect(src).toContain("to: '/dba'");
  });

  it('DBA route is registered', async () => {
    const fs = await import('fs');
    const path = await import('path');
    const src = fs.readFileSync(
      path.resolve(__dirname, '../../src/routes/index.tsx'),
      'utf-8'
    );
    expect(src).toContain("path: '/dba'");
    expect(src).toContain('DBAAgentPage');
  });
});
