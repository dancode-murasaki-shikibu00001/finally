import { test, expect } from '@playwright/test';

test.describe('Trade execution', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="trade-bar"]', { timeout: 10000 });
    // Wait for prices to load
    await page.waitForTimeout(2000);
  });

  test('buying shares decreases cash balance', async ({ page }) => {
    // Get initial cash balance
    const cashEl = page.locator('[data-testid="cash-balance"]');
    const initialCash = await cashEl.textContent();

    // Click AAPL to select it
    await page.locator('text=AAPL').first().click();

    // Enter quantity and buy
    await page.locator('[data-testid="trade-quantity"]').fill('1');
    await page.locator('[data-testid="buy-button"]').click();

    // Wait for portfolio to update
    await page.waitForTimeout(2000);

    // Cash should have decreased
    const newCash = await cashEl.textContent();
    expect(newCash).not.toBe(initialCash);
  });

  test('position appears after buying', async ({ page }) => {
    await page.locator('text=AAPL').first().click();
    await page.locator('[data-testid="trade-quantity"]').fill('1');
    await page.locator('[data-testid="buy-button"]').click();

    await page.waitForTimeout(2000);

    // AAPL should appear in positions table
    await expect(page.locator('[data-testid="positions-table"]').locator('text=AAPL')).toBeVisible({ timeout: 5000 });
  });

  test('insufficient cash shows error', async ({ page }) => {
    await page.locator('text=AAPL').first().click();
    await page.locator('[data-testid="trade-quantity"]').fill('99999');
    await page.locator('[data-testid="buy-button"]').click();

    // Should show an error message
    await expect(page.locator('[data-testid="trade-status"]')).toContainText(/insufficient|error|failed/i, { timeout: 5000 });
  });
});
