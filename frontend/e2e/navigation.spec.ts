/**
 * Navigation E2E tests.
 *
 * HOW TO RUN WITH A REAL BACKEND:
 *   1. Start the backend: `cd backend && uvicorn app.main:app --reload`
 *   2. Start the frontend: `cd frontend && npm run dev`
 *   3. Run: `npx playwright test navigation`
 *
 * These tests use the authenticated storage state (from auth.setup.ts).
 * API responses are mocked via `page.route()` for isolated testing.
 */

import { test, expect } from '@playwright/test';

// Mock common API endpoints used across all pages
async function mockCommonApis(page: any) {
  await page.route('**/api/v1/servers', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { id: 'srv1', name: 'default', host: '127.0.0.1', port: 6032, admin_user: 'admin', is_default: true },
      ]),
    });
  });

  await page.route('**/api/v1/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ id: 1, username: 'admin', role: 'admin', email: null }),
    });
  });
}

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await mockCommonApis(page);
    await page.goto('/dashboard');
  });

  test('should display sidebar with all navigation items', async ({ page }) => {
    const sidebar = page.locator('aside');
    await expect(sidebar).toBeVisible();

    // Verify all nav items are present
    const navItems = [
      'Dashboard', 'Wizards', 'Table Browser', 'SQL Console',
      'Config Sync', 'Config Diff', 'Servers', 'Clusters',
      'Users', 'Settings',
    ];

    for (const item of navItems) {
      await expect(sidebar.getByText(item)).toBeVisible();
    }
  });

  test('should navigate to each page via sidebar', async ({ page }) => {
    // Mock dashboard data
    await page.route('**/api/v1/dashboard/*/snapshot', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ connections: [{ used: 5, free: 10 }], qps: [{ questions: 100 }], traffic: [{ queries: 5000 }], hostgroups: [] }),
      });
    });

    const navLinks = [
      { label: 'Wizards', path: '/wizards' },
      { label: 'Table Browser', path: '/tables' },
      { label: 'SQL Console', path: '/query' },
      { label: 'Config Sync', path: '/sync' },
      { label: 'Config Diff', path: '/config-diff' },
      { label: 'Servers', path: '/servers' },
      { label: 'Clusters', path: '/clusters' },
      { label: 'Users', path: '/users' },
      { label: 'Settings', path: '/settings' },
    ];

    for (const nav of navLinks) {
      // Mock specific page APIs
      await page.route(`**/api/v1/wizards/definitions`, async (route) => {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ wizards: [] }) });
      });
      await page.route(`**/api/v1/*/tables`, async (route) => {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ tables: [] }) });
      });
      await page.route(`**/api/v1/sync/*/status`, async (route) => {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ tables: [] }) });
      });
      await page.route(`**/api/v1/config-diff/*`, async (route) => {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ tables: [] }) });
      });
      await page.route(`**/api/v1/users`, async (route) => {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
      });
      await page.route(`**/api/v1/settings/info`, async (route) => {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ version: '1.0', user_count: 1, server_count: 1, audit_log_count: 0 }) });
      });
      await page.route(`**/api/v1/settings/audit-logs**`, async (route) => {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ logs: [] }) });
      });
      await page.route(`**/api/v1/clusters`, async (route) => {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
      });

      await page.locator('aside').getByText(nav.label).click();
      await expect(page).toHaveURL(new RegExp(nav.path));
    }
  });

  test('should collapse and expand sidebar', async ({ page }) => {
    const sidebar = page.locator('aside');

    // Initially sidebar is open (width 64)
    await expect(sidebar).toHaveClass(/w-64/);

    // Click collapse button
    await page.locator('aside button').filter({ has: page.locator('svg') }).first().click();

    // Sidebar should be collapsed (width 16)
    await expect(sidebar).toHaveClass(/w-16/);

    // Title should be hidden
    await expect(sidebar.getByText('ProxySQL Admin')).not.toBeVisible();

    // Nav labels should be hidden
    await expect(sidebar.getByText('Dashboard').locator('..').locator('span')).not.toBeVisible();

    // Click expand button to reopen
    await page.locator('aside button').filter({ has: page.locator('svg') }).first().click();
    await expect(sidebar).toHaveClass(/w-64/);
  });

  test('should switch language and update UI labels', async ({ page }) => {
    // Mock dashboard
    await page.route('**/api/v1/dashboard/*/snapshot', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ connections: [{ used: 5, free: 10 }], qps: [{ questions: 100 }], traffic: [{ queries: 5000 }], hostgroups: [] }),
      });
    });

    // Find the language switcher in the top bar
    const langSelect = page.locator('select[title="Language / 语言"]');

    // Default should be English — "Dashboard" in sidebar
    await expect(page.locator('aside').getByText('Dashboard')).toBeVisible();

    // Switch to Chinese
    await langSelect.selectOption('zh-CN');

    // "仪表盘" should now appear (Chinese translation of Dashboard)
    await expect(page.locator('aside').getByText('仪表盘')).toBeVisible();

    // Switch back to English
    await langSelect.selectOption('en-US');
    await expect(page.locator('aside').getByText('Dashboard')).toBeVisible();
  });

  test('should logout and redirect to login page', async ({ page }) => {
    // Click logout button in sidebar
    await page.locator('aside').getByText('Logout').click();

    // Should redirect to login page
    await expect(page).toHaveURL(/\/login/);

    // localStorage tokens should be cleared
    const tokens = await page.evaluate(() => localStorage.getItem('access_token'));
    expect(tokens).toBeNull();
  });

  test('should show username and role in sidebar', async ({ page }) => {
    await expect(page.locator('aside').getByText('admin')).toBeVisible();
    await expect(page.locator('aside').getByText('admin').locator('..').getByText('admin')).toBeVisible();
  });
});
