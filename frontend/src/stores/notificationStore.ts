// Spec: Toast notification system — Zustand store for notifications
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

interface NotificationState {
  notifications: Notification[];
  unreadCount: number;
  panelOpen: boolean;
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

  addNotification: (n) => {
    const state = get();

    // Deduplicate: skip if same title+instanceName already exists and unread
    const isDuplicate = state.notifications.some(
      (existing) =>
        !existing.read &&
        existing.title === n.title &&
        existing.instanceName === n.instanceName
    );
    if (isDuplicate) return false;

    const notification: Notification = {
      ...n,
      id: generateId(),
      timestamp: new Date(),
      read: false,
    };

    set((s) => {
      const updated = [notification, ...s.notifications].slice(
        0,
        MAX_NOTIFICATIONS
      );
      return {
        notifications: updated,
        unreadCount: updated.filter((x) => !x.read).length,
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
    }),
}));
