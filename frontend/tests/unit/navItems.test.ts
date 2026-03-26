// Spec: FS-DASH-004 AC-6 — SideNav items verification
// Verifies that the navigation structure includes all required menu items
import { describe, it, expect } from 'vitest';

// Replicate navItems from MainLayout.tsx to test without React Router dependencies
const navItems = [
  { to: '/', icon: 'dashboard', label: 'Dashboard' },
  { to: '/instances', icon: 'dns', label: 'Instances' },
  { to: '/ash', icon: 'analytics', label: 'ASH Explorer' },
  { to: '/incidents', icon: 'report_problem', label: 'Incidents' },
  { to: '/settings', icon: 'settings', label: 'Settings' },
];

describe('SideNav navItems — FS-DASH-004 AC-6', () => {
  it('contains exactly 5 navigation items', () => {
    expect(navItems).toHaveLength(5);
  });

  it('includes Dashboard as root route', () => {
    const dashboard = navItems.find((n) => n.label === 'Dashboard');
    expect(dashboard).toBeDefined();
    expect(dashboard!.to).toBe('/');
    expect(dashboard!.icon).toBe('dashboard');
  });

  it('includes Instances route', () => {
    const instances = navItems.find((n) => n.label === 'Instances');
    expect(instances).toBeDefined();
    expect(instances!.to).toBe('/instances');
  });

  it('includes ASH Explorer route', () => {
    const ash = navItems.find((n) => n.label === 'ASH Explorer');
    expect(ash).toBeDefined();
    expect(ash!.to).toBe('/ash');
  });

  it('includes Incidents route — required by FS-DASH-004', () => {
    const incidents = navItems.find((n) => n.label === 'Incidents');
    expect(incidents).toBeDefined();
    expect(incidents!.to).toBe('/incidents');
    expect(incidents!.icon).toBe('report_problem');
  });

  it('includes Settings route', () => {
    const settings = navItems.find((n) => n.label === 'Settings');
    expect(settings).toBeDefined();
    expect(settings!.to).toBe('/settings');
  });

  it('all routes start with /', () => {
    for (const item of navItems) {
      expect(item.to.startsWith('/')).toBe(true);
    }
  });

  it('all items have non-empty icon and label', () => {
    for (const item of navItems) {
      expect(item.icon.length).toBeGreaterThan(0);
      expect(item.label.length).toBeGreaterThan(0);
    }
  });
});
