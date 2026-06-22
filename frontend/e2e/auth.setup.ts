/**
 * Authentication setup for E2E tests.
 *
 * This file runs before all authenticated tests. It logs in via the UI
 * and saves the browser storage state (cookies, localStorage) so that
 * subsequent tests start already authenticated.
 *
 * HOW TO RUN WITH A REAL BACKEND:
 *   1. Start the backend: `cd backend && uvicorn app.main:app --reload`
 *   2. Start the frontend: `cd frontend && npm run dev`
 *   3. Run tests: `npx playwright test`
 *
 * The login credentials below should match the backend's seeded test user.
 * If your backend uses different credentials, update them here.
 */

import { test as setup, expect } from '@playwright/test';

const AUTH_FILE = './e2e/.auth/user.json';

setup('authenticate', async ({ page }) => {
  // Mock the login API response for isolated testing
  await page.route('**/api/v1/auth/login', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'mock-access-token-e2e',
        refresh_token: 'mock-refresh-token-e2e',
        user: {
          id: 1,
          username: 'admin',
          role: 'admin',
          email: null,
        },
      }),
    });
  });

  await page.goto('/login');

  await page.getByPlaceholder('Enter username').fill('admin');
  await page.getByPlaceholder('Enter password').fill('admin');

  await page.getByRole('button', { name: 'Sign In' }).click();

  // Wait for navigation to dashboard after successful login
  await page.waitForURL('/dashboard');

  // Save storage state (includes localStorage tokens)
  await page.context().storageState({ path: AUTH_FILE });
});
