// Spec: FS-KPI-001 AC-12 — Notification store with persistent suppress
import { create } from 'zustand';

const MAX_NOTIFICATIONS = 50;

export interface Notification {
  id: string;
  level: 'info' | 'warning' | 'error';
  title: string;
  message: string;
  action?: string;
  timestamp: Date;
  read: boolean;
  instanceName?: string;
}

function dedupKey(title: string, instanceName?: string): string {
  return `${title}::${instanceName ?? ''}`;
}

interface NotificationState {
  notifications: Notification[];
  unreadCount: number;
  panelOpen: boolean;
  /** Permanently suppressed keys — survives clearAll, markAllRead, and page refresh */
  _suppressedKeys: Set<string>;
  /** Temporarily seen keys (timestamp-based, 5 min) */
  _seenKeys: Map<string, number>;
  addNotification: (n: Omit<Notification, 'id' | 'timestamp' | 'read'>) => boolean;
  markAllRead: () => void;
  togglePanel: () => void;
  closePanel: () => void;
  clearAll: () => void;
}

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/**
 * Load suppressed keys from sessionStorage.
 * sessionStorage persists across page refreshes but clears on tab close.
 */
function loadSuppressed(): Set<string> {
  try {
    const raw = sessionStorage.getItem('neuraldb:suppressed-notifications');
    if (raw) return new Set(JSON.parse(raw) as string[]);
  } catch { /* ignore */ }
  return new Set();
}

function saveSuppressed(keys: Set<string>): void {
  try {
    sessionStorage.setItem(
      'neuraldb:suppressed-notifications',
      JSON.stringify([...keys]),
    );
  } catch { /* ignore */ }
}

export const useNotificationStore = create<NotificationState>((set, get) => ({
  notifications: [],
  unreadCount: 0,
  panelOpen: false,
  _suppressedKeys: loadSuppressed(),
  _seenKeys: new Map(),

  addNotification: (n) => {
    const state = get();
    const key = dedupKey(n.title, n.instanceName);

    // 1. Permanently suppressed (clearAll / markAllRead에서 등록)
    if (state._suppressedKeys.has(key)) {
      return false;
    }

    // 2. Recently seen (5 min window)
    const now = Date.now();
    const lastSeen = state._seenKeys.get(key);
    if (lastSeen && now - lastSeen < 5 * 60 * 1000) {
      return false;
    }

    // 3. Already exists in current list
    const isDuplicate = state.notifications.some(
      (existing) =>
        existing.title === n.title &&
        existing.instanceName === n.instanceName,
    );
    if (isDuplicate) return false;

    const notification: Notification = {
      ...n,
      id: generateId(),
      timestamp: new Date(),
      read: false,
    };

    const newSeenKeys = new Map(state._seenKeys);
    newSeenKeys.set(key, now);
    // Prune old entries
    for (const [k, ts] of newSeenKeys) {
      if (now - ts > 5 * 60 * 1000) newSeenKeys.delete(k);
    }

    set((s) => {
      const updated = [notification, ...s.notifications].slice(0, MAX_NOTIFICATIONS);
      return {
        notifications: updated,
        unreadCount: updated.filter((x) => !x.read).length,
        _seenKeys: newSeenKeys,
      };
    });
    return true;
  },

  markAllRead: () => {
    const state = get();
    // Suppress all current notification keys so they don't come back
    const newSuppressed = new Set(state._suppressedKeys);
    for (const n of state.notifications) {
      newSuppressed.add(dedupKey(n.title, n.instanceName));
    }
    saveSuppressed(newSuppressed);

    set({
      notifications: [],
      unreadCount: 0,
      _suppressedKeys: newSuppressed,
    });
  },

  togglePanel: () => set((s) => ({ panelOpen: !s.panelOpen })),
  closePanel: () => set({ panelOpen: false }),

  clearAll: () => {
    const state = get();
    // Suppress all current notification keys permanently
    const newSuppressed = new Set(state._suppressedKeys);
    for (const n of state.notifications) {
      newSuppressed.add(dedupKey(n.title, n.instanceName));
    }
    saveSuppressed(newSuppressed);

    set({
      notifications: [],
      unreadCount: 0,
      _suppressedKeys: newSuppressed,
    });
  },
}));
