# Frontend Test Spec: React 단위/컴포넌트 테스트 전략

> **Spec ID**: TEST-FE-001
> **PRD 참조**: FR-DASH-001~005, FR-AI-011 (Confidence Badge), MVP-DASH-001~005
> **상태**: Approved
> **프레임워크**: Vitest + React Testing Library
> **디자인 참조**: `docs/FRONTEND_DESIGN.md`
> **테스트 전략**: `TEST_STRATEGY.md` (Spec-Driven Test Generation)

---

## 1. 테스트 원칙

| 원칙 | 설명 |
|------|------|
| **BE 의존 없음** | API는 MSW(Mock Service Worker)로 모킹. BE 서버 불필요 |
| **사용자 관점** | DOM 구조가 아닌 "사용자가 보는 것"을 테스트 (`getByRole`, `getByText`) |
| **디자인 토큰 검증** | 색상/폰트가 FRONTEND_DESIGN.md와 일치하는지 스냅샷으로 확인 |
| **접근성 기본** | 모든 인터랙티브 요소에 ARIA label 존재 여부 검증 |

---

## 2. 디렉토리 구조

```
frontend/
├── src/
│   ├── components/
│   │   ├── common/
│   │   │   ├── Button/
│   │   │   │   ├── Button.tsx
│   │   │   │   ├── Button.test.tsx       ← 컴포넌트 옆에 위치
│   │   │   │   └── index.ts
│   │   │   ├── Badge/
│   │   │   │   ├── Badge.tsx
│   │   │   │   └── Badge.test.tsx
│   │   │   └── ...
│   │   ├── dashboard/
│   │   │   ├── MetricCard/
│   │   │   │   ├── MetricCard.tsx
│   │   │   │   └── MetricCard.test.tsx
│   │   │   └── ...
│   │   └── ...
│   ├── hooks/
│   │   ├── useWebSocket.ts
│   │   └── useWebSocket.test.ts
│   ├── api/
│   │   └── hooks/
│   │       ├── useInstances.ts
│   │       └── useInstances.test.ts
│   └── stores/
│       ├── incidentStore.ts
│       └── incidentStore.test.ts
│
│   ※ v3.3 신규 컴포넌트 테스트:
│   ├── components/common/ConfidenceBadge/
│   │   ├── ConfidenceBadge.tsx
│   │   └── ConfidenceBadge.test.tsx    ← Spec: FS-AI-011 AC-4
│   ├── components/diagnosis/ReasoningChain/
│   │   ├── ReasoningChain.tsx
│   │   └── ReasoningChain.test.tsx     ← Spec: FS-AI-011 AC-5
│   └── components/diagnosis/EvidenceLink/
│       ├── EvidenceLink.tsx
│       └── EvidenceLink.test.tsx       ← Spec: FS-AI-011 AC-6
├── tests/
│   ├── setup.ts                          ← Vitest global setup
│   ├── mocks/
│   │   ├── handlers.ts                   ← MSW request handlers
│   │   └── server.ts                     ← MSW server setup
│   └── utils/
│       └── renderWithProviders.tsx        ← TanStack Query + Router wrapper
└── vitest.config.ts
```

---

## 3. 테스트 설정

### 3.1 Vitest 설정

```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.test.*', 'src/types/**'],
      thresholds: {
        lines: 80,
        branches: 75,
        functions: 80,
        statements: 80,
      },
    },
  },
});
```

### 3.2 MSW (Mock Service Worker)

```typescript
// tests/mocks/handlers.ts
import { http, HttpResponse } from 'msw';

export const handlers = [
  // Instances
  http.get('/api/v1/instances', () => {
    return HttpResponse.json({
      items: [
        { id: 'uuid-1', name: 'pg-prod-01', db_type: 'postgresql', health_status: 'healthy', ... },
        { id: 'uuid-2', name: 'pg-prod-02', db_type: 'postgresql', health_status: 'degraded', ... },
      ],
      total: 2,
      has_next: false,
    });
  }),

  // Metrics
  http.get('/api/v1/instances/:id/metrics/latest', ({ params }) => {
    return HttpResponse.json({
      instance_id: params.id,
      sampled_at: new Date().toISOString(),
      metrics: { cpu_usage: 45.2, memory_usage: 72.1, active_connections: 42, tps: 1240 },
    });
  }),

  // Incidents
  http.get('/api/v1/incidents', () => {
    return HttpResponse.json({
      items: [
        { id: 'inc-1', severity: 'critical', status: 'open', title: 'CPU Spike on pg-prod-01' },
      ],
      total: 1,
      has_next: false,
    });
  }),

  // Auth
  http.post('/api/v1/auth/login', () => {
    return HttpResponse.json({ access_token: 'mock-jwt', refresh_token: 'mock-refresh' });
  }),

  // System Health
  http.get('/api/v1/system/health', () => {
    return HttpResponse.json({
      status: 'healthy',
      components: {
        database: { status: 'healthy', latency_ms: 2.1 },
        valkey: { status: 'healthy', latency_ms: 0.3 },
        kafka: { status: 'healthy', consumer_lag: 12 },
        celery: { status: 'healthy', active_workers: 4, queued_tasks: 3 },
      },
    });
  }),
];
```

### 3.3 렌더 유틸리티

```typescript
// tests/utils/renderWithProviders.tsx
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

export function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  );
}
```

---

## 4. 컴포넌트별 테스트 시나리오

### 4.1 Common Components

#### Button
```typescript
// src/components/common/Button/Button.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { Button } from './Button';

describe('Button', () => {
  it('renders with correct text', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument();
  });

  it('applies primary variant styles', () => {
    render(<Button variant="primary">Save</Button>);
    const btn = screen.getByRole('button');
    expect(btn.className).toContain('bg-primary-container');
  });

  it('calls onClick handler', async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Click</Button>);
    fireEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('is disabled when loading', () => {
    render(<Button isLoading>Save</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });
});
```

#### Badge (Status)
```typescript
describe('Badge', () => {
  it.each([
    ['critical', 'bg-error'],
    ['warning', 'bg-amber-500/20'],
    ['resolved', 'bg-tertiary/20'],
    ['predictive', 'bg-secondary/20'],
  ])('renders %s severity with correct style', (severity, expectedClass) => {
    render(<Badge severity={severity}>Label</Badge>);
    expect(screen.getByText('Label').className).toContain(expectedClass);
  });
});
```

### 4.2 Dashboard Components

#### MetricCard
```typescript
// src/components/dashboard/MetricCard/MetricCard.test.tsx
describe('MetricCard', () => {
  it('renders metric label and value', () => {
    render(<MetricCard label="Total Instances" value={52} icon="dns" />);
    expect(screen.getByText('Total Instances')).toBeInTheDocument();
    expect(screen.getByText('52')).toBeInTheDocument();
  });

  it('shows trend indicator when provided', () => {
    render(<MetricCard label="Instances" value={52} trend={+3} />);
    expect(screen.getByText('+3 this week')).toBeInTheDocument();
  });

  it('applies error style for anomaly metrics', () => {
    render(<MetricCard label="Anomalies" value={2} variant="error" />);
    expect(screen.getByText('2').className).toContain('text-error');
  });
});
```

#### IncidentList
```typescript
describe('IncidentList', () => {
  it('renders incidents from API', async () => {
    renderWithProviders(<IncidentList />);
    expect(await screen.findByText('CPU Spike on pg-prod-01')).toBeInTheDocument();
  });

  it('shows severity badge', async () => {
    renderWithProviders(<IncidentList />);
    expect(await screen.findByText('CRITICAL')).toBeInTheDocument();
  });

  it('displays empty state when no incidents', async () => {
    // Override MSW handler for empty response
    server.use(http.get('/api/v1/incidents', () => HttpResponse.json({ items: [], total: 0 })));
    renderWithProviders(<IncidentList />);
    expect(await screen.findByText('No active incidents')).toBeInTheDocument();
  });
});
```

### 4.3 ASH Components

#### ASHHeatmap
```typescript
describe('ASHHeatmap', () => {
  it('renders heatmap container', () => {
    render(<ASHHeatmap instanceId="uuid-1" />);
    expect(screen.getByTestId('ash-heatmap')).toBeInTheDocument();
  });

  it('shows legend with wait event categories', () => {
    render(<ASHHeatmap instanceId="uuid-1" />);
    expect(screen.getByText('CPU')).toBeInTheDocument();
    expect(screen.getByText('I/O')).toBeInTheDocument();
    expect(screen.getByText('Lock')).toBeInTheDocument();
  });

  it('displays time range selector', () => {
    render(<ASHHeatmap instanceId="uuid-1" />);
    expect(screen.getByRole('button', { name: '1s' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '10s' })).toBeInTheDocument();
  });
});
```

#### SessionTable
```typescript
describe('SessionTable', () => {
  it('renders session columns', async () => {
    renderWithProviders(<SessionTable instanceId="uuid-1" />);
    expect(await screen.findByText('PID')).toBeInTheDocument();
    expect(screen.getByText('Query Snippet')).toBeInTheDocument();
    expect(screen.getByText('Wait Event')).toBeInTheDocument();
  });

  it('shows Explain button on row hover', async () => {
    renderWithProviders(<SessionTable instanceId="uuid-1" />);
    const row = await screen.findByTestId('session-row-0');
    fireEvent.mouseEnter(row);
    expect(screen.getByText('Explain')).toBeVisible();
  });
});
```

### 4.4 NL2SQL Chat

```typescript
describe('NL2SQLChat', () => {
  it('sends user question and displays result', async () => {
    renderWithProviders(<NL2SQLChat instanceId="uuid-1" />);

    const input = screen.getByPlaceholderText('Ask follow up...');
    fireEvent.change(input, { target: { value: '가장 느린 쿼리 5개' } });
    fireEvent.click(screen.getByTestId('send-button'));

    expect(await screen.findByText(/SELECT/)).toBeInTheDocument();
  });

  it('shows loading state while querying', async () => {
    renderWithProviders(<NL2SQLChat instanceId="uuid-1" />);
    const input = screen.getByPlaceholderText('Ask follow up...');
    fireEvent.change(input, { target: { value: 'test' } });
    fireEvent.click(screen.getByTestId('send-button'));

    expect(screen.getByTestId('chat-loading')).toBeInTheDocument();
  });
});
```

### 4.5 Settings - Add Database Wizard

```typescript
// 디자인 참조: docs/screen6_add_database.html
describe('AddDatabaseWizard', () => {
  it('shows 3-step indicator (TYPE → CONNECTION → OPTIONS)', () => {
    render(<AddDatabaseWizard />);
    expect(screen.getByText('TYPE')).toBeInTheDocument();
    expect(screen.getByText('CONNECTION')).toBeInTheDocument();
    expect(screen.getByText('OPTIONS')).toBeInTheDocument();
  });

  it('step 1: selects PostgreSQL by default', () => {
    render(<AddDatabaseWizard />);
    expect(screen.getByTestId('db-type-postgresql')).toHaveClass('border-primary');
  });

  it('step 2: validates required fields', async () => {
    render(<AddDatabaseWizard initialStep={2} />);
    fireEvent.click(screen.getByText('Save & Start Monitoring'));
    expect(await screen.findByText(/host.*required/i)).toBeInTheDocument();
  });

  it('test connection button calls API', async () => {
    renderWithProviders(<AddDatabaseWizard initialStep={2} />);
    fireEvent.change(screen.getByLabelText('Host Address'), { target: { value: 'localhost' } });
    fireEvent.change(screen.getByLabelText('Port'), { target: { value: '5432' } });
    fireEvent.click(screen.getByText('Test Connection'));

    expect(await screen.findByText(/connection successful/i)).toBeInTheDocument();
  });
});
```

---

## 5. Hook 테스트

### TanStack Query Hooks

```typescript
// src/api/hooks/useInstances.test.ts
import { renderHook, waitFor } from '@testing-library/react';
import { useInstanceList } from './useInstances';
import { createWrapper } from '../../../tests/utils/renderWithProviders';

describe('useInstanceList', () => {
  it('fetches instance list', async () => {
    const { result } = renderHook(() => useInstanceList(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(2);
    expect(result.current.data?.items[0].name).toBe('pg-prod-01');
  });

  it('returns loading state initially', () => {
    const { result } = renderHook(() => useInstanceList(), { wrapper: createWrapper() });
    expect(result.current.isLoading).toBe(true);
  });
});
```

### WebSocket Hooks

```typescript
// src/hooks/useWebSocket.test.ts
import { renderHook, act } from '@testing-library/react';
import { useMetricSocket } from './useMetricSocket';
import { io } from 'socket.io-client';

vi.mock('socket.io-client');

describe('useMetricSocket', () => {
  it('connects to /ws/metrics namespace', () => {
    renderHook(() => useMetricSocket('uuid-1'));
    expect(io).toHaveBeenCalledWith('/ws/metrics', expect.objectContaining({
      query: { instanceId: 'uuid-1' },
    }));
  });

  it('updates data on metric:update event', async () => {
    const mockSocket = { on: vi.fn(), disconnect: vi.fn(), connected: true };
    vi.mocked(io).mockReturnValue(mockSocket as any);

    const { result } = renderHook(() => useMetricSocket('uuid-1'));

    // Simulate server event
    const callback = mockSocket.on.mock.calls.find(c => c[0] === 'metric:update')?.[1];
    act(() => callback?.({ cpu_usage: 88.5, tps: 1500 }));

    expect(result.current.data?.cpu_usage).toBe(88.5);
  });

  it('disconnects on unmount', () => {
    const mockSocket = { on: vi.fn(), disconnect: vi.fn(), connected: true };
    vi.mocked(io).mockReturnValue(mockSocket as any);

    const { unmount } = renderHook(() => useMetricSocket('uuid-1'));
    unmount();
    expect(mockSocket.disconnect).toHaveBeenCalled();
  });
});
```

---

## 6. Store 테스트

```typescript
// src/stores/incidentStore.test.ts
import { useIncidentStore } from './incidentStore';

describe('incidentStore', () => {
  beforeEach(() => useIncidentStore.setState({ selectedIncident: null }));

  it('selects an incident', () => {
    useIncidentStore.getState().setIncident('inc-1');
    expect(useIncidentStore.getState().selectedIncident).toBe('inc-1');
  });

  it('clears selection', () => {
    useIncidentStore.getState().setIncident('inc-1');
    useIncidentStore.getState().setIncident(null);
    expect(useIncidentStore.getState().selectedIncident).toBeNull();
  });
});
```

---

## 7. Coverage 목표 (모듈별)

| 모듈 | Lines | Branches | 우선순위 |
|------|-------|----------|---------|
| `components/common/` | 90% | 85% | P0 — 재사용 컴포넌트 |
| `components/dashboard/` | 80% | 75% | P0 — MVP 핵심 |
| `components/ash/` | 80% | 75% | P0 — MVP 핵심 |
| `components/nl2sql/` | 75% | 70% | P0 |
| `api/hooks/` | 85% | 80% | P0 — 데이터 레이어 |
| `hooks/` | 80% | 75% | P0 |
| `stores/` | 90% | 85% | P0 — 상태 레이어 |
| `components/topology/` | 60% | 50% | P1 — Phase 3 |
| `components/playbook/` | 60% | 50% | P1 — Phase 2 |
| `components/diagnosis/` | 70% | 60% | P1 — Phase 2 |
| `lib/` (유틸리티) | 95% | 90% | P0 — 순수 함수 |

---

## 8. 실행 명령

```bash
cd frontend

# 전체 단위 테스트
npm run test

# Watch 모드 (개발 중)
npm run test -- --watch

# Coverage 리포트
npm run test -- --coverage

# 특정 파일만
npm run test -- src/components/common/Button/Button.test.tsx
```
