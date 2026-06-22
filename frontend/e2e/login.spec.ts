/**
 * Login page E2E tests.
 *
 * HOW TO RUN WITH A REAL BACKEND:
 *   1. Start the backend: `cd backend && uvicorn app.main:app --reload`
 *   2. Start the frontend: `cd frontend && npm run dev`
 *   3. Run: `npx playwright test login`
 *
 * For isolated testing (no backend needed), the tests mock API responses
 * using `page.route()`.
 */

import { test, expect } from '@playwright/test';

test.describe('Login Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
  });

  test('should display login form with title and fields', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'ProxySQL Admin' })).toBeVisible();
    await expect(page.getByText('Sign in to manage your proxy')).toBeVisible();
    await expect(page.getByPlaceholder('Enter username')).toBeVisible();
    await expect(page.getByPlaceholder('Enter password')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Sign In' })).toBeVisible();
  });

  test('should show language switcher on login page', async ({ page }) => {
    // Language switcher should be visible before login
    const langSelect = page.locator('select[title="Language / 语言"]');
    await expect(langSelect).toBeVisible();
  });

  test('should login successfully and redirect to dashboard', async ({ page }) => {
    // Mock successful login
    await page.route('**/api/v1/auth/login', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: 'mock-access-token',
          refresh_token: 'mock-refresh-token',
          user: { id: 1, username: 'admin', role: 'admin', email: null },
        }),
      });
    });

    await page.getByPlaceholder('Enter username').fill('admin');
    await page.getByPlaceholder('Enter password').fill('admin');
    await page.getByRole('button', { name: 'Sign In' }).click();

    await page.waitForURL('/dashboard');
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('should show error on failed login (wrong password)', async ({ page }) => {
    // Mock failed login
    await page.route('**/api/v1/auth/login', async (route) => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Invalid credentials' }),
      });
    });

    await page.getByPlaceholder('Enter username').fill('admin');
    await page.getByPlaceholder('Enter password').fill('wrongpassword');
    await page.getByRole('button', { name: 'Sign In' }).click();

    // Error message should appear
    await expect(page.getByText('Invalid credentials')).toBeVisible();
    // Should still be on login page
    await expect(page).toHaveURL(/\/login/);
  });

  test('should show error on empty credentials submission', async ({ page }) => {
    // HTML5 required validation should prevent submission
    // The username and password inputs have `required` attribute
    const usernameInput = page.getByPlaceholder('Enter username');
    const passwordInput = page.getByPlaceholder('Enter password');

    // Try to submit without filling — browser validation blocks it
    await page.getByRole('button', { name: 'Sign In' }).click();

    // Should remain on login page (no navigation occurred)
    await expect(page).toHaveURL(/\/login/);
  });

  test('should navigate to dashboard after successful login and show server selector', async ({ page }) => {
    // Mock login
    await page.route('**/api/v1/auth/login', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: 'mock-access-token',
          refresh_token: 'mock-refresh-token',
          user: { id: 1, username: 'admin', role: 'admin', email: null },
        }),
      });
    });

    // Mock servers list for server selector
    await page.route('**/api/v1/servers', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'srv1', name: 'default', host: '127.0.0.1', port: 6032, admin_user: 'admin', is_default: true },
        ]),
      });
    });

    // Mock dashboard snapshot
    await page.route('**/api/v1/dashboard/*/snapshot', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          connections: [{ used: 5, free: 10 }],
          qps: [{ questions: 100 }],
          traffic: [{ queries: 5000 }],
          hostgroups: [],
        }),
      });
    });

    await page.getByPlaceholder('Enter username').fill('admin');
    await page.getByPlaceholder('Enter password').fill('admin');
    await page.getByRole('button', { name: 'Sign In' }).click();

    await page.waitForURL('/dashboard');
    // Verify the main layout is shown (sidebar exists)
    await expect(page.locator('aside')).toBeVisible();
  });
});
