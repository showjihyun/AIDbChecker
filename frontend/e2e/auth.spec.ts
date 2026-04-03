// E2E: Authentication flow
import { test, expect } from '@playwright/test';

const ADMIN_EMAIL = 'admin@neuraldb.local';
const ADMIN_PASSWORD = process.env.SEED_ADMIN_PASSWORD || 'change-me-in-production';

test.describe('Authentication', () => {
  test('shows login page when not authenticated', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole('textbox', { name: /email/i })).toBeVisible();
  });

  test('login with valid credentials → redirects to dashboard', async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('textbox', { name: /email/i }).fill(ADMIN_EMAIL);
    await page.getByRole('textbox', { name: /password/i }).fill(ADMIN_PASSWORD);
    await page.getByRole('button', { name: /sign in/i }).click();

    await expect(page).toHaveURL('/', { timeout: 10_000 });
    await expect(page.locator('text=Dashboard').first()).toBeVisible({ timeout: 5_000 });
  });

  test('login with wrong password → shows error', async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('textbox', { name: /email/i }).fill(ADMIN_EMAIL);
    await page.getByRole('textbox', { name: /password/i }).fill('wrong-password');
    await page.getByRole('button', { name: /sign in/i }).click();

    await expect(page.locator('text=/incorrect|invalid|failed|Login failed/i').first()).toBeVisible({ timeout: 5_000 });
  });
});
