import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright E2E Test Configuration
 *
 * Tests run against the dev environment with auth bypass enabled:
 * - VITE_ENABLE_AUTH=false (frontend)
 * - ENABLE_AUTH=false (backend)
 *
 * Role switching is done via localStorage.setItem('dev_role', 'Admin')
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report' }],
    ['junit', { outputFile: 'test-results/e2e-results.xml' }],
  ],
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'echo "Ensure docker-compose services are running"',
    url: 'http://localhost:3000',
    reuseExistingServer: true,
    timeout: 5000,
  },
  // Timeout settings
  timeout: 30000,
  expect: {
    timeout: 10000,
  },
  // Output directories
  outputDir: 'test-results',
})
