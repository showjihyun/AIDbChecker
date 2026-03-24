// Spec: TECH_STACK.md — TanStack Router setup
import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
} from '@tanstack/react-router';
import { MainLayout } from '@/components/layout/MainLayout';
import { DashboardPage } from '@/routes/pages/DashboardPage';
import { ASHExplorerPage } from '@/routes/pages/ASHExplorerPage';
import { SettingsPage } from '@/routes/pages/SettingsPage';

const rootRoute = createRootRoute({
  component: () => (
    <MainLayout>
      <Outlet />
    </MainLayout>
  ),
});

const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: DashboardPage,
});

const ashRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/ash',
  component: ASHExplorerPage,
});

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings',
  component: SettingsPage,
});

const routeTree = rootRoute.addChildren([dashboardRoute, ashRoute, settingsRoute]);

export const router = createRouter({ routeTree });

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
