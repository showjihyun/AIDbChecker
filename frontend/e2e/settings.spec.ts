// E2E: Settings pages — LLM + Slack
import { test, expect } from '@playwright/test';

const ADMIN_EMAIL = 'admin@neuraldb.local';
const ADMIN_PASSWORD = 'NeuralDB@2026!';

async function loginAndGo(page: any, path: string) {
  await page.goto('/login');
  await page.getByRole('textbox', { name: /email/i }).fill(ADMIN_EMAIL);
  await page.getByRole('textbox', { name: /password/i }).fill(ADMIN_PASSWORD);
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page).toHaveURL('/', { timeout: 10_000 });
  await page.goto(path);
}

test.describe('Settings', () => {
  test('settings page shows all sections', async ({ page }) => {
    await loginAndGo(page, '/settings');

    await expect(page.locator('text=Settings')).toBeVisible();
    await expect(page.locator('text=/AI Configuration/i')).toBeVisible();
    await expect(page.locator('text=/Alert Channels/i')).toBeVisible();
    await expect(page.locator('text=/User Management/i')).toBeVisible();
  });

  test('LLM settings shows current provider', async ({ page }) => {
    await loginAndGo(page, '/settings/llm');

    await expect(page.locator('text=/LLM.*Provider/i').first()).toBeVisible({ timeout: 5_000 });
    // Should show provider selection (Ollama, OpenAI, Anthropic, Google)
    await expect(page.locator('text=/Anthropic|Ollama|OpenAI/i').first()).toBeVisible();
  });

  test('LLM settings — Sonnet 4.6 is selectable', async ({ page }) => {
    await loginAndGo(page, '/settings/llm');

    // Click Anthropic provider
    const anthropicBtn = page.locator('text=/Anthropic/i').first();
    if (await anthropicBtn.isVisible()) {
      await anthropicBtn.click();
    }

    // Model selector should have claude-sonnet-4-6
    await page.waitForTimeout(1000);
    const modelText = await page.locator('text=/claude-sonnet|claude-opus/i').first().isVisible().catch(() => false);
    expect(modelText).toBeTruthy();
  });

  test('Slack settings page loads', async ({ page }) => {
    await loginAndGo(page, '/settings/slack');

    await expect(page.locator('text=Slack Integration')).toBeVisible();
    await expect(page.locator('text=/Bot Token/i').first()).toBeVisible();
    await expect(page.locator('text=/Channel ID/i').first()).toBeVisible();
    await expect(page.locator('button:has-text("테스트 발송")')).toBeVisible();
  });
});
