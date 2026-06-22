/**
 * Clusters page E2E tests.
 *
 * HOW TO RUN WITH A REAL BACKEND:
 *   1. Start the backend: `cd backend && uvicorn app.main:app --reload`
 *   2. Start the frontend: `cd frontend && npm run dev`
 *   3. Run: `npx playwright test clusters`
 */

import { test, expect } from '@playwright/test';

const MOCK_SERVERS = [
  { id: 'srv1', name: 'default', host: '127.0.0.1', port: 6032, admin_user: 'admin', is_default: true },
  { id: 'srv2', name: 'node2', host: '192.168.1.2', port: 6032, admin_user: 'admin', is_default: false },
];

const MOCK_CLUSTERS = [
  {
    id: 'cluster1',
    name: 'Production Cluster',
    description: 'Main production ProxySQL cluster',
    master_server_id: 'srv1',
    member_count: 2,
  },
  {
    id: 'cluster2',
    name: 'Staging Cluster',
    description: 'Staging environment cluster',
    master_server_id: 'srv2',
    member_count: 1,
  },
];

const MOCK_MEMBERS = [
  { server_id: 'srv1', server_name: 'default', server_host: '127.0.0.1', server_port: 6032, role: 'master' },
  { server_id: 'srv2', server_name: 'node2', server_host: '192.168.1.2', server_port: 6032, role: 'slave' },
];

const MOCK_CLUSTER_STATUS = {
  nodes: [
    { server_id: 'srv1', online: true, version: '2.5.5' },
    { server_id: 'srv2', online: true, version: '2.5.5' },
  ],
  config_consistency: {
    status: 'consistent',
    consistent_tables: 7,
    total_tables: 7,
    tables: {},
  },
};

test.describe('Clusters Page - List', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/servers', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_SERVERS) });
    });
    await page.route('**/api/v1/auth/me', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 1, username: 'admin', role: 'admin', email: null }) });
    });
    await page.route('**/api/v1/clusters', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_CLUSTERS) });
    });
  });

  test('should load cluster list with existing clusters', async ({ page }) => {
    await page.goto('/clusters');

    await expect(page.getByRole('heading', { name: 'Cluster Management' })).toBeVisible();
    await expect(page.getByText('Production Cluster')).toBeVisible();
    await expect(page.getByText('Staging Cluster')).toBeVisible();

    // Member count badges
    await expect(page.getByText('2 node(s)').first()).toBeVisible();
    await expect(page.getByText('1 node(s)').first()).toBeVisible();
  });

  test('should show empty state when no clusters exist', async ({ page }) => {
    await page.route('**/api/v1/clusters', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });

    await page.goto('/clusters');

    await expect(page.getByText('No cluster groups created')).toBeVisible();
  });

  test('should navigate to cluster detail when clicking a cluster', async ({ page }) => {
    await page.route('**/api/v1/clusters/cluster1', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_CLUSTERS[0]) });
    });
    await page.route('**/api/v1/clusters/cluster1/members', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_MEMBERS) });
    });
    await page.route('**/api/v1/clusters/cluster1/status', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_CLUSTER_STATUS) });
    });
    await page.route('**/api/v1/clusters/cluster1/sync-logs**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });

    await page.goto('/clusters');

    // Click on Production Cluster name
    await page.getByText('Production Cluster').click();

    await expect(page).toHaveURL(/\/clusters\/cluster1/);
  });

  test('should open create cluster form when clicking Create Cluster', async ({ page }) => {
    await page.goto('/clusters');

    await page.getByText('Create Cluster').click();

    await expect(page.getByPlaceholder('Cluster Name')).toBeVisible();
    await expect(page.getByPlaceholder('Description')).toBeVisible();
    // Master node selector
    await expect(page.locator('select').filter({ has: page.getByText('Select master node') })).toBeVisible();
  });

  test('should create a new cluster', async ({ page }) => {
    const newCluster = {
      id: 'cluster3',
      name: 'Test Cluster',
      description: 'Test',
      master_server_id: 'srv1',
      member_count: 0,
    };

    await page.route('**/api/v1/clusters', async (route) => {
      const method = route.request().method();
      if (method === 'POST') {
        await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(newCluster) });
      } else {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([...MOCK_CLUSTERS, newCluster]) });
      }
    });

    await page.goto('/clusters');

    await page.getByText('Create Cluster').click();

    await page.getByPlaceholder('Cluster Name').fill('Test Cluster');
    await page.getByPlaceholder('Description').fill('Test');

    await page.locator('button.bg-green-600').filter({ hasText: 'Add' }).click();

    await expect(page.getByText('Test Cluster')).toBeVisible();
  });

  test('should delete a cluster', async ({ page }) => {
    let clusters = [...MOCK_CLUSTERS];

    await page.route('**/api/v1/clusters/cluster2', async (route) => {
      if (route.request().method() === 'DELETE') {
        clusters = clusters.filter(c => c.id !== 'cluster2');
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'Deleted' }) });
      }
    });

    await page.route('**/api/v1/clusters', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(clusters) });
    });

    await page.goto('/clusters');

    // Accept the confirm dialog
    page.on('dialog', async dialog => {
      await dialog.accept();
    });

    const stagingRow = page.locator('[class*="rounded-xl"]').filter({ hasText: 'Staging Cluster' });
    await stagingRow.locator('button[title="Delete"]').click();

    await expect(page.getByText('Staging Cluster')).not.toBeVisible();
  });
});

test.describe('Clusters Page - Detail', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/servers', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_SERVERS) });
    });
    await page.route('**/api/v1/auth/me', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 1, username: 'admin', role: 'admin', email: null }) });
    });
    await page.route('**/api/v1/clusters', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_CLUSTERS) });
    });
    await page.route('**/api/v1/clusters/cluster1', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_CLUSTERS[0]) });
    });
    await page.route('**/api/v1/clusters/cluster1/members', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_MEMBERS) });
    });
    await page.route('**/api/v1/clusters/cluster1/status', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_CLUSTER_STATUS) });
    });
    await page.route('**/api/v1/clusters/cluster1/sync-logs**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });
  });

  test('should display cluster detail with header and tabs', async ({ page }) => {
    await page.goto('/clusters/cluster1');

    await expect(page.getByText('Production Cluster')).toBeVisible();
    await expect(page.getByText('2 node(s) total')).toBeVisible();

    // Back link
    await expect(page.getByText('← Back to clusters')).toBeVisible();

    // Tabs should be visible
    await expect(page.getByText('Nodes')).toBeVisible();
    await expect(page.getByText('Sync')).toBeVisible();
    await expect(page.getByText('Variables')).toBeVisible();
    await expect(page.getByText('Logs')).toBeVisible();
  });

  test('should show config consistency status', async ({ page }) => {
    await page.goto('/clusters/cluster1');

    await expect(page.getByText('Consistent')).toBeVisible();
  });

  test('should display member list in Nodes tab', async ({ page }) => {
    await page.goto('/clusters/cluster1');

    // Nodes tab is default active
    await expect(page.getByText('default')).toBeVisible();
    await expect(page.getByText('127.0.0.1:6032')).toBeVisible();
    await expect(page.getByText('node2')).toBeVisible();

    // Role badges
    await expect(page.getByText('Master').first()).toBeVisible();
    await expect(page.getByText('Slave').first()).toBeVisible();

    // Online status
    await expect(page.getByText('Online').first()).toBeVisible();
  });

  test('should navigate back to cluster list', async ({ page }) => {
    await page.goto('/clusters/cluster1');

    await page.getByText('← Back to clusters').click();

    await expect(page).toHaveURL(/\/clusters$/);
  });

  test('should show add node form when clicking Add Node', async ({ page }) => {
    await page.goto('/clusters/cluster1');

    await page.getByText('Add Node').click();

    // Server selector and role selector should appear
    await expect(page.getByText('Select server')).toBeVisible();
  });

  test('should show sync tab with module selection', async ({ page }) => {
    await page.goto('/clusters/cluster1');

    // Switch to Sync tab
    await page.getByText('Sync').click();

    await expect(page.getByText('Select modules to sync')).toBeVisible();
    await expect(page.getByText('MySQL Servers')).toBeVisible();
    await expect(page.getByText('MySQL Users')).toBeVisible();
    await expect(page.getByText('Auto-apply to Runtime')).toBeVisible();
  });

  test('should show empty logs in Logs tab', async ({ page }) => {
    await page.goto('/clusters/cluster1');

    await page.getByText('Logs').click();

    await expect(page.getByText('No sync logs')).toBeVisible();
  });
});
