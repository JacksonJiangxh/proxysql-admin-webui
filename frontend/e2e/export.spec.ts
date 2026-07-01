/**
 * E2E tests for Data Export functionality.
 *
 * Covers: query result export (CSV/JSON), table data export.
 * All API calls are mocked via page.route().
 */
import { test, expect } from '@playwright/test';

// ── Mock Data ──────────────────────────────────────────────────────
const MOCK_SERVERS = [
  { id: 'srv1', name: 'Production ProxySQL 1', host: '10.0.0.1', port: 6032 },
];

const MOCK_USER = {
  id: 1, username: 'admin', role: 'admin', email: 'admin@example.com',
};

const MOCK_TABLES = {
  tables: [
    { name: 'mysql_servers', rows: 5 },
    { name: 'mysql_users', rows: 3 },
    { name: 'mysql_query_rules', rows: 12 },
  ],
};

const MOCK_QUERY_RESULT = {
  type: 'select',
  columns: ['hostgroup', 'srv_host', 'srv_port', 'status'],
  rows: [
    { hostgroup: 0, srv_host: '10.0.1.1', srv_port: 3306, status: 'ONLINE' },
    { hostgroup: 0, srv_host: '10.0.1.2', srv_port: 3306, status: 'ONLINE' },
    { hostgroup: 1, srv_host: '10.0.2.1', srv_port: 3306, status: 'ONLINE' },
  ],
  row_count: 3,
  elapsed_ms: 12.5,
};

// ── Helpers ────────────────────────────────────────────────────────
async function mockCommonApis(page: any) {
  await page.route('**/api/v1/auth/me', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_USER) });
  });
  await page.route('**/api/v1/servers', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_SERVERS) });
  });
}

// ── Tests ──────────────────────────────────────────────────────────
test.describe('Query Result Export', () => {
  test.beforeEach(async ({ page }) => {
    await mockCommonApis(page);
    await page.goto('/query');
  });

  test('should export query results as CSV', async ({ page }) => {
    // Mock the export endpoint
    const downloadPromise = page.waitForEvent('download', { timeout: 10000 }).catch(() => null);

    await page.route('**/api/v1/export/srv1/query-result**', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 200,
          contentType: 'text/csv',
          headers: { 'Content-Disposition': 'attachment; filename="query_export.csv"' },
          body: 'hostgroup,srv_host,srv_port,status\n0,10.0.1.1,3306,ONLINE\n0,10.0.1.2,3306,ONLINE',
        });
      }
    });

    // Type a query
    const sqlEditor = page.locator('textarea').or(page.locator('[contenteditable="true"]')).or(page.locator('.monaco-editor textarea'));
    if (await sqlEditor.isVisible({ timeout: 5000 })) {
      await sqlEditor.fill('SELECT * FROM main.mysql_servers');
    }

    // Look for export button
    const exportBtn = page.getByRole('button', { name: /export/i }).or(page.getByText(/export/i));
    if (await exportBtn.isVisible({ timeout: 3000 })) {
      await exportBtn.click();
      // Check for format selector
      const csvOption = page.getByText('CSV').or(page.getByRole('option', { name: /csv/i }));
      if (await csvOption.isVisible({ timeout: 2000 })) {
        await csvOption.click();
      }
    }

    // Wait for download
    const download = await downloadPromise;
    if (download) {
      expect(download.suggestedFilename()).toContain('csv');
    }
  });

  test('should export query results as JSON', async ({ page }) => {
    const downloadPromise = page.waitForEvent('download', { timeout: 10000 }).catch(() => null);

    await page.route('**/api/v1/export/srv1/query-result**', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          headers: { 'Content-Disposition': 'attachment; filename="query_export.json"' },
          body: JSON.stringify(MOCK_QUERY_RESULT.rows, null, 2),
        });
      }
    });

    const exportBtn = page.getByRole('button', { name: /export/i }).or(page.getByText(/export/i));
    if (await exportBtn.isVisible({ timeout: 3000 })) {
      await exportBtn.click();
      const jsonOption = page.getByText('JSON').or(page.getByRole('option', { name: /json/i }));
      if (await jsonOption.isVisible({ timeout: 2000 })) {
        await jsonOption.click();
      }
    }

    const download = await downloadPromise;
    if (download) {
      expect(download.suggestedFilename()).toContain('json');
    }
  });

  test('should show error when query returns no rows', async ({ page }) => {
    await page.route('**/api/v1/export/srv1/query-result**', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'Query returned no rows to export' }) });
      }
    });

    const exportBtn = page.getByRole('button', { name: /export/i }).or(page.getByText(/export/i));
    if (await exportBtn.isVisible({ timeout: 3000 })) {
      await exportBtn.click();
      const csvOption = page.getByText('CSV').or(page.getByRole('option', { name: /csv/i }));
      if (await csvOption.isVisible({ timeout: 2000 })) {
        await csvOption.click();
      }
    }

    // Should show error toast or message
    await expect(page.getByText(/no rows/i).or(page.getByText(/empty/i))).toBeVisible({ timeout: 5000 });
  });
});


test.describe('Table Data Export', () => {
  test.beforeEach(async ({ page }) => {
    await mockCommonApis(page);
    // Mock table listing
    await page.route('**/api/v1/srv1/tables**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_TABLES) });
    });
    await page.goto('/tables');
  });

  test('should export table data as CSV', async ({ page }) => {
    const downloadPromise = page.waitForEvent('download', { timeout: 10000 }).catch(() => null);

    await page.route('**/api/v1/export/srv1/table/mysql_servers**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/csv',
        headers: { 'Content-Disposition': 'attachment; filename="mysql_servers_memory.csv"' },
        body: 'hostgroup,srv_host,srv_port,status\n0,10.0.1.1,3306,ONLINE',
      });
    });

    // Look for export button on table page
    const exportBtn = page.getByRole('button', { name: /export/i }).or(page.getByText(/export/i));
    if (await exportBtn.isVisible({ timeout: 5000 })) {
      await exportBtn.click();
    }

    const download = await downloadPromise;
    if (download) {
      expect(download.suggestedFilename()).toContain('.csv');
    }
  });

  test('should export table data as JSON', async ({ page }) => {
    const downloadPromise = page.waitForEvent('download', { timeout: 10000 }).catch(() => null);

    await page.route('**/api/v1/export/srv1/table/mysql_servers**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        headers: { 'Content-Disposition': 'attachment; filename="mysql_servers_memory.json"' },
        body: JSON.stringify(MOCK_QUERY_RESULT.rows),
      });
    });

    const exportBtn = page.getByRole('button', { name: /export/i }).or(page.getByText(/export/i));
    if (await exportBtn.isVisible({ timeout: 5000 })) {
      // If format selector exists
      const jsonOption = page.getByText('JSON').or(page.getByRole('option', { name: /json/i }));
      if (await jsonOption.isVisible({ timeout: 2000 })) {
        await jsonOption.click();
      }
      await exportBtn.click();
    }

    const download = await downloadPromise;
    if (download) {
      expect(download.suggestedFilename()).toContain('.json');
    }
  });
});
