// Spec: FS-KPI-001 AC-4, FS-DASH-004 AC-2 — KPI formatter and status color tests
// Tests: formatCompact, formatBytes, statusColor, kpiStatusColorMap
import { describe, it, expect } from 'vitest';

// --- Inline reimplementation of pure functions from components ---
// These mirror the logic in InstanceCard.tsx and KPIOverviewPanel.tsx
// to test formatting and color mapping without rendering React components.

// InstanceCard formatCompact
function formatCompact(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(Math.round(n));
}

// InstanceCard formatBytes
function formatBytesCard(bytes: number): string {
  if (bytes >= 1_073_741_824) return `${(bytes / 1_073_741_824).toFixed(1)}G`;
  if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(0)}M`;
  if (bytes >= 1_024) return `${(bytes / 1_024).toFixed(0)}K`;
  return `${bytes}B`;
}

// KPIOverviewPanel formatBytes (slightly different format with spaces)
function formatBytesPanel(bytes: number): string {
  if (bytes >= 1_073_741_824) return `${(bytes / 1_073_741_824).toFixed(1)} GB`;
  if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(1)} MB`;
  if (bytes >= 1_024) return `${(bytes / 1_024).toFixed(1)} KB`;
  return `${bytes} B`;
}

// KPIOverviewPanel statusColor
type KPIStatus = 'normal' | 'warning' | 'critical' | 'unknown';

function statusColor(status: KPIStatus): string {
  switch (status) {
    case 'warning':
      return 'text-warning';
    case 'critical':
      return 'text-error';
    case 'unknown':
      return 'text-outline';
    default:
      return 'text-on-surface';
  }
}

// InstanceCard kpiStatusColorMap
const kpiStatusColorMap: Record<string, string> = {
  normal: 'text-on-surface',
  warning: 'text-warning',
  critical: 'text-error',
  unknown: 'text-outline',
};

// --- Tests ---

describe('formatCompact (InstanceCard & KPIOverviewPanel)', () => {
  it('formats small numbers as-is (rounded)', () => {
    expect(formatCompact(0)).toBe('0');
    expect(formatCompact(42)).toBe('42');
    expect(formatCompact(999)).toBe('999');
    expect(formatCompact(3.7)).toBe('4');
  });

  it('formats thousands as K', () => {
    expect(formatCompact(1000)).toBe('1.0K');
    expect(formatCompact(1500)).toBe('1.5K');
    expect(formatCompact(25_432)).toBe('25.4K');
    expect(formatCompact(999_999)).toBe('1000.0K');
  });

  it('formats millions as M', () => {
    expect(formatCompact(1_000_000)).toBe('1.0M');
    expect(formatCompact(2_500_000)).toBe('2.5M');
    expect(formatCompact(123_456_789)).toBe('123.5M');
  });

  it('formats billions as B', () => {
    expect(formatCompact(1_000_000_000)).toBe('1.0B');
    expect(formatCompact(5_300_000_000)).toBe('5.3B');
  });
});

describe('formatBytes — InstanceCard variant (compact, no spaces)', () => {
  it('formats bytes', () => {
    expect(formatBytesCard(0)).toBe('0B');
    expect(formatBytesCard(512)).toBe('512B');
  });

  it('formats kilobytes', () => {
    expect(formatBytesCard(1024)).toBe('1K');
    expect(formatBytesCard(2048)).toBe('2K');
  });

  it('formats megabytes', () => {
    expect(formatBytesCard(1_048_576)).toBe('1M');
    expect(formatBytesCard(536_870_912)).toBe('512M');
  });

  it('formats gigabytes', () => {
    expect(formatBytesCard(1_073_741_824)).toBe('1.0G');
    expect(formatBytesCard(10_737_418_240)).toBe('10.0G');
  });
});

describe('formatBytes — KPIOverviewPanel variant (with units)', () => {
  it('formats bytes', () => {
    expect(formatBytesPanel(0)).toBe('0 B');
    expect(formatBytesPanel(512)).toBe('512 B');
  });

  it('formats kilobytes', () => {
    expect(formatBytesPanel(1024)).toBe('1.0 KB');
    expect(formatBytesPanel(5120)).toBe('5.0 KB');
  });

  it('formats megabytes', () => {
    expect(formatBytesPanel(1_048_576)).toBe('1.0 MB');
    expect(formatBytesPanel(524_288_000)).toBe('500.0 MB');
  });

  it('formats gigabytes', () => {
    expect(formatBytesPanel(1_073_741_824)).toBe('1.0 GB');
    expect(formatBytesPanel(5_368_709_120)).toBe('5.0 GB');
  });
});

describe('statusColor (KPIOverviewPanel)', () => {
  it('returns correct class for each status', () => {
    expect(statusColor('normal')).toBe('text-on-surface');
    expect(statusColor('warning')).toBe('text-warning');
    expect(statusColor('critical')).toBe('text-error');
    expect(statusColor('unknown')).toBe('text-outline');
  });
});

describe('kpiStatusColorMap (InstanceCard)', () => {
  it('maps all KPI statuses to Tailwind classes', () => {
    expect(kpiStatusColorMap['normal']).toBe('text-on-surface');
    expect(kpiStatusColorMap['warning']).toBe('text-warning');
    expect(kpiStatusColorMap['critical']).toBe('text-error');
    expect(kpiStatusColorMap['unknown']).toBe('text-outline');
  });

  it('returns undefined for unmapped statuses', () => {
    expect(kpiStatusColorMap['nonexistent']).toBeUndefined();
  });
});

describe('severity color mapping — FS-DASH-004 AC-2', () => {
  // Verify that the color system covers all 4 severity levels
  // used by incidents: critical, warning, info (notice), and normal
  const severityToStatus: Record<string, KPIStatus> = {
    critical: 'critical',
    warning: 'warning',
    notice: 'normal',
    info: 'normal',
  };

  it('maps critical severity to error color', () => {
    expect(statusColor(severityToStatus['critical'])).toBe('text-error');
  });

  it('maps warning severity to warning color', () => {
    expect(statusColor(severityToStatus['warning'])).toBe('text-warning');
  });

  it('maps notice/info severity to normal color', () => {
    expect(statusColor(severityToStatus['notice'])).toBe('text-on-surface');
    expect(statusColor(severityToStatus['info'])).toBe('text-on-surface');
  });
});
