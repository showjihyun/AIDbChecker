---
name: gen-react-hook
description: Generate custom React hooks for the NeuralDB frontend. Creates hooks for data fetching (TanStack Query), WebSocket subscriptions (Socket.io), state management (Zustand), and common UI patterns.
argument-hint: "[hook-name] [type: query|mutation|websocket|store|util]"
allowed-tools: Read, Write, Glob, Grep, Edit
---

# Generate React Hook

## Arguments
- Hook name: $0
- Type: $1 (default: query)

## Reference
- Read `docs/TECH_STACK.md` for frontend stack
- Read `docs/FRONTEND_DESIGN.md` for UI patterns

## Output Location
```
# TanStack Query hooks
frontend/src/api/hooks/use{Name}.ts

# WebSocket hooks
frontend/src/hooks/use{Name}.ts

# Zustand stores
frontend/src/stores/{name}Store.ts

# Utility hooks
frontend/src/hooks/use{Name}.ts
```

## Templates

### TanStack Query (Data Fetching)
```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../client';
import type { {Name}Response, {Name}Create } from '../types';

export const {name}Keys = {
  all: ['{name}'] as const,
  lists: () => [...{name}Keys.all, 'list'] as const,
  list: (filters: Record<string, unknown>) => [...{name}Keys.lists(), filters] as const,
  details: () => [...{name}Keys.all, 'detail'] as const,
  detail: (id: string) => [...{name}Keys.details(), id] as const,
};

export function use{Name}List(params?: { limit?: number }) {
  return useQuery({
    queryKey: {name}Keys.list(params ?? {}),
    queryFn: () => apiClient.get<{Name}Response[]>('/api/v1/{name}', { params }),
  });
}

export function use{Name}(id: string) {
  return useQuery({
    queryKey: {name}Keys.detail(id),
    queryFn: () => apiClient.get<{Name}Response>(`/api/v1/{name}/${id}`),
    enabled: !!id,
  });
}

export function useCreate{Name}() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {Name}Create) => apiClient.post('/api/v1/{name}', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: {name}Keys.lists() }),
  });
}
```

### WebSocket Hook (Real-time)
```typescript
import { useEffect, useCallback, useRef } from 'react';
import { io, Socket } from 'socket.io-client';

export function use{Name}Socket(instanceId: string) {
  const socketRef = useRef<Socket | null>(null);
  const [data, setData] = useState<{Name}Data | null>(null);

  useEffect(() => {
    const socket = io('/ws/{name}', { query: { instanceId } });
    socketRef.current = socket;

    socket.on('{name}:update', (payload: {Name}Data) => setData(payload));
    socket.on('connect_error', (err) => console.error('{name} socket error:', err));

    return () => { socket.disconnect(); };
  }, [instanceId]);

  return { data, isConnected: socketRef.current?.connected ?? false };
}
```

### Zustand Store
```typescript
import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

interface {Name}State {
  selected{Name}: string | null;
  set{Name}: (id: string | null) => void;
}

export const use{Name}Store = create<{Name}State>()(
  devtools(
    persist(
      (set) => ({
        selected{Name}: null,
        set{Name}: (id) => set({ selected{Name}: id }),
      }),
      { name: '{name}-store' }
    )
  )
);
```

## Rules
- Query keys use factory pattern for cache invalidation
- WebSocket hooks clean up on unmount
- Zustand stores use devtools + persist middleware
- All hooks return typed data
- Error handling with `onError` callbacks
- Loading states exposed (`isLoading`, `isPending`)
