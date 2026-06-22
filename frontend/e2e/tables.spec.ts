/**
 * Table Browser page E2E tests.
 *
 * HOW TO RUN WITH A REAL BACKEND:
 *   1. Start the backend: `cd backend && uvicorn app.main:app --reload`
 *   2. Start the frontend: `cd frontend && npm run dev`
 *   3. Run: `npx playwright test tables`
 */

import { test, expect } from '@playwright/test';

const MOCK_SERVERS = [
  { id: 'srv1', name: 'default', host: '127.0.0.1', port: 6032, admin_user: 'admin', is_default: true },
];

const MOCK_TABLES = [
  'mysql_servers',
  'mysql_users',
  'mysql_query_rules',
  'scheduler',
  'global_variables',
];

const MOCK_TABLE_DATA = {
  column_names: ['hostgroup_id', 'hostname', 'port', 'status', 'weight'],
  rows: [
    { hostgroup_id: 0, hostname: '10.0.0.1', port: 3306, status: 'ONLINE', weight: 1 },
    { hostgroup_id: 0, hostname: '10.0.0.2', port: 3306, status: 'ONLINE', weight: 1 },
    { hostgroup_id: 1, hostname: '10.0.0.3', port: 3306, status: 'SHUNNED', weight: 1000 },
  ],
};

test.describe('Table Browser Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/servers', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_SERVERS) });
    });
    await page.route('**/api/v1/auth/me', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 1, username: 'admin', role: 'admin', email: null }) });
    });
    await page.route('**/api/v1/srv1/tables', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ tables: MOCK_TABLES }) });
    });
  });

  test('should load table browser with table list', async ({ page }) => {
    await page.goto('/tables');

    await expect(page.getByRole('heading', { name: 'Table Browser' })).toBeVisible();

    // Table list panel
    await expect(page.getByText('mysql_servers')).toBeVisible();
    await expect(page.getByText('mysql_users')).toBeVisible();
    await expect(page.getByText('scheduler')).toBeVisible();
  });

  test('should show "Select a table" prompt when no table is selected', async ({ page }) => {
    await page.goto('/tables');

    await expect(page.getByText('Select a table from the left panel')).toBeVisible();
  });

  test('should display table data when a table is selected', async ({ page }) => {
    await page.route('**/api/v1/srv1/tables/mysql_servers**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_TABLE_DATA) });
    });

    await page.goto('/tables');

    // Click on a table
    await page.getByText('mysql_servers').click();

    // Table data view should appear
    await expect(page.getByText('mysql_servers').locator('..').filter({ hasText: '3 rows' })).toBeVisible();

    // Column headers
    await expect(page.getByText('hostgroup_id')).toBeVisible();
    await expect(page.getByText('hostname')).toBeVisible();

    // Data cells
    await expect(page.getByText('10.0.0.1')).toBeVisible();
    await expect(page.getByText('ONLINE').first()).toBeVisible();
  });

  test('should highlight selected table in the list', async ({ page }) => {
    await page.route('**/api/v1/srv1/tables/mysql_servers**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_TABLE_DATA) });
    });

    await page.goto('/tables');

    await page.getByText('mysql_servers').click();

    // Selected table should have active styling (blue background class)
    const selectedButton = page.locator('button').filter({ hasText: 'mysql_servers' });
    await expect(selectedButton).toHaveClass(/bg-blue-50/);
  });

  test('should show empty data message for tables with no rows', async ({ page }) => {
    await page.route('**/api/v1/srv1/tables/scheduler**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ column_names: ['id', 'active', 'interval_ms'], rows: [] }),
      });
    });

    await page.goto('/tables');

    await page.getByText('scheduler').click();
    await expect(page.getByText('No data')).toBeVisible();
  });

  test('should show no server selected warning', async ({ page }) => {
    await page.route('**/api/v1/servers', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });

    await page.goto('/tables');

    await expect(page.getByText('No ProxySQL server selected')).toBeVisible();
  });

  test('should display NULL values correctly', async ({ page }) => {
    const dataWithNulls = {
      column_names: ['hostgroup_id', 'hostname', 'comment'],
      rows: [
        { hostgroup_id: 0, hostname: '10.0.0.1', comment: null },
      ],
    };

    await page.route('**/api/v1/srv1/tables/mysql_servers**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(dataWithNulls) });
    });

    await page.goto('/tables');
    await page.getByText('mysql_servers').click();

    // NULL should be displayed as italic text
    await expect(page.getByText('NULL').first()).toBeVisible();
  });
});
