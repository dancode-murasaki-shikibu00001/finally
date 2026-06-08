import { test, expect } from '@playwright/test';

test.describe('Watchlist management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="watchlist"]', { timeout: 10000 });
  });

  test('can add a ticker to the watchlist', async ({ page }) => {
    const input = page.locator('[data-testid="add-ticker-input"]');
    await input.fill('AMD');
    await input.press('Enter');
    await expect(page.locator('text=AMD')).toBeVisible({ timeout: 5000 });
  });

  test('can remove a ticker from the watchlist', async ({ page }) => {
    // First verify a default ticker is there
    await expect(page.locator('text=AAPL').first()).toBeVisible();
    // Hover over AAPL row to reveal the remove button, then remove it
    await page.locator('text=AAPL').first().hover();
    await page.locator('[data-testid="remove-ticker-AAPL"]').click();
    await expect(page.locator('text=AAPL').first()).not.toBeVisible({ timeout: 5000 });
  });
});
