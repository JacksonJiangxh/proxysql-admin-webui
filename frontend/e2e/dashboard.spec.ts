/**
 * Dashboard page E2E tests.
 *
 * HOW TO RUN WITH A REAL BACKEND:
 *   1. Start the backend: `cd backend && uvicorn app.main:app --reload`
 *   2. Start the frontend: `cd frontend && npm run dev`
 *   3. Run: `npx playwright test dashboard`
 */

import { test, expect } from '@playwright/test';

const MOCK_SERVERS = [
  { id: 'srv1', name: 'default', host: '127.0.0.1', port: 6032, admin_user: 'admin', is_default: true },
];

const MOCK_SNAPSHOT = {
  connections: [{ used: 42, free: 58 }],
  qps: [{ questions: 1234 }],
  traffic: [{ queries: 98765 }],
  hostgroups: [
    { hostgroup: 0, srv_host: '10.0.0.1', srv_port: 3306, status: 'ONLINE', ConnUsed: 5, ConnFree: 10 },
    { hostgroup: 1, srv_host: '10.0.0.2', srv_port: 3306, status: 'ONLINE', ConnUsed: 3, ConnFree: 7 },
  ],
};

test.describe('Dashboard Page', () => {
  test.beforeEach(async ({ page }) => {
    // Mock common APIs
    await page.route('**/api/v1/servers', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_SERVERS),
      });
    });

    await page.route('**/api/v1/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 1, username: 'admin', role: 'admin', email: null }),
      });
    });

    await page.route('**/api/v1/dashboard/srv1/snapshot', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_SNAPSHOT),
      });
    });
  });

  test('should load dashboard with metric cards', async ({ page }) => {
    await page.goto('/dashboard');

    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();

    // Verify metric cards
    await expect(page.getByText('Active Connections')).toBeVisible();
    await expect(page.getByText('Free Connections')).toBeVisible();
    await expect(page.getByText('Total Queries')).toBeVisible();
    await expect(page.getByText('QPS')).toBeVisible();

    // Verify metric values from mock data
    await expect(page.getByText('42').first()).toBeVisible(); // Active Connections
    await expect(page.getByText('1234').first()).toBeVisible(); // QPS
  });

  test('should display connection pool table', async ({ page }) => {
    await page.goto('/dashboard');

    await expect(page.getByText('Connection Pool Status')).toBeVisible();

    // Table headers
    await expect(page.getByText('Hostgroup')).toBeVisible();
    await expect(page.getByText('Host')).toBeVisible();
    await expect(page.getByText('Port')).toBeVisible();

    // Data rows from mock
    await expect(page.getByText('10.0.0.1')).toBeVisible();
    await expect(page.getByText('ONLINE').first()).toBeVisible();
  });

  test('should show server selector in top bar', async ({ page }) => {
    await page.goto('/dashboard');

    // Server selector dropdown should be visible
    const serverSelect = page.locator('select[title="Select ProxySQL instance"]');
    await expect(serverSelect).toBeVisible();
    await expect(serverSelect).toHaveValue('srv1');
  });

  test('should show no server selected warning when no server is configured', async ({ page }) => {
    // Override servers mock to return empty
    await page.route('**/api/v1/servers', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    await page.goto('/dashboard');

    // Warning about no server selected should appear
    await expect(page.getByText('No ProxySQL server selected')).toBeVisible();
  });

  test('should update data when server selector changes', async ({ page }) => {
    // Add a second server
    const twoServers = [
      { id: 'srv1', name: 'default', host: '127.0.0.1', port: 6032, admin_user: 'admin', is_default: true },
      { id: 'srv2', name: 'secondary', host: '192.168.1.1', port: 6032, admin_user: 'admin', is_default: false },
    ];

    await page.route('**/api/v1/servers', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(twoServers),
      });
    });

    const snapshot2 = {
      connections: [{ used: 10, free: 20 }],
      qps: [{ questions: 567 }],
      traffic: [{ queries: 3000 }],
      hostgroups: [],
    };

    await page.route('**/api/v1/dashboard/srv2/snapshot', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(snapshot2),
      });
    });

    await page.goto('/dashboard');

    // Select second server
    const serverSelect = page.locator('select[title="Select ProxySQL instance"]');
    await serverSelect.selectOption('srv2');

    // Dashboard data should update to reflect the second server's data
    await expect(page.getByText('10').first()).toBeVisible(); // Active Connections for srv2
  });

  test('should show loading spinner while fetching data', async ({ page }) => {
    // Delay the snapshot response to see loading state
    await page.route('**/api/v1/dashboard/srv1/snapshot', async (route) => {
      await new Promise(resolve => setTimeout(resolve, 2000));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_SNAPSHOT),
      });
    });

    await page.goto('/dashboard');

    // Loading spinner should appear
    const spinner = page.locator('.animate-spin');
    await expect(spinner).toBeVisible({ timeout: 1000 });
  });
});
