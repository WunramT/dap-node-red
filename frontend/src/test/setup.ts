/**
 * Vitest Global Test Setup
 *
 * This file runs before all tests and sets up:
 * - Vuetify plugin for component tests
 * - Pinia stores
 * - MSW mock server for API requests
 * - Global test utilities
 */

// Declare global types for test environment
declare const global: typeof globalThis

import { config } from '@vue/test-utils'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import { createPinia, setActivePinia } from 'pinia'
import { vi, beforeAll, afterAll, afterEach } from 'vitest'
import { server } from './mocks/server'

// Create Vuetify instance for tests
const vuetify = createVuetify({
  components,
  directives,
})

// Configure Vue Test Utils globals
config.global.plugins = [vuetify]

// Setup Pinia before each test file
beforeAll(() => {
  setActivePinia(createPinia())
})

// Start MSW server before all tests
beforeAll(() => {
  // Use 'bypass' to silently ignore unhandled requests (avoids errors on cleanup)
  server.listen({ onUnhandledRequest: 'bypass' })
})

// Reset handlers after each test
afterEach(() => {
  server.resetHandlers()
})

// Close MSW server after all tests
afterAll(async () => {
  server.close()
  // Give MSW time to clean up pending requests
  await new Promise((resolve) => setTimeout(resolve, 100))
})

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value.toString()
    },
    removeItem: (key: string) => {
      delete store[key]
    },
    clear: () => {
      store = {}
    },
  }
})()

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
})

// Mock sessionStorage
Object.defineProperty(window, 'sessionStorage', {
  value: localStorageMock,
})

// Mock ResizeObserver (needed by Vuetify)
class MockResizeObserver {
  observe = vi.fn()
  unobserve = vi.fn()
  disconnect = vi.fn()
}
global.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver

// Mock IntersectionObserver (needed by some Vuetify components)
class MockIntersectionObserver {
  observe = vi.fn()
  unobserve = vi.fn()
  disconnect = vi.fn()
  root = null
  rootMargin = ''
  thresholds = []
  takeRecords = vi.fn().mockReturnValue([])
}
global.IntersectionObserver = MockIntersectionObserver as unknown as typeof IntersectionObserver

// Mock window.matchMedia (needed by Vuetify theme)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Mock scrollTo
window.scrollTo = vi.fn()
