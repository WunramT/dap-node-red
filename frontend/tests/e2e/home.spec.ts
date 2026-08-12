import { test, expect } from '@playwright/test'

/**
 * Home Page E2E Tests
 *
 * These tests run against the dev environment with auth disabled.
 * Make sure the application is running before executing tests:
 * podman compose -f docker-compose.dev.yml up -d
 */

test.describe('Home Page', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to home page
    await page.goto('/')
  })

  test('should display welcome message', async ({ page }) => {
    // Check for welcome heading
    await expect(page.locator('h1')).toContainText('Welcome')
  })

  test('should show navigation bar', async ({ page }) => {
    // Check for app bar
    const appBar = page.locator('.v-app-bar')
    await expect(appBar).toBeVisible()
  })

  test('should show API documentation link', async ({ page }) => {
    // Check for API docs button
    const docsButton = page.getByRole('link', { name: /API Documentation/i })
    await expect(docsButton).toBeVisible()
  })

  test('should show health check link', async ({ page }) => {
    // Check for health check button
    const healthButton = page.getByRole('link', { name: /Health Check/i })
    await expect(healthButton).toBeVisible()
  })

  test('should show dev mode indicator when auth is disabled', async ({ page }) => {
    // In dev mode, there should be a DEV MODE chip
    const devChip = page.locator('.v-chip', { hasText: 'DEV MODE' })
    await expect(devChip).toBeVisible()
  })

  test('should show role switcher in dev mode', async ({ page }) => {
    // The role switcher should be visible in dev mode
    const roleSelect = page.locator('.dev-role-select')
    await expect(roleSelect).toBeVisible()
  })
})

test.describe('Navigation', () => {
  test('should navigate to home when clicking logo', async ({ page }) => {
    await page.goto('/')

    // Click on the brand/logo area
    await page.locator('.nav-brand').click()

    // Should stay on home page
    await expect(page).toHaveURL('/')
  })
})

test.describe('Health Check', () => {
  test('API health endpoint should return healthy status', async ({ request }) => {
    const response = await request.get('/api/health')
    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    expect(data.status).toBe('healthy')
  })
})
