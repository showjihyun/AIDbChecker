// Spec: TECH_STACK.md — TanStack Router setup + MVP-ADMIN-001 auth guard
import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  redirect,
} from '@tanstack/react-router';
import { MainLayout } from '@/components/layout/MainLayout';
import { DashboardPage } from '@/routes/pages/DashboardPage';
import { ASHExplorerPage } from '@/routes/pages/ASHExplorerPage';
import { SettingsPage } from '@/routes/pages/SettingsPage';
import { LLMSettingsPage } from '@/routes/pages/LLMSettingsPage';
import { IncidentsPage } from '@/routes/pages/IncidentsPage';
import { InstancesManagementPage } from '@/routes/pages/InstancesManagementPage';
import { TuningPage } from '@/routes/pages/TuningPage';
import { DBAAgentPage } from '@/routes/pages/DBAAgentPage';
import { PlaybooksPage } from '@/routes/pages/PlaybooksPage';
import { TasksPage } from '@/routes/pages/TasksPage';
import { DBAReportsPage } from '@/routes/pages/DBAReportsPage';
import { LLMObservabilityPage } from '@/routes/pages/LLMObservabilityPage';
import { LoginPage } from '@/routes/pages/LoginPage';
import { useAuthStore } from '@/stores/authStore';

// --- Public root (no layout) ---
const rootRoute = createRootRoute({
  component: () => <Outlet />,
});

// --- Login route (full-screen, no MainLayout) ---
const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  beforeLoad: () => {
    const { isAuthenticated } = useAuthStore.getState();
    if (isAuthenticated) {
      throw redirect({ to: '/' });
    }
  },
  component: LoginPage,
});

// --- Authenticated layout route (wraps all protected pages) ---
const authenticatedRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: 'authenticated',
  beforeLoad: () => {
    const { isAuthenticated } = useAuthStore.getState();
    if (!isAuthenticated) {
      throw redirect({ to: '/login' });
    }
  },
  component: () => (
    <MainLayout>
      <Outlet />
    </MainLayout>
  ),
});

const dashboardRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: '/',
  component: DashboardPage,
});

const ashRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: '/ash',
  component: ASHExplorerPage,
});

const incidentsRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: '/incidents',
  component: IncidentsPage,
});

const instancesRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: '/instances',
  component: InstancesManagementPage,
});

const settingsRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: '/settings',
  component: SettingsPage,
});

const llmSettingsRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: '/settings/llm',
  component: LLMSettingsPage,
});

const tuningRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: '/tuning',
  component: TuningPage,
});

const dbaAgentRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: '/dba',
  component: DBAAgentPage,
});

const llmObsRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: '/llm-observability',
  component: LLMObservabilityPage,
});

const playbooksRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: '/playbooks',
  component: PlaybooksPage,
});

const tasksRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: '/tasks',
  component: TasksPage,
});

const reportsRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: '/reports',
  component: DBAReportsPage,
});

const routeTree = rootRoute.addChildren([
  loginRoute,
  authenticatedRoute.addChildren([
    dashboardRoute, ashRoute, incidentsRoute, instancesRoute,
    tuningRoute, dbaAgentRoute, llmObsRoute, playbooksRoute, tasksRoute, reportsRoute,
    settingsRoute, llmSettingsRoute,
  ]),
]);

export const router = createRouter({ routeTree });

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
