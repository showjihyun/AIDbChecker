// Spec: Toast notification popup — auto-dismiss, stacked, slide-in animation
import { useState, useEffect, useCallback } from 'react';
import { create } from 'zustand';
import { cn } from '@/lib/cn';

export interface ToastItem {
  id: string;
  level: 'info' | 'warning' | 'error';
  title: string;
  message: string;
}

interface ToastState {
  toasts: ToastItem[];
  addToast: (t: Omit<ToastItem, 'id'>) => void;
  removeToast: (id: string) => void;
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],

  addToast: (t) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    set((s) => ({
      toasts: [...s.toasts, { ...t, id }],
    }));
  },

  removeToast: (id) =>
    set((s) => ({
      toasts: s.toasts.filter((t) => t.id !== id),
    })),
}));

const levelConfig = {
  info: {
    icon: 'info',
    bg: 'bg-primary/15',
    border: 'border-primary/30',
    iconColor: 'text-primary',
    titleColor: 'text-primary',
  },
  warning: {
    icon: 'warning',
    bg: 'bg-warning/15',
    border: 'border-warning/30',
    iconColor: 'text-warning',
    titleColor: 'text-warning',
  },
  error: {
    icon: 'error',
    bg: 'bg-error/15',
    border: 'border-error/30',
    iconColor: 'text-error',
    titleColor: 'text-error',
  },
};

function ToastEntry({ toast }: { toast: ToastItem }) {
  const removeToast = useToastStore((s) => s.removeToast);
  const [visible, setVisible] = useState(false);
  const [exiting, setExiting] = useState(false);

  const dismiss = useCallback(() => {
    setExiting(true);
    setTimeout(() => removeToast(toast.id), 300);
  }, [removeToast, toast.id]);

  useEffect(() => {
    // Slide in
    const showTimer = requestAnimationFrame(() => setVisible(true));

    // Auto-dismiss: 8s for info, 12s for warning/error
    const duration = toast.level === 'info' ? 8000 : 12000;
    const autoTimer = setTimeout(dismiss, duration);

    return () => {
      cancelAnimationFrame(showTimer);
      clearTimeout(autoTimer);
    };
  }, [dismiss, toast.level]);

  const config = levelConfig[toast.level];

  return (
    <div
      role="alert"
      className={cn(
        'w-80 rounded-lg border p-3 shadow-neural-glow',
        'transition-all duration-300 ease-out',
        config.bg,
        config.border,
        visible && !exiting
          ? 'translate-x-0 opacity-100'
          : 'translate-x-full opacity-0'
      )}
    >
      <div className="flex items-start gap-2.5">
        <span
          className={cn('material-symbols-outlined text-lg mt-0.5 shrink-0', config.iconColor)}
        >
          {config.icon}
        </span>
        <div className="flex-1 min-w-0">
          <p className={cn('text-xs font-semibold', config.titleColor)}>
            {toast.title}
          </p>
          <p className="text-xs text-on-surface-variant mt-0.5 leading-relaxed">
            {toast.message}
          </p>
        </div>
        <button
          onClick={dismiss}
          className="text-on-surface-variant hover:text-on-surface transition-colors shrink-0"
          aria-label="Close notification"
        >
          <span className="material-symbols-outlined text-base">close</span>
        </button>
      </div>
    </div>
  );
}

export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);

  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed top-20 right-4 z-[60] flex flex-col gap-2"
      aria-live="polite"
      aria-label="Notifications"
    >
      {toasts.map((toast) => (
        <ToastEntry key={toast.id} toast={toast} />
      ))}
    </div>
  );
}
