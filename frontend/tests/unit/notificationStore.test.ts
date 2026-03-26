// Spec: FS-KPI-001 AC-9, AC-10, AC-11 — Notification store tests
// Tests: deduplication, markAllRead, clearAll, max 50 FIFO, unreadCount
import { describe, it, expect, beforeEach } from 'vitest';
import { useNotificationStore } from '@/stores/notificationStore';

function resetStore() {
  useNotificationStore.setState({
    notifications: [],
    unreadCount: 0,
    panelOpen: false,
  });
}

describe('notificationStore', () => {
  beforeEach(() => {
    resetStore();
  });

  // --- addNotification ---

  it('adds a notification and increments unreadCount', () => {
    const store = useNotificationStore.getState();
    const added = store.addNotification({
      level: 'warning',
      title: 'High CPU',
      message: 'CPU usage exceeded 90%',
      instanceName: 'pg-prod-01',
    });

    expect(added).toBe(true);

    const state = useNotificationStore.getState();
    expect(state.notifications).toHaveLength(1);
    expect(state.unreadCount).toBe(1);
    expect(state.notifications[0].title).toBe('High CPU');
    expect(state.notifications[0].read).toBe(false);
    expect(state.notifications[0].level).toBe('warning');
    expect(state.notifications[0].instanceName).toBe('pg-prod-01');
  });

  it('deduplicates by title+instanceName when unread exists', () => {
    const store = useNotificationStore.getState();

    store.addNotification({
      level: 'error',
      title: 'Connection Limit',
      message: 'Connections exceeded 200',
      instanceName: 'pg-prod-01',
    });

    // Same title + instanceName should be rejected
    const duplicate = useNotificationStore.getState().addNotification({
      level: 'error',
      title: 'Connection Limit',
      message: 'Different message text',
      instanceName: 'pg-prod-01',
    });

    expect(duplicate).toBe(false);
    expect(useNotificationStore.getState().notifications).toHaveLength(1);
  });

  it('allows same title for different instanceName', () => {
    const store = useNotificationStore.getState();

    store.addNotification({
      level: 'warning',
      title: 'High CPU',
      message: 'CPU 90%',
      instanceName: 'pg-prod-01',
    });

    const added = useNotificationStore.getState().addNotification({
      level: 'warning',
      title: 'High CPU',
      message: 'CPU 95%',
      instanceName: 'pg-prod-02',
    });

    expect(added).toBe(true);
    expect(useNotificationStore.getState().notifications).toHaveLength(2);
  });

  it('allows duplicate title after original is marked read', () => {
    const store = useNotificationStore.getState();

    store.addNotification({
      level: 'info',
      title: 'Baseline Updated',
      message: 'New baseline trained',
      instanceName: 'pg-prod-01',
    });

    // Mark all read
    useNotificationStore.getState().markAllRead();

    // Now same title+instance should be accepted
    const added = useNotificationStore.getState().addNotification({
      level: 'info',
      title: 'Baseline Updated',
      message: 'Another baseline trained',
      instanceName: 'pg-prod-01',
    });

    expect(added).toBe(true);
    expect(useNotificationStore.getState().notifications).toHaveLength(2);
  });

  // --- FIFO max 50 ---

  it('enforces max 50 notifications (FIFO)', () => {
    const store = useNotificationStore.getState();

    for (let i = 0; i < 55; i++) {
      useNotificationStore.getState().addNotification({
        level: 'info',
        title: `Notification ${i}`,
        message: `Message ${i}`,
        // Unique instanceName to avoid dedup
        instanceName: `instance-${i}`,
      });
    }

    const state = useNotificationStore.getState();
    expect(state.notifications).toHaveLength(50);
    // Most recent should be first (prepend order)
    expect(state.notifications[0].title).toBe('Notification 54');
    // Oldest should be trimmed (index 0..4 dropped)
    expect(state.notifications[49].title).toBe('Notification 5');
  });

  // --- markAllRead ---

  it('markAllRead sets all notifications to read and unreadCount to 0', () => {
    const store = useNotificationStore.getState();

    store.addNotification({
      level: 'warning',
      title: 'Alert 1',
      message: 'msg',
    });
    useNotificationStore.getState().addNotification({
      level: 'error',
      title: 'Alert 2',
      message: 'msg',
    });

    expect(useNotificationStore.getState().unreadCount).toBe(2);

    useNotificationStore.getState().markAllRead();

    const state = useNotificationStore.getState();
    expect(state.unreadCount).toBe(0);
    expect(state.notifications.every((n) => n.read)).toBe(true);
  });

  // --- clearAll ---

  it('clearAll removes all notifications and resets unreadCount', () => {
    const store = useNotificationStore.getState();

    store.addNotification({
      level: 'info',
      title: 'Alert',
      message: 'msg',
    });

    useNotificationStore.getState().clearAll();

    const state = useNotificationStore.getState();
    expect(state.notifications).toHaveLength(0);
    expect(state.unreadCount).toBe(0);
  });

  // --- togglePanel / closePanel ---

  it('togglePanel toggles panelOpen state', () => {
    expect(useNotificationStore.getState().panelOpen).toBe(false);
    useNotificationStore.getState().togglePanel();
    expect(useNotificationStore.getState().panelOpen).toBe(true);
    useNotificationStore.getState().togglePanel();
    expect(useNotificationStore.getState().panelOpen).toBe(false);
  });

  it('closePanel sets panelOpen to false', () => {
    useNotificationStore.setState({ panelOpen: true });
    useNotificationStore.getState().closePanel();
    expect(useNotificationStore.getState().panelOpen).toBe(false);
  });

  // --- unreadCount accuracy ---

  it('unreadCount reflects actual unread count after mixed operations', () => {
    const store = useNotificationStore.getState();

    store.addNotification({
      level: 'info',
      title: 'N1',
      message: 'msg',
      instanceName: 'a',
    });
    useNotificationStore.getState().addNotification({
      level: 'warning',
      title: 'N2',
      message: 'msg',
      instanceName: 'b',
    });
    useNotificationStore.getState().addNotification({
      level: 'error',
      title: 'N3',
      message: 'msg',
      instanceName: 'c',
    });

    expect(useNotificationStore.getState().unreadCount).toBe(3);

    // Mark all read
    useNotificationStore.getState().markAllRead();
    expect(useNotificationStore.getState().unreadCount).toBe(0);

    // Add one more
    useNotificationStore.getState().addNotification({
      level: 'info',
      title: 'N4',
      message: 'msg',
      instanceName: 'd',
    });
    expect(useNotificationStore.getState().unreadCount).toBe(1);
  });
});
