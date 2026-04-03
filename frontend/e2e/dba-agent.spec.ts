// E2E: DBA Agent Chat — Claude Sonnet 4.6 Native Tool Use
import { test, expect } from '@playwright/test';

const ADMIN_EMAIL = 'admin@neuraldb.local';
const ADMIN_PASSWORD = process.env.SEED_ADMIN_PASSWORD || 'change-me-in-production';

// Helper: login and navigate
async function loginAndGo(page: any, path: string) {
  await page.goto('/login');
  await page.getByRole('textbox', { name: /email/i }).fill(ADMIN_EMAIL);
  await page.getByRole('textbox', { name: /password/i }).fill(ADMIN_PASSWORD);
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page).toHaveURL('/', { timeout: 10_000 });
  if (path !== '/') {
    await page.goto(path);
  }
}

test.describe('DBA Agent Chat', () => {
  test('mini chat opens and shows model info', async ({ page }) => {
    await loginAndGo(page, '/');

    // Click floating DBA Agent button
    const chatBtn = page.locator('button[aria-label="Open DBA Agent"]');
    await expect(chatBtn).toBeVisible({ timeout: 5_000 });
    await chatBtn.click();

    // Chat window should open with model info
    await expect(page.locator('text=DBA Agent')).toBeVisible();
    // Should show LLM model (anthropic · claude-sonnet-4-6)
    await expect(
      page.locator('text=/anthropic|claude|ollama/i').first()
    ).toBeVisible({ timeout: 5_000 });
  });

  test('DBA Agent page shows instance selector', async ({ page }) => {
    await loginAndGo(page, '/dba');

    await expect(page.locator('text=DBA Agent')).toBeVisible();
    await expect(page.locator('text=/AI-powered/i')).toBeVisible();
  });

  test('send question and receive Korean answer', async ({ page }) => {
    test.setTimeout(60_000); // Claude API may take time

    await loginAndGo(page, '/');

    // Open mini chat
    await page.locator('button[aria-label="Open DBA Agent"]').click();
    await expect(page.locator('text=DBA Agent')).toBeVisible();

    // Select instance (first in dropdown)
    const select = page.locator('select').first();
    await select.waitFor({ timeout: 5_000 });
    const options = await select.locator('option').allTextContents();
    if (options.length > 1) {
      await select.selectOption({ index: 1 }); // Skip placeholder
    }

    // Send message
    const input = page.locator('input[placeholder*="Ask"]');
    await input.fill('DB 상태 알려줘');
    await input.press('Enter');

    // Wait for response (loading indicator → answer)
    await expect(page.locator('text=/Analyzing/i')).toBeVisible({ timeout: 5_000 });

    // Agent should respond (wait up to 45s for Claude)
    await expect(
      page.locator('text=/시스템 상태|데이터베이스|healthy|HEALTHY|상태/i').first()
    ).toBeVisible({ timeout: 45_000 });

    // Should show feedback buttons
    await expect(page.locator('span:has-text("thumb_up")').first()).toBeVisible();
  });
});
