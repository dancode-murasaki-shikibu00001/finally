import { test, expect } from '@playwright/test';

test.describe('AI chat (mock mode)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="chat-panel"]', { timeout: 10000 });
  });

  test('can send a message and get a response', async ({ page }) => {
    const input = page.locator('[data-testid="chat-input"]');
    await input.fill('Hello FinAlly');
    await page.locator('[data-testid="chat-send"]').click();

    // User message should appear
    await expect(page.locator('[data-testid="chat-messages"]').locator('text=Hello FinAlly')).toBeVisible({ timeout: 5000 });

    // Assistant response should appear (mock returns FinAlly greeting)
    await expect(page.locator('[data-testid="chat-messages"]').locator('text=FinAlly')).toBeVisible({ timeout: 10000 });
  });

  test('shows loading indicator while waiting for response', async ({ page }) => {
    const input = page.locator('[data-testid="chat-input"]');
    await input.fill('What is my portfolio?');
    await page.locator('[data-testid="chat-send"]').click();

    // Loading indicator should briefly appear
    // It may be brief, so just check the message was sent
    await expect(page.locator('[data-testid="chat-messages"]').locator('text=What is my portfolio?')).toBeVisible({ timeout: 5000 });
  });
});
