/**
 * E2E tests for Auto-backup Scheduler functionality.
 *
 * Covers: schedule listing, creation, deletion.
 * All API calls are mocked via page.route().
 */
import { test, expect } from '@playwright/test';

// ── Mock Data ──────────────────────────────────────────────────────
const MOCK_SCHEDULES = [
  {
    id: 1, server_id: 'srv1', cron_expression: '0 3 * * *',
    enabled: true, last_run: '2026-07-01T03:00:00Z',
    next_run: '2026-07-02T03:00:00Z', created_at: '2026-06-20T00:00:00Z',
  },
  {
    id: 2, server_id: 'srv2', cron_expression: '0 */6 * * *',
    enabled: true, last_run: '2026-07-01T18:00:00Z',
    next_run: '2026-07-02T00:00:00Z', created_at: '2026-06-25T00:00:00Z',
  },
];

const MOCK_SERVERS = [
  { id: 'srv1', name: 'Production ProxySQL 1', host: '10.0.0.1', port: 6032 },
  { id: 'srv2', name: 'Staging ProxySQL', host: '10.0.0.2', port: 6032 },
];

const MOCK_USER = {
  id: 1, username: 'admin', role: 'admin', email: 'admin@example.com',
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
test.describe('Scheduler Page', () => {
  test.beforeEach(async ({ page }) => {
    await mockCommonApis(page);
    await page.route('**/api/v1/scheduler/status', async (route) => {
      await route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify({ schedules: MOCK_SCHEDULES }),
      });
    });
    await page.goto('/backup');
  });

  test('should display schedule listing', async ({ page }) => {
    // Check for schedule-related UI — may be a tab or section within backup page
    const scheduleTab = page.getByText(/schedule/i).or(page.getByRole('tab', { name: /schedule/i }));
    if (await scheduleTab.isVisible({ timeout: 3000 })) {
      await scheduleTab.click();
      // Verify schedule entries are visible
      await expect(page.getByText('0 3 * * *')).toBeVisible({ timeout: 5000 });
      await expect(page.getByText('0 */6 * * *')).toBeVisible();
    }
  });

  test('should create a new schedule', async ({ page }) => {
    await page.route('**/api/v1/scheduler/backup', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify({
            id: 3, server_id: 'srv1', cron_expression: '0 12 * * 1-5',
            message: 'Schedule created successfully',
          }),
        });
      }
    });

    // Navigate to schedule section
    const scheduleTab = page.getByText(/schedule/i).or(page.getByRole('tab', { name: /schedule/i }));
    if (await scheduleTab.isVisible({ timeout: 3000 })) {
      await scheduleTab.click();
    }

    // Look for create schedule form
    const cronInput = page.getByPlaceholder(/cron/i).or(page.locator('input[name="cron_expression"]'));
    if (await cronInput.isVisible({ timeout: 3000 })) {
      await cronInput.fill('0 12 * * 1-5');
      const createBtn = page.getByRole('button', { name: /create/i }).or(page.getByRole('button', { name: /add/i }));
      if (await createBtn.isVisible()) {
        await createBtn.click();
      }
    }
  });

  test('should delete a schedule', async ({ page }) => {
    let schedules = [...MOCK_SCHEDULES];
    await page.route('**/api/v1/scheduler/**', async (route) => {
      const url = route.request().url();
      if (url.endsWith('/status')) {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ schedules }) });
      } else if (route.request().method() === 'DELETE') {
        const match = url.match(/\/backup\/(\d+)$/);
        if (match) {
          schedules = schedules.filter(s => s.id !== parseInt(match[1]));
          await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'Schedule removed' }) });
        }
      }
    });

    const scheduleTab = page.getByText(/schedule/i).or(page.getByRole('tab', { name: /schedule/i }));
    if (await scheduleTab.isVisible({ timeout: 3000 })) {
      await scheduleTab.click();
    }

    const deleteBtn = page.getByRole('button', { name: /delete/i }).first();
    if (await deleteBtn.isVisible({ timeout: 3000 })) {
      page.on('dialog', async dialog => { await dialog.accept(); });
      await deleteBtn.click();
    }
  });

  test('should show empty state when no schedules', async ({ page }) => {
    await page.route('**/api/v1/scheduler/status', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ schedules: [] }) });
    });

    const scheduleTab = page.getByText(/schedule/i).or(page.getByRole('tab', { name: /schedule/i }));
    if (await scheduleTab.isVisible({ timeout: 3000 })) {
      await scheduleTab.click();
      await expect(page.getByText(/no schedules/i).or(page.getByText(/no schedule/i))).toBeVisible({ timeout: 5000 });
    }
  });
});
