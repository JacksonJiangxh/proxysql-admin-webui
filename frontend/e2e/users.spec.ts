/**
 * Users page E2E tests.
 *
 * HOW TO RUN WITH A REAL BACKEND:
 *   1. Start the backend: `cd backend && uvicorn app.main:app --reload`
 *   2. Start the frontend: `cd frontend && npm run dev`
 *   3. Run: `npx playwright test users`
 */

import { test, expect } from '@playwright/test';

const MOCK_SERVERS = [
  { id: 'srv1', name: 'default', host: '127.0.0.1', port: 6032, admin_user: 'admin', is_default: true },
];

const MOCK_USERS = [
  { id: 1, username: 'admin', role: 'admin', email: null, is_active: true },
  { id: 2, username: 'operator1', role: 'operator', email: 'op@example.com', is_active: true },
  { id: 3, username: 'viewer1', role: 'viewer', email: null, is_active: false },
];

test.describe('Users Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/servers', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_SERVERS) });
    });
    await page.route('**/api/v1/auth/me', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 1, username: 'admin', role: 'admin', email: null }) });
    });
    await page.route('**/api/v1/users', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_USERS) });
    });
  });

  test('should load user list with existing users', async ({ page }) => {
    await page.goto('/users');

    await expect(page.getByRole('heading', { name: 'Users' })).toBeVisible();

    // User rows
    await expect(page.getByText('admin')).toBeVisible();
    await expect(page.getByText('operator1')).toBeVisible();
    await expect(page.getByText('viewer1')).toBeVisible();

    // Role badges
    await expect(page.getByText('Admin').first()).toBeVisible();
    await expect(page.getByText('Operator').first()).toBeVisible();
    await expect(page.getByText('Viewer').first()).toBeVisible();

    // Active/Inactive status
    await expect(page.getByText('Yes').first()).toBeVisible();
    await expect(page.getByText('No').first()).toBeVisible();

    // Delete buttons (Trash2 icons)
    const deleteButtons = page.locator('button[title="Delete"]');
    await expect(deleteButtons).toHaveCount(3);
  });

  test('should open create user form when clicking Add User', async ({ page }) => {
    await page.goto('/users');

    await page.getByText('Add User').click();

    await expect(page.getByPlaceholder('Username')).toBeVisible();
    await expect(page.getByPlaceholder('Password')).toBeVisible();
    await expect(page.getByPlaceholder('Confirm Password')).toBeVisible();

    // Role selector
    await expect(page.locator('select').filter({ has: page.getByText('Viewer') })).toBeVisible();
  });

  test('should create a new user', async ({ page }) => {
    const newUser = { id: 4, username: 'newuser', role: 'viewer', email: null, is_active: true };

    await page.route('**/api/v1/users', async (route) => {
      const method = route.request().method();
      if (method === 'POST') {
        await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(newUser) });
      } else {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([...MOCK_USERS, newUser]) });
      }
    });

    await page.goto('/users');

    await page.getByText('Add User').click();

    await page.getByPlaceholder('Username').fill('newuser');
    await page.getByPlaceholder('Password').fill('password123');
    await page.getByPlaceholder('Confirm Password').fill('password123');

    await page.locator('button').filter({ hasText: 'Add' }).filter({ has: page.locator('.bg-green-600') }).click();

    await expect(page.getByText('newuser')).toBeVisible();
  });

  test('should show password mismatch error', async ({ page }) => {
    await page.goto('/users');

    await page.getByText('Add User').click();

    await page.getByPlaceholder('Username').fill('testuser');
    await page.getByPlaceholder('Password').fill('password1');
    await page.getByPlaceholder('Confirm Password').fill('password2');

    await page.locator('button').filter({ hasText: 'Add' }).filter({ has: page.locator('.bg-green-600') }).click();

    await expect(page.getByText('Passwords do not match')).toBeVisible();
  });

  test('should delete a user', async ({ page }) => {
    let users = [...MOCK_USERS];

    await page.route('**/api/v1/users/3', async (route) => {
      if (route.request().method() === 'DELETE') {
        users = users.filter(u => u.id !== 3);
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'Deleted' }) });
      }
    });

    await page.route('**/api/v1/users', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(users) });
    });

    await page.goto('/users');

    const viewerRow = page.locator('tr').filter({ hasText: 'viewer1' });
    await viewerRow.locator('button[title="Delete"]').click();

    await expect(page.getByText('viewer1')).not.toBeVisible();
  });

  test('should cancel create user form', async ({ page }) => {
    await page.goto('/users');

    await page.getByText('Add User').click();
    await expect(page.getByPlaceholder('Username')).toBeVisible();

    await page.locator('button').filter({ hasText: 'Cancel' }).click();

    await expect(page.getByPlaceholder('Username')).not.toBeVisible();
  });

  test('should disable Add button when required fields are empty', async ({ page }) => {
    await page.goto('/users');

    await page.getByText('Add User').click();

    const addButton = page.locator('button.bg-green-600').filter({ hasText: 'Add' });
    await expect(addButton).toBeDisabled();
  });
});
