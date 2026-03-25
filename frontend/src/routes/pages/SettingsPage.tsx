// Spec: MVP-ADMIN — Settings page (instance registration, alerts, users, system config)
import { Link } from '@tanstack/react-router';
import { cn } from '@/lib/cn';

interface SettingsSectionProps {
  title: string;
  icon: string;
  description: string;
  items: { label: string; detail: string; to?: string }[];
  actionLabel?: string;
  actionTo?: string;
}

function SettingsSection({
  title,
  icon,
  description,
  items,
  actionLabel,
  actionTo,
}: SettingsSectionProps) {
  return (
    <div className="bg-surface-container rounded-xl p-6 hover:bg-surface-container-high transition-colors duration-200 ease-out">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-10 h-10 rounded-lg bg-primary-container/10 flex items-center justify-center">
          <span className="material-symbols-outlined text-primary-container">
            {icon}
          </span>
        </div>
        <div>
          <h3 className="text-sm font-semibold text-on-surface">{title}</h3>
          <p className="text-xs text-on-surface-variant">{description}</p>
        </div>
      </div>

      <div className="space-y-2 mt-4">
        {items.map((item) => (
          <div
            key={item.label}
            className="flex items-center justify-between py-2 px-3 rounded-lg bg-surface/50"
          >
            <div>
              <p className="text-xs font-medium text-on-surface">
                {item.label}
              </p>
              <p className="text-xs text-on-surface-variant">{item.detail}</p>
            </div>
            {item.to && (
              <Link
                to={item.to}
                className="text-xs text-primary-container hover:underline"
              >
                View
              </Link>
            )}
          </div>
        ))}
      </div>

      {actionLabel && actionTo && (
        <div className="mt-4 pt-4">
          <Link
            to={actionTo}
            className={cn(
              'inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium',
              'bg-primary-container/10 text-primary-container',
              'hover:bg-primary-container/20 transition-colors duration-200 ease-out'
            )}
          >
            <span className="material-symbols-outlined text-base">
              arrow_forward
            </span>
            {actionLabel}
          </Link>
        </div>
      )}
    </div>
  );
}

export function SettingsPage() {
  return (
    <div className="space-y-module-gap">
      <div>
        <h1 className="text-2xl font-display font-bold text-on-surface tracking-tight">
          Settings
        </h1>
        <p className="text-xs text-on-surface-variant mt-1">
          Instance management, alert channels, and user administration
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Instance Management */}
        <SettingsSection
          title="Instance Management"
          icon="dns"
          description="Register and manage monitored PostgreSQL instances."
          items={[
            {
              label: 'Registered Instances',
              detail: 'View, add, or modify database connections',
              to: '/',
            },
            {
              label: 'Connection Testing',
              detail: 'Test connectivity to target databases',
            },
            {
              label: 'Schema Change Detection',
              detail: 'Auto-detect DDL changes every 60 seconds',
            },
          ]}
          actionLabel="Manage Instances"
          actionTo="/"
        />

        {/* Alert Channels */}
        <SettingsSection
          title="Alert Channels"
          icon="notifications"
          description="Configure Slack, Webhook, and other notification channels."
          items={[
            {
              label: 'Slack Integration',
              detail: 'Send CRITICAL/WARNING/NOTICE/INFO alerts to Slack',
            },
            {
              label: 'Webhook Endpoints',
              detail: 'Custom webhook URLs for external integrations',
            },
            {
              label: 'Cooldown Policy',
              detail: '30-minute cooldown between duplicate alerts',
            },
          ]}
        />

        {/* User Management */}
        <SettingsSection
          title="User Management"
          icon="group"
          description="Manage user accounts and RBAC role assignments."
          items={[
            {
              label: 'RBAC Roles',
              detail: 'Super Admin, DB Admin, Operator, Viewer, API User',
            },
            {
              label: 'Local Authentication',
              detail: 'Email + Password with bcrypt hashing',
            },
            {
              label: 'Audit Logging',
              detail: 'All state changes tracked with WHO/WHAT/WHEN',
            },
          ]}
        />

        {/* System Configuration */}
        <SettingsSection
          title="System Configuration"
          icon="tune"
          description="Collection intervals, AI model settings, and system behavior."
          items={[
            {
              label: 'Collection Intervals',
              detail: 'Hot: 1s, Warm: 10s, Cold: 60s, Schema: 60s',
            },
            {
              label: 'AI Mode',
              detail: 'Online (Cloud LLM) / Offline (Ollama) switching',
            },
            {
              label: 'Baseline Training',
              detail: 'STL + Isolation Forest, retrained every 6 hours',
            },
            {
              label: 'System Health',
              detail: 'DB / Valkey / Celery status monitoring',
            },
          ]}
        />
      </div>
    </div>
  );
}
