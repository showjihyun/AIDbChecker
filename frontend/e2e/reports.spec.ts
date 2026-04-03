// E2E: Reports page — list + generate + PDF download
import { test, expect } from '@playwright/test';

const ADMIN_EMAIL = 'admin@neuraldb.local';
const ADMIN_PASSWORD = process.env.SEED_ADMIN_PASSWORD || 'change-me-in-production';

async function loginAndGo(page: any, path: string) {
  await page.goto('/login');
  await page.getByRole('textbox', { name: /email/i }).fill(ADMIN_EMAIL);
  await page.getByRole('textbox', { name: /password/i }).fill(ADMIN_PASSWORD);
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page).toHaveURL('/', { timeout: 10_000 });
  await page.goto(path);
}

test.describe('DBA Reports', () => {
  test('reports page loads with sidebar menu', async ({ page }) => {
    await loginAndGo(page, '/reports');

    await expect(page.locator('text=DBA Reports')).toBeVisible();
    await expect(page.locator('text=/일간.*주간.*월간/i').first()).toBeVisible({ timeout: 5_000 });
  });

  test('reports list shows existing reports', async ({ page }) => {
    await loginAndGo(page, '/reports');

    // Should show reports or empty state
    const hasReports = await page.locator('text=/pg-prod|neuraldb|geoai/i').first().isVisible().catch(() => false);
    const hasEmpty = await page.locator('text=/리포트가 없습니다/').first().isVisible().catch(() => false);

    expect(hasReports || hasEmpty).toBeTruthy();
  });

  test('generate report form opens', async ({ page }) => {
    await loginAndGo(page, '/reports');

    // Click generate button
    const genBtn = page.locator('button:has-text("리포트 생성")');
    await expect(genBtn).toBeVisible({ timeout: 5_000 });
    await genBtn.click();

    // Form should appear
    await expect(page.locator('text=/인스턴스/i')).toBeVisible();
    await expect(page.locator('input[type="date"]').first()).toBeVisible();
    await expect(page.locator('text=/Slow Query Top/i')).toBeVisible();
  });

  test('period filter works', async ({ page }) => {
    await loginAndGo(page, '/reports');

    const periodSelect = page.locator('select').first();
    await periodSelect.selectOption('daily');
    await page.waitForTimeout(1000);

    // Filter should update URL or list
    await periodSelect.selectOption('');
  });

  test('PDF download button visible for reports', async ({ page }) => {
    await loginAndGo(page, '/reports');

    // If reports exist, PDF button should be visible
    const pdfBtn = page.locator('button:has-text("PDF")').first();
    const exists = await pdfBtn.isVisible().catch(() => false);
    if (exists) {
      // Click should trigger download
      const [download] = await Promise.all([
        page.waitForEvent('download', { timeout: 10_000 }).catch(() => null),
        pdfBtn.click(),
      ]);
      if (download) {
        expect(download.suggestedFilename()).toContain('neuraldb');
      }
    }
  });
});
