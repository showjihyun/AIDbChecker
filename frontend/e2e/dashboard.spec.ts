// E2E: Dashboard + DBA Agent
import { test, expect } from '@playwright/test';

const ADMIN_EMAIL = 'admin@neuraldb.local';
const ADMIN_PASSWORD = 'NeuralDB@2026!';

// Helper: login before each test
async function login(page: import('@playwright/test').Page) {
  await page.goto('/login');
  await page.getByRole('textbox', { name: /email/i }).fill(ADMIN_EMAIL);
  await page.getByRole('textbox', { name: /password/i }).fill(ADMIN_PASSWORD);
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page).toHaveURL('/', { timeout: 10_000 });
}

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('shows system health panel', async ({ page }) => {
    await expect(page.locator('text=System Health').first()).toBeVisible({ timeout: 10_000 });
  });

  test('shows instance cards', async ({ page }) => {
    // Wait for instances to load
    await expect(page.locator('text=/neuraldb|geoai/i').first()).toBeVisible({ timeout: 15_000 });
  });

  test('navigation sidebar has DBA Agent link', async ({ page }) => {
    await expect(page.locator('text=DBA Agent').first()).toBeVisible();
  });
});

test.describe('DBA Agent Mini Chat', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('floating button is visible on dashboard', async ({ page }) => {
    // The smart_toy icon button should be in bottom-right
    const chatBtn = page.locator('button[aria-label="Open DBA Agent"]');
    await expect(chatBtn).toBeVisible({ timeout: 5_000 });
  });

  test('clicking opens chat widget with instance selector', async ({ page }) => {
    const chatBtn = page.locator('button[aria-label="Open DBA Agent"]');
    await chatBtn.click();

    // Widget should show instance dropdown
    await expect(page.locator('select').last()).toBeVisible();
    await expect(page.locator('text=DBA Agent').first()).toBeVisible();
  });

  test('chat disabled without instance selection', async ({ page }) => {
    const chatBtn = page.locator('button[aria-label="Open DBA Agent"]');
    await chatBtn.click();

    // Should show "Select a DB instance" message
    await expect(page.locator('text=/Select.*instance/i').first()).toBeVisible();
  });
});

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('can navigate to ASH Explorer', async ({ page }) => {
    await page.locator('text=ASH Explorer').first().click();
    await expect(page).toHaveURL(/\/ash/);
  });

  test('can navigate to Incidents', async ({ page }) => {
    await page.locator('text=Incidents').first().click();
    await expect(page).toHaveURL(/\/incidents/);
  });

  test('can navigate to Settings', async ({ page }) => {
    await page.locator('text=Settings').first().click();
    await expect(page).toHaveURL(/\/settings/);
  });
});
