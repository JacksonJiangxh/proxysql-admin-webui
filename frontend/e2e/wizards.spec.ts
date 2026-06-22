/**
 * Wizards page E2E tests.
 *
 * HOW TO RUN WITH A REAL BACKEND:
 *   1. Start the backend: `cd backend && uvicorn app.main:app --reload`
 *   2. Start the frontend: `cd frontend && npm run dev`
 *   3. Run: `npx playwright test wizards`
 */

import { test, expect } from '@playwright/test';

const MOCK_SERVERS = [
  { id: 'srv1', name: 'default', host: '127.0.0.1', port: 6032, admin_user: 'admin', is_default: true },
];

const MOCK_WIZARDS = {
  wizards: [
    {
      id: 'add_backend_server',
      name: 'Add Backend MySQL Server',
      description: 'Add a new MySQL backend server to a hostgroup.',
      category: 'backend_servers',
      status: 'implemented',
      auto_apply_module: true,
      fields: [
        { name: 'hostgroup_id', label: 'Hostgroup ID', type: 'number', required: true, default: 0, help: 'The hostgroup to assign the server to' },
        { name: 'hostname', label: 'Hostname', type: 'text', required: true, placeholder: 'e.g. 10.0.0.1' },
        { name: 'port', label: 'Port', type: 'number', required: true, default: 3306 },
        { name: 'weight', label: 'Weight', type: 'number', default: 1, min: 0, max: 1000000 },
        { name: 'max_connections', label: 'Max Connections', type: 'number', default: 200 },
        { name: 'comment', label: 'Comment', type: 'text', placeholder: 'Optional comment' },
      ],
    },
    {
      id: 'remove_backend_server',
      name: 'Remove Backend MySQL Server',
      description: 'Remove a backend server from ProxySQL configuration.',
      category: 'backend_servers',
      status: 'implemented',
      fields: [
        { name: 'hostgroup_id', label: 'Hostgroup ID', type: 'number', required: true },
        { name: 'hostname', label: 'Hostname', type: 'text', required: true },
        { name: 'port', label: 'Port', type: 'number', required: true },
      ],
    },
    {
      id: 'add_mysql_user',
      name: 'Add MySQL User',
      description: 'Add a new MySQL user to ProxySQL.',
      category: 'backend_users',
      status: 'implemented',
      auto_apply_module: true,
      fields: [
        { name: 'username', label: 'Username', type: 'text', required: true },
        { name: 'password', label: 'Password', type: 'password', required: true },
        { name: 'default_hostgroup', label: 'Default Hostgroup', type: 'number', default: 0 },
        { name: 'active', label: 'Active', type: 'toggle', default: 1 },
      ],
    },
    {
      id: 'future_wizard',
      name: 'Future Feature',
      description: 'A planned wizard that is not yet implemented.',
      category: 'monitoring',
      status: 'planned',
      fields: [],
    },
  ],
};

test.describe('Wizards Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/servers', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_SERVERS) });
    });
    await page.route('**/api/v1/auth/me', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 1, username: 'admin', role: 'admin', email: null }) });
    });
    await page.route('**/api/v1/wizards/definitions', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_WIZARDS) });
    });
  });

  test('should load wizard page with categories', async ({ page }) => {
    await page.goto('/wizards');

    await expect(page.getByRole('heading', { name: 'Configuration Wizards' })).toBeVisible();

    // Category headers should be visible
    await expect(page.getByText('Backend Servers (W01-W08)')).toBeVisible();
    await expect(page.getByText('Backend Users (W09-W15)')).toBeVisible();
    await expect(page.getByText('Monitoring & Diagnostics (W53-W63)')).toBeVisible();
  });

  test('should display wizard cards with names and badges', async ({ page }) => {
    await page.goto('/wizards');

    // Wizard cards
    await expect(page.getByText('Add Backend MySQL Server')).toBeVisible();
    await expect(page.getByText('Remove Backend MySQL Server')).toBeVisible();

    // Status badges
    await expect(page.getByText('Implemented').first()).toBeVisible();
    await expect(page.getByText('Planned')).toBeVisible();

    // Field count badge
    await expect(page.getByText('6 fields')).toBeVisible();

    // Auto-apply badge
    await expect(page.getByText('Auto-apply')).toBeVisible();
  });

  test('should navigate to wizard detail when clicking a wizard card', async ({ page }) => {
    await page.goto('/wizards');

    await page.getByText('Add Backend MySQL Server').click();

    await expect(page).toHaveURL(/\/wizards\/add_backend_server/);
    await expect(page.getByText('← Back to wizards')).toBeVisible();
    await expect(page.getByText('add_backend_server')).toBeVisible();
  });

  test('should show wizard form with fields when navigating to detail', async ({ page }) => {
    await page.route('**/api/v1/wizards/definitions/add_backend_server', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_WIZARDS) });
    });

    await page.goto('/wizards/add_backend_server');

    // Form fields should be visible
    await expect(page.getByText('Hostgroup ID')).toBeVisible();
    await expect(page.getByText('Hostname')).toBeVisible();
    await expect(page.getByText('Port')).toBeVisible();
    await expect(page.getByText('Weight')).toBeVisible();

    // Required indicators
    await expect(page.getByText('*').first()).toBeVisible();

    // Auto-apply checkbox
    await expect(page.getByText('Auto-apply')).toBeVisible();
  });

  test('should show SQL preview button and execute button', async ({ page }) => {
    await page.goto('/wizards/add_backend_server');

    await expect(page.getByText('Preview SQL')).toBeVisible();
    await expect(page.getByText('Execute')).toBeVisible();
  });

  test('should preview SQL when clicking preview button', async ({ page }) => {
    await page.route('**/api/v1/wizards/preview', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          sql_preview: [
            'INSERT INTO mysql_servers (hostgroup_id, hostname, port, weight, max_connections) VALUES (0, "10.0.0.1", 3306, 1, 200)',
            'LOAD MYSQL SERVERS TO RUNTIME',
          ],
        }),
      });
    });

    await page.goto('/wizards/add_backend_server');

    // Fill required fields
    await page.getByPlaceholder('e.g. 10.0.0.1').fill('10.0.0.1');

    await page.getByText('Preview SQL').click();

    // SQL preview section should appear
    await expect(page.getByText('SQL Preview')).toBeVisible();
    await expect(page.getByText('INSERT INTO mysql_servers')).toBeVisible();
  });

  test('should execute wizard when clicking execute button', async ({ page }) => {
    await page.route('**/api/v1/wizards/execute', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          executed_sql: ['INSERT INTO mysql_servers ...', 'LOAD MYSQL SERVERS TO RUNTIME'],
        }),
      });
    });

    await page.goto('/wizards/add_backend_server');

    await page.getByPlaceholder('e.g. 10.0.0.1').fill('10.0.0.1');

    await page.getByText('Execute').click();

    // Execution result should appear
    await expect(page.getByText('Execution Result')).toBeVisible();
  });

  test('should show planned notice for planned wizards', async ({ page }) => {
    await page.goto('/wizards/future_wizard');

    await expect(page.getByText('This wizard is part of the roadmap but not yet implemented')).toBeVisible();
  });

  test('should navigate back to wizard list', async ({ page }) => {
    await page.goto('/wizards/add_backend_server');

    await page.getByText('← Back to wizards').click();

    await expect(page).toHaveURL(/\/wizards$/);
    await expect(page.getByRole('heading', { name: 'Configuration Wizards' })).toBeVisible();
  });
});
