// E2E: Authentication flow
import { test, expect } from '@playwright/test';

const ADMIN_EMAIL = 'admin@neuraldb.local';
const ADMIN_PASSWORD = 'NeuralDB@2026!';

test.describe('Authentication', () => {
  test('shows login page when not authenticated', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByPlaceholder(/email/i)).toBeVisible();
  });

  test('login with valid credentials → redirects to dashboard', async ({ page }) => {
    await page.goto('/login');
    await page.getByPlaceholder(/email/i).fill(ADMIN_EMAIL);
    await page.getByPlaceholder(/password/i).fill(ADMIN_PASSWORD);
    await page.getByRole('button', { name: /sign in|log in/i }).click();

    // Should redirect to dashboard
    await expect(page).toHaveURL('/', { timeout: 10_000 });
    // Dashboard should show content
    await expect(page.locator('text=Dashboard').first()).toBeVisible({ timeout: 5_000 });
  });

  test('login with wrong password → shows error', async ({ page }) => {
    await page.goto('/login');
    await page.getByPlaceholder(/email/i).fill(ADMIN_EMAIL);
    await page.getByPlaceholder(/password/i).fill('wrong-password');
    await page.getByRole('button', { name: /sign in|log in/i }).click();

    // Should show error message
    await expect(page.locator('text=/invalid|incorrect|failed/i').first()).toBeVisible({ timeout: 5_000 });
  });
});
