// Spec: Toast notification system — Zustand store for notifications
import { create } from 'zustand';

const MAX_NOTIFICATIONS = 50;
/** How long to suppress duplicate notifications after read/clear (ms) */
const DEDUP_WINDOW_MS = 5 * 60 * 1000; // 5 minutes

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

/** Key used for deduplication */
function dedupKey(title: string, instanceName?: string): string {
  return `${title}::${instanceName ?? ''}`;
}

interface NotificationState {
  notifications: Notification[];
  unreadCount: number;
  panelOpen: boolean;
  /** Tracks recently seen notification keys with timestamp to prevent re-adding */
  _seenKeys: Map<string, number>;
  addNotification: (
    n: Omit<Notification, 'id' | 'timestamp' | 'read'>
  ) => boolean;
  markAllRead: () => void;
  togglePanel: () => void;
  closePanel: () => void;
  clearAll: () => void;
}

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export const useNotificationStore = create<NotificationState>((set, get) => ({
  notifications: [],
  unreadCount: 0,
  panelOpen: false,
  _seenKeys: new Map(),

  addNotification: (n) => {
    const state = get();
    const key = dedupKey(n.title, n.instanceName);
    const now = Date.now();

    // Check _seenKeys for recent duplicates (survives clearAll)
    const lastSeen = state._seenKeys.get(key);
    if (lastSeen && now - lastSeen < DEDUP_WINDOW_MS) {
      return false;
    }

    // Also check existing notifications in array
    const isDuplicate = state.notifications.some(
      (existing) =>
        existing.title === n.title &&
        existing.instanceName === n.instanceName &&
        now - existing.timestamp.getTime() < DEDUP_WINDOW_MS
    );
    if (isDuplicate) return false;

    const notification: Notification = {
      ...n,
      id: generateId(),
      timestamp: new Date(),
      read: false,
    };

    // Record in _seenKeys
    const newSeenKeys = new Map(state._seenKeys);
    newSeenKeys.set(key, now);
    // Prune old entries (> DEDUP_WINDOW_MS)
    for (const [k, ts] of newSeenKeys) {
      if (now - ts > DEDUP_WINDOW_MS) newSeenKeys.delete(k);
    }

    set((s) => {
      const updated = [notification, ...s.notifications].slice(
        0,
        MAX_NOTIFICATIONS
      );
      return {
        notifications: updated,
        unreadCount: updated.filter((x) => !x.read).length,
        _seenKeys: newSeenKeys,
      };
    });
    return true;
  },

  markAllRead: () =>
    set((s) => ({
      notifications: s.notifications.map((n) => ({ ...n, read: true })),
      unreadCount: 0,
    })),

  togglePanel: () => set((s) => ({ panelOpen: !s.panelOpen })),

  closePanel: () => set({ panelOpen: false }),

  clearAll: () =>
    set({
      notifications: [],
      unreadCount: 0,
      // _seenKeys preserved intentionally — prevents re-adding cleared notifications
    }),
}));
