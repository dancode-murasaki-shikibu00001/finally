import { test, expect } from '@playwright/test';

test.describe('Fresh start', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // Wait for the page to load and SSE to connect
    await page.waitForSelector('[data-testid="connection-status"]', { state: 'visible', timeout: 15000 });
  });

  test('shows FinAlly header', async ({ page }) => {
    await expect(page.locator('text=FinAlly')).toBeVisible();
  });

  test('shows $10,000 starting cash balance', async ({ page }) => {
    await expect(page.locator('[data-testid="cash-balance"]')).toContainText('10,000');
  });

  test('shows default watchlist with tickers', async ({ page }) => {
    // At least one of the default tickers should be visible
    const tickers = ['AAPL', 'GOOGL', 'MSFT', 'NVDA', 'TSLA'];
    let found = false;
    for (const ticker of tickers) {
      const el = page.locator(`text=${ticker}`).first();
      if (await el.isVisible()) { found = true; break; }
    }
    expect(found).toBe(true);
  });

  test('shows connection status indicator', async ({ page }) => {
    const status = page.locator('[data-testid="connection-status"]');
    await expect(status).toBeVisible();
  });

  test('prices are updating (SSE working)', async ({ page }) => {
    // Wait for at least one price to appear
    await page.waitForFunction(() => {
      const prices = document.querySelectorAll('[data-testid="ticker-price"]');
      return prices.length > 0 && prices[0].textContent !== '0.00' && prices[0].textContent !== '';
    }, { timeout: 10000 });
  });
});
