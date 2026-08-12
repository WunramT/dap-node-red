/**
 * E2E Test Fixtures
 *
 * Provides test fixtures and utilities for Playwright tests.
 */
import { test as base } from '@playwright/test'

/**
 * Extended test with custom fixtures
 */
export const test = base.extend({
  // Add custom fixtures here
  // Example:
  // authenticatedPage: async ({ page }, use) => {
  //   // Set up dev role
  //   await page.evaluate(() => {
  //     localStorage.setItem('dev_role', 'Admin')
  //   })
  //   await use(page)
  // },
})

export { expect } from '@playwright/test'

/**
 * Test data constants
 */
export const TEST_DATA = {
  devRoles: ['Admin', 'User'],
  apiEndpoints: {
    health: '/api/health',
    authMe: '/api/auth/me',
  },
}
