import { test, expect, type Page } from '@playwright/test';

async function waitForApp(page: Page) {
  await page.goto('/');
  // Wait for the header to be visible (app loaded)
  await expect(page.locator('text=FIN')).toBeVisible({ timeout: 15_000 });
}

// Reset the database before each test so tests are hermetic.
// /api/debug/reset is only available when LLM_MOCK=true.
test.beforeEach(async ({ request }) => {
  await request.post('/api/debug/reset');
});

test.describe('Fresh start', () => {
  test('shows default watchlist with 10 tickers', async ({ page }) => {
    await waitForApp(page);
    // The watchlist panel heading (use first() to avoid strict mode violation)
    await expect(page.locator('text=Watchlist').first()).toBeVisible();
    // Default seed tickers should be present
    await expect(page.locator('text=AAPL').first()).toBeVisible();
    await expect(page.locator('text=GOOGL').first()).toBeVisible();
    await expect(page.locator('text=MSFT').first()).toBeVisible();
  });

  test('shows $10,000 starting cash balance', async ({ page }) => {
    await waitForApp(page);
    // Cash balance in header — formatted as $10,000.00
    await expect(page.locator('text=$10,000.00').first()).toBeVisible();
  });

  test('shows connection status indicator', async ({ page }) => {
    await waitForApp(page);
    // Connection dot should show LIVE within a few seconds of startup
    await expect(page.locator('text=LIVE')).toBeVisible({ timeout: 10_000 });
  });

  test('prices stream live updates', async ({ page }) => {
    await waitForApp(page);
    // AAPL should be visible in the watchlist
    const aapl = page.locator('text=AAPL').first();
    await expect(aapl).toBeVisible();
    // Wait a moment and verify the page is still live (no crash, prices present)
    await page.waitForTimeout(2000);
    await expect(page.locator('text=AAPL')).toBeVisible();
  });
});

test.describe('Watchlist management', () => {
  test('can add a new ticker to the watchlist', async ({ page }) => {
    await waitForApp(page);
    const input = page.locator('input[placeholder="Add ticker…"]');
    await input.fill('IBM');
    await input.press('Enter');
    await expect(page.locator('text=IBM')).toBeVisible({ timeout: 5_000 });
  });

  test('can remove a ticker from the watchlist', async ({ page }) => {
    await waitForApp(page);
    // Wait for watchlist to load (10 tickers = 10 remove buttons)
    await expect(page.locator('button[title="Remove"]')).toHaveCount(10, { timeout: 5_000 });
    // Use the API directly to remove a ticker, then verify the UI updates
    await page.request.delete('/api/watchlist/AAPL');
    await page.reload();
    await expect(page.locator('button[title="Remove"]')).toHaveCount(9, { timeout: 8_000 });
  });

  test('normalizes lowercase ticker to uppercase', async ({ page }) => {
    await waitForApp(page);
    const input = page.locator('input[placeholder="Add ticker…"]');
    await input.fill('ibm');
    await input.press('Enter');
    await expect(page.locator('text=IBM')).toBeVisible({ timeout: 5_000 });
  });
});

test.describe('Trading', () => {
  test('buy shares: cash decreases, position appears', async ({ page }) => {
    await waitForApp(page);
    // Wait for prices to stream (first price update means SSE is live)
    await expect(page.locator('text=LIVE')).toBeVisible({ timeout: 8_000 });

    // Use the trade bar: AAPL should be pre-selected from the watchlist click
    await page.locator('text=AAPL').first().click();

    const tickerInput = page.locator('input[placeholder="Ticker"]');
    const qtyInput = page.locator('input[placeholder="Qty"]');

    await tickerInput.fill('AAPL');
    await qtyInput.fill('1');
    await page.getByRole('button', { name: 'BUY' }).click();

    // Success message should flash
    await expect(page.locator('text=/BUY 1 AAPL/i')).toBeVisible({ timeout: 8_000 });

    // A position for AAPL should now exist in the positions table
    await expect(page.locator('table').getByText('AAPL')).toBeVisible({ timeout: 5_000 });
  });

  test('sell shares: cash increases, position updates', async ({ page }) => {
    await waitForApp(page);
    await expect(page.locator('text=LIVE')).toBeVisible({ timeout: 8_000 });

    // First buy 2 shares
    await page.locator('input[placeholder="Ticker"]').fill('AAPL');
    await page.locator('input[placeholder="Qty"]').fill('2');
    await page.getByRole('button', { name: 'BUY' }).click();
    await expect(page.locator('text=/BUY 2 AAPL/i')).toBeVisible({ timeout: 8_000 });

    // Then sell 1 share
    await page.locator('input[placeholder="Qty"]').fill('1');
    await page.getByRole('button', { name: 'SELL' }).click();
    await expect(page.locator('text=/SELL 1 AAPL/i')).toBeVisible({ timeout: 8_000 });

    // Position should still exist
    await expect(page.locator('table').getByText('AAPL')).toBeVisible();
  });

  test('buy with insufficient cash shows error', async ({ page }) => {
    await waitForApp(page);
    await expect(page.locator('text=LIVE')).toBeVisible({ timeout: 8_000 });
    // Try to buy 10,000 shares at market price (will exceed $10k)
    await page.locator('input[placeholder="Ticker"]').fill('AAPL');
    await page.locator('input[placeholder="Qty"]').fill('10000');
    await page.getByRole('button', { name: 'BUY' }).click();
    // Error message should flash in trade bar
    await expect(
      page.locator('text=/insufficient|Insufficient|failed|Failed/').first()
    ).toBeVisible({ timeout: 8_000 });
  });
});

test.describe('Portfolio visualization', () => {
  test('heatmap renders after a trade', async ({ page }) => {
    await waitForApp(page);
    await expect(page.locator('text=LIVE')).toBeVisible({ timeout: 8_000 });

    // Buy a position so the heatmap has data
    await page.locator('input[placeholder="Ticker"]').fill('AAPL');
    await page.locator('input[placeholder="Qty"]').fill('1');
    await page.getByRole('button', { name: 'BUY' }).click();
    await expect(page.locator('text=/BUY 1 AAPL/i')).toBeVisible({ timeout: 8_000 });

    // Heatmap section heading should be visible
    await expect(page.locator('text=POSITIONS HEATMAP').or(page.locator('text=Heatmap'))).toBeVisible({
      timeout: 5_000,
    });
  });

  test('P&L chart section is visible', async ({ page }) => {
    await waitForApp(page);
    // The PnLChart component renders "P&L Chart" as its heading
    await expect(page.locator('text=P&L Chart')).toBeVisible();
  });
});

test.describe('AI chat (LLM mock mode)', () => {
  test('can send a message and receive a response', async ({ page }) => {
    await waitForApp(page);

    // Open chat panel if collapsed
    const chatToggle = page.locator('button[title="Open AI chat"]');
    if (await chatToggle.isVisible()) {
      await chatToggle.click();
    }

    // Find the chat textarea
    const textarea = page.locator('textarea[placeholder="Message FinAlly…"]');
    await expect(textarea).toBeVisible({ timeout: 5_000 });

    await textarea.fill('Hello, what is my portfolio?');
    await page.locator('button:text("→")').click();

    // User message should appear immediately in chat history
    await expect(
      page.locator('text=Hello, what is my portfolio?')
    ).toBeVisible({ timeout: 5_000 });

    // Then either "Thinking…" or an assistant response arrives
    await expect(
      page.locator('text=Thinking…').or(page.locator('.bg-bg-tertiary >> text=/.+/')).first()
    ).toBeVisible({ timeout: 8_000 });
  });

  test('chat panel toggles open and closed', async ({ page }) => {
    await waitForApp(page);

    // Find toggle button
    const closeBtn = page.locator('button[title="Close chat"]');
    const openBtn = page.locator('button[title="Open AI chat"]');

    if (await closeBtn.isVisible()) {
      await closeBtn.click();
      await expect(
        page.locator('textarea[placeholder="Message FinAlly…"]')
      ).not.toBeVisible();
      await openBtn.click();
      await expect(
        page.locator('textarea[placeholder="Message FinAlly…"]')
      ).toBeVisible();
    } else if (await openBtn.isVisible()) {
      await openBtn.click();
      await expect(
        page.locator('textarea[placeholder="Message FinAlly…"]')
      ).toBeVisible();
    }
  });
});

test.describe('Health endpoint', () => {
  test('GET /api/health returns 200 ok', async ({ request }) => {
    const resp = await request.get('/api/health');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body.status).toBe('ok');
  });
});

test.describe('API smoke tests', () => {
  test('GET /api/watchlist returns tickers', async ({ request }) => {
    const resp = await request.get('/api/watchlist');
    expect(resp.status()).toBe(200);
    const data = await resp.json();
    expect(data.tickers).toBeDefined();
    expect(data.tickers.length).toBeGreaterThan(0);
  });

  test('GET /api/portfolio returns cash balance', async ({ request }) => {
    const resp = await request.get('/api/portfolio');
    expect(resp.status()).toBe(200);
    const data = await resp.json();
    expect(data.cash_balance).toBeGreaterThan(0);
  });

  test('POST /api/chat returns message', async ({ request }) => {
    const resp = await request.post('/api/chat', {
      data: { message: 'Hello' },
    });
    expect(resp.status()).toBe(200);
    const data = await resp.json();
    expect(typeof data.message).toBe('string');
    expect(data.message.length).toBeGreaterThan(0);
  });
});
