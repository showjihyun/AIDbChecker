// Spec: FS-KPI-001 AC-9 — Toast store tests
import { describe, it, expect, beforeEach } from 'vitest';
import { useToastStore } from '@/components/common/Toast';

function resetStore() {
  useToastStore.setState({ toasts: [] });
}

describe('toastStore', () => {
  beforeEach(() => {
    resetStore();
  });

  it('addToast appends a toast with generated id', () => {
    const store = useToastStore.getState();
    store.addToast({
      level: 'info',
      title: 'Test',
      message: 'Hello',
    });

    const state = useToastStore.getState();
    expect(state.toasts).toHaveLength(1);
    expect(state.toasts[0].title).toBe('Test');
    expect(state.toasts[0].level).toBe('info');
    expect(state.toasts[0].id).toBeTruthy();
  });

  it('addToast supports all 3 levels', () => {
    const store = useToastStore.getState();
    store.addToast({ level: 'info', title: 'Info', message: 'msg' });
    useToastStore.getState().addToast({ level: 'warning', title: 'Warn', message: 'msg' });
    useToastStore.getState().addToast({ level: 'error', title: 'Error', message: 'msg' });

    const state = useToastStore.getState();
    expect(state.toasts).toHaveLength(3);
    expect(state.toasts.map((t) => t.level)).toEqual(['info', 'warning', 'error']);
  });

  it('removeToast removes the correct toast by id', () => {
    const store = useToastStore.getState();
    store.addToast({ level: 'info', title: 'Keep', message: 'keep' });
    useToastStore.getState().addToast({ level: 'error', title: 'Remove', message: 'remove' });

    const toasts = useToastStore.getState().toasts;
    expect(toasts).toHaveLength(2);

    const removeId = toasts.find((t) => t.title === 'Remove')!.id;
    useToastStore.getState().removeToast(removeId);

    const state = useToastStore.getState();
    expect(state.toasts).toHaveLength(1);
    expect(state.toasts[0].title).toBe('Keep');
  });

  it('removeToast with nonexistent id does nothing', () => {
    const store = useToastStore.getState();
    store.addToast({ level: 'info', title: 'Only', message: 'msg' });

    useToastStore.getState().removeToast('nonexistent-id');
    expect(useToastStore.getState().toasts).toHaveLength(1);
  });

  it('generates unique ids for each toast', () => {
    const store = useToastStore.getState();
    store.addToast({ level: 'info', title: 'A', message: 'msg' });
    useToastStore.getState().addToast({ level: 'info', title: 'B', message: 'msg' });

    const ids = useToastStore.getState().toasts.map((t) => t.id);
    expect(ids[0]).not.toBe(ids[1]);
  });
});
