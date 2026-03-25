// Spec: FRONTEND_DESIGN.md Section 3 — Layout Structure
import { useState, useRef, useEffect } from 'react';
import { Link, useMatchRoute, useNavigate } from '@tanstack/react-router';
import { cn } from '@/lib/cn';
import { useMetricStore } from '@/stores/metricStore';
import { useAuthStore } from '@/stores/authStore';
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
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu on outside click
  useEffect(() => {
    if (!menuOpen) return;
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [menuOpen]);

  const handleLogout = () => {
    setMenuOpen(false);
    logout();
    navigate({ to: '/login' });
  };

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

        {/* Account button with dropdown */}
        <div className="relative" ref={menuRef}>
          <button
            className={cn(
              'flex items-center gap-2 px-2 py-1 rounded-lg',
              'text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high',
              'transition-all duration-200 ease-out'
            )}
            aria-label="Account menu"
            aria-expanded={menuOpen}
            aria-haspopup="true"
            onClick={() => setMenuOpen((prev) => !prev)}
          >
            <span className="material-symbols-outlined text-xl">
              account_circle
            </span>
            {user && (
              <span className="hidden md:inline text-xs font-medium max-w-[120px] truncate">
                {user.name}
              </span>
            )}
          </button>

          {menuOpen && (
            <div
              className={cn(
                'absolute right-0 top-full mt-2 w-56',
                'bg-surface-container-high rounded-lg shadow-neural-glow',
                'py-2 z-50'
              )}
              role="menu"
            >
              {user && (
                <div className="px-4 py-2 mb-1">
                  <p className="text-sm font-medium text-on-surface truncate">
                    {user.name}
                  </p>
                  <p className="text-xs text-on-surface-variant truncate">
                    {user.email}
                  </p>
                  <p className="text-[10px] font-semibold tracking-wider uppercase text-primary mt-1">
                    {user.role.replace('_', ' ')}
                  </p>
                </div>
              )}
              <div className="h-px bg-outline-variant mx-3 my-1" />
              <button
                className={cn(
                  'w-full text-left px-4 py-2 text-sm',
                  'text-on-surface-variant hover:text-error hover:bg-surface-container-highest',
                  'transition-colors duration-200 ease-out flex items-center gap-2'
                )}
                role="menuitem"
                onClick={handleLogout}
              >
                <span className="material-symbols-outlined text-lg">logout</span>
                Sign Out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

function SideNav() {
  const matchRoute = useMatchRoute();

  return (
    <nav
      className={cn(
        'fixed top-16 left-0 bottom-0 z-40',
        'w-16 md:w-64',
        'bg-surface-container',
        'flex flex-col',
        'transition-[width] duration-200 ease-out'
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
              <span className="hidden md:inline">{item.label}</span>
            </Link>
          );
        })}
      </div>

      <div className="p-3 hidden md:block">
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
      <main className="ml-16 md:ml-64 pt-16 min-h-screen">
        <div className="p-4 md:p-8">
          {children}
        </div>
      </main>
    </div>
  );
}
