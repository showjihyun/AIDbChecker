// Spec: Notification dropdown panel — shows advisory history with actions
import { useRef, useEffect, useState, useCallback } from 'react';
import { cn } from '@/lib/cn';
import {
  useNotificationStore,
  type Notification,
} from '@/stores/notificationStore';

const levelConfig = {
  info: {
    icon: 'info',
    iconColor: 'text-primary',
    dotColor: 'bg-primary',
  },
  warning: {
    icon: 'warning',
    iconColor: 'text-warning',
    dotColor: 'bg-warning',
  },
  error: {
    icon: 'error',
    iconColor: 'text-error',
    dotColor: 'bg-error',
  },
};

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for non-secure contexts
      const textarea = document.createElement('textarea');
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [text]);

  return (
    <button
      onClick={handleCopy}
      className={cn(
        'px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors',
        copied
          ? 'bg-tertiary/20 text-tertiary'
          : 'bg-surface-container-highest text-on-surface-variant hover:text-on-surface'
      )}
      aria-label={copied ? 'Copied' : 'Copy to clipboard'}
    >
      <span className="material-symbols-outlined text-xs align-middle mr-0.5">
        {copied ? 'check' : 'content_copy'}
      </span>
      {copied ? 'Copied' : 'Copy'}
    </button>
  );
}

function formatTimestamp(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);

  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

function NotificationItem({ notification }: { notification: Notification }) {
  const config = levelConfig[notification.level];

  return (
    <div
      className={cn(
        'px-3 py-2.5 transition-colors',
        !notification.read
          ? 'bg-surface-container-high/50'
          : 'bg-transparent'
      )}
    >
      <div className="flex items-start gap-2.5">
        <span
          className={cn(
            'material-symbols-outlined text-base mt-0.5 shrink-0',
            config.iconColor
          )}
        >
          {config.icon}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <p className="text-xs font-semibold text-on-surface truncate">
              {notification.title}
            </p>
            {!notification.read && (
              <span
                className={cn('w-1.5 h-1.5 rounded-full shrink-0', config.dotColor)}
                aria-label="Unread"
              />
            )}
          </div>
          <p className="text-[11px] text-on-surface-variant leading-relaxed">
            {notification.message}
          </p>
          {notification.instanceName && (
            <p className="text-[10px] text-outline mt-0.5">
              {notification.instanceName}
            </p>
          )}
          {notification.action && (
            <div className="mt-1.5 flex items-center gap-2">
              <code className="flex-1 min-w-0 text-[10px] font-mono bg-surface-container-lowest rounded px-2 py-1 text-primary truncate">
                {notification.action}
              </code>
              <CopyButton text={notification.action} />
            </div>
          )}
          <p className="text-[10px] text-outline mt-1">
            {formatTimestamp(notification.timestamp)}
          </p>
        </div>
      </div>
    </div>
  );
}

export function NotificationPanel() {
  const panelOpen = useNotificationStore((s) => s.panelOpen);
  const notifications = useNotificationStore((s) => s.notifications);
  const closePanel = useNotificationStore((s) => s.closePanel);
  const markAllRead = useNotificationStore((s) => s.markAllRead);
  const clearAll = useNotificationStore((s) => s.clearAll);
  const panelRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!panelOpen) return;
    function handleClick(e: MouseEvent) {
      if (
        panelRef.current &&
        !panelRef.current.contains(e.target as Node)
      ) {
        closePanel();
      }
    }
    // Use setTimeout to avoid closing immediately from the same click
    const timer = setTimeout(() => {
      document.addEventListener('mousedown', handleClick);
    }, 0);
    return () => {
      clearTimeout(timer);
      document.removeEventListener('mousedown', handleClick);
    };
  }, [panelOpen, closePanel]);

  if (!panelOpen) return null;

  return (
    <div
      ref={panelRef}
      className={cn(
        'absolute right-0 top-full mt-2 w-80 sm:w-96',
        'bg-surface-container rounded-lg shadow-neural-glow',
        'border border-outline-variant/30',
        'z-50 overflow-hidden',
        'animate-in fade-in slide-in-from-top-2'
      )}
      role="dialog"
      aria-label="Notifications"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-outline-variant/20">
        <h3 className="text-xs font-semibold text-on-surface">
          Notifications
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={markAllRead}
            className="text-[10px] text-primary hover:text-primary-container transition-colors font-medium"
          >
            Mark all read
          </button>
          <button
            onClick={clearAll}
            className="text-[10px] text-on-surface-variant hover:text-error transition-colors font-medium"
          >
            Clear all
          </button>
        </div>
      </div>

      {/* Notification list */}
      <div className="max-h-[400px] overflow-y-auto divide-y divide-outline-variant/10">
        {notifications.length === 0 ? (
          <div className="px-3 py-8 text-center">
            <span className="material-symbols-outlined text-2xl text-outline mb-1 block">
              notifications_none
            </span>
            <p className="text-xs text-outline">No notifications</p>
          </div>
        ) : (
          notifications.map((n) => (
            <NotificationItem key={n.id} notification={n} />
          ))
        )}
      </div>
    </div>
  );
}
