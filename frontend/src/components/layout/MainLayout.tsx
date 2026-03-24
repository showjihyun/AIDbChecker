// Spec: FRONTEND_DESIGN.md Section 3 — Layout Structure
import { Link, useMatchRoute } from '@tanstack/react-router';
import { cn } from '@/lib/cn';
import { useMetricStore } from '@/stores/metricStore';
import { useWebSocket } from '@/hooks/useWebSocket';
import { Badge } from '@/components/common/Badge';

interface NavItem {
  to: string;
  icon: string;
  label: string;
}

const navItems: NavItem[] = [
  { to: '/', icon: 'dashboard', label: 'Dashboard' },
  { to: '/ash', icon: 'analytics', label: 'ASH Explorer' },
  { to: '/settings', icon: 'settings', label: 'Settings' },
];

function TopNav() {
  const wsConnected = useMetricStore((s) => s.wsConnected);

  return (
    <header
      className={cn(
        'fixed top-0 left-0 right-0 h-16 z-50',
        'bg-surface shadow-neural-glow',
        'flex items-center justify-between px-6'
      )}
    >
      <div className="flex items-center gap-3">
        <span className="text-xl font-display font-bold text-primary-container tracking-tighter">
          NeuralDB
        </span>
        <span className="text-xs text-on-surface-variant font-medium tracking-wider uppercase">
          monitoring
        </span>
      </div>

      <div className="flex items-center gap-4">
        <Badge
          variant={wsConnected ? 'healthy' : 'critical'}
          dot
        >
          {wsConnected ? 'Live' : 'Disconnected'}
        </Badge>

        <button
          className="text-on-surface-variant hover:text-on-surface transition-colors duration-200 ease-out"
          aria-label="Notifications"
        >
          <span className="material-symbols-outlined text-xl">
            notifications
          </span>
        </button>

        <button
          className="text-on-surface-variant hover:text-on-surface transition-colors duration-200 ease-out"
          aria-label="Account"
        >
          <span className="material-symbols-outlined text-xl">
            account_circle
          </span>
        </button>
      </div>
    </header>
  );
}

function SideNav() {
  const matchRoute = useMatchRoute();

  return (
    <nav
      className={cn(
        'fixed top-16 left-0 bottom-0 w-64 z-40',
        'bg-surface-container',
        'flex flex-col'
      )}
      aria-label="Main navigation"
    >
      <div className="flex-1 py-4 px-3 space-y-1">
        {navItems.map((item) => {
          const isActive = matchRoute({ to: item.to, fuzzy: item.to !== '/' });

          return (
            <Link
              key={item.to}
              to={item.to}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg',
                'text-sm font-medium transition-all duration-200 ease-out',
                isActive
                  ? 'bg-surface-container-high text-primary'
                  : 'text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface'
              )}
              aria-current={isActive ? 'page' : undefined}
            >
              <span className="material-symbols-outlined text-xl">
                {item.icon}
              </span>
              {item.label}
            </Link>
          );
        })}
      </div>

      <div className="p-3">
        <div className="bg-surface-container-high rounded-lg p-3">
          <p className="text-xs text-on-surface-variant font-medium mb-1">
            NeuralDB v0.1.0
          </p>
          <p className="text-xs text-outline">
            MVP Demo
          </p>
        </div>
      </div>
    </nav>
  );
}

interface MainLayoutProps {
  children: React.ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
  // Fix #3: WebSocket connects here so it is always mounted with the layout
  useWebSocket();

  return (
    <div className="min-h-screen bg-surface">
      <TopNav />
      <SideNav />
      <main className="ml-64 pt-16 min-h-screen">
        <div className="p-8">
          {children}
        </div>
      </main>
    </div>
  );
}
