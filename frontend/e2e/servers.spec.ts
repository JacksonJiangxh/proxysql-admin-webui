/**
 * Servers page E2E tests.
 *
 * HOW TO RUN WITH A REAL BACKEND:
 *   1. Start the backend: `cd backend && uvicorn app.main:app --reload`
 *   2. Start the frontend: `cd frontend && npm run dev`
 *   3. Run: `npx playwright test servers`
 */

import { test, expect } from '@playwright/test';

const MOCK_SERVERS = [
  { id: 'srv1', name: 'default', host: '127.0.0.1', port: 6032, admin_user: 'admin', is_default: true },
  { id: 'srv2', name: 'secondary', host: '192.168.1.1', port: 6032, admin_user: 'admin', is_default: false },
];

test.describe('Servers Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/servers', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_SERVERS) });
    });
    await page.route('**/api/v1/auth/me', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 1, username: 'admin', role: 'admin', email: null }) });
    });
  });

  test('should load server list with existing servers', async ({ page }) => {
    await page.goto('/servers');

    await expect(page.getByRole('heading', { name: 'Servers' })).toBeVisible();

    // Server rows in the table
    await expect(page.getByText('default')).toBeVisible();
    await expect(page.getByText('127.0.0.1:6032')).toBeVisible();
    await expect(page.getByText('secondary')).toBeVisible();
    await expect(page.getByText('192.168.1.1:6032')).toBeVisible();

    // Default server indicator
    // CheckCircle icon for default server
    const defaultIcon = page.locator('svg.inline.text-green-500');
    await expect(defaultIcon).toBeVisible();

    // Action buttons
    await expect(page.getByText('Use').first()).toBeVisible();
    await expect(page.getByText('Test').first()).toBeVisible();
  });

  test('should show empty state when no servers exist', async ({ page }) => {
    await page.route('**/api/v1/servers', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });

    await page.goto('/servers');

    await expect(page.getByText('No servers configured')).toBeVisible();
  });

  test('should open add server form when clicking Add Server button', async ({ page }) => {
    await page.goto('/servers');

    await page.getByText('Add Server').click();

    // Create form should appear
    await expect(page.getByPlaceholder('Server Name')).toBeVisible();
    await expect(page.getByPlaceholder('Host')).toBeVisible();
    await expect(page.getByPlaceholder('Port')).toBeVisible();
    await expect(page.getByPlaceholder('Admin User')).toBeVisible();
    await expect(page.getByPlaceholder('Admin Password')).toBeVisible();
    await expect(page.getByText('Add').first()).toBeVisible();
    await expect(page.getByText('Cancel').first()).toBeVisible();
  });

  test('should add a new server', async ({ page }) => {
    const newServer = { id: 'srv3', name: 'new-server', host: '10.0.0.5', port: 6032, admin_user: 'admin', is_default: false };

    await page.route('**/api/v1/servers', async (route) => {
      const method = route.request().method();
      if (method === 'POST') {
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify(newServer),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([...MOCK_SERVERS, newServer]),
        });
      }
    });

    await page.goto('/servers');

    await page.getByText('Add Server').click();

    await page.getByPlaceholder('Server Name').fill('new-server');
    await page.getByPlaceholder('Host').fill('10.0.0.5');
    await page.getByPlaceholder('Admin User').fill('admin');
    await page.getByPlaceholder('Admin Password').fill('password123');

    await page.getByText('Add').first().click();

    // New server should appear in the list after refresh
    await expect(page.getByText('new-server')).toBeVisible();
  });

  test('should test server connection', async ({ page }) => {
    await page.route('**/api/v1/servers/srv1/test', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ message: 'Connection successful' }),
      });
    });

    await page.goto('/servers');

    await page.getByText('Test').first().click();

    // The test triggers an alert() — accept it
    page.on('dialog', async dialog => {
      expect(dialog.message()).toContain('Connection successful');
      await dialog.accept();
    });
  });

  test('should delete a server', async ({ page }) => {
    let servers = [...MOCK_SERVERS];

    await page.route('**/api/v1/servers/srv2', async (route) => {
      if (route.request().method() === 'DELETE') {
        servers = servers.filter(s => s.id !== 'srv2');
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'Deleted' }) });
      }
    });

    await page.route('**/api/v1/servers', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(servers) });
    });

    await page.goto('/servers');

    // Click delete button (Trash2 icon) for secondary server row
    const secondaryRow = page.locator('tr').filter({ hasText: 'secondary' });
    await secondaryRow.locator('button[title="Delete server"]').click();

    // Server should be removed from the list
    await expect(page.getByText('secondary')).not.toBeVisible();
  });

  test('should cancel add server form', async ({ page }) => {
    await page.goto('/servers');

    await page.getByText('Add Server').click();
    await expect(page.getByPlaceholder('Server Name')).toBeVisible();

    await page.getByText('Cancel').first().click();

    // Form should disappear
    await expect(page.getByPlaceholder('Server Name')).not.toBeVisible();
  });

  test('should disable Add button when required fields are empty', async ({ page }) => {
    await page.goto('/servers');

    await page.getByText('Add Server').click();

    // The Add button in the create form should be disabled initially
    const addButton = page.locator('button').filter({ hasText: 'Add' }).filter({ has: page.locator('bg-green-600') });
    await expect(addButton).toBeDisabled();
  });
});
