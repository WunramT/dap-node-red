import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import vuetify from 'vite-plugin-vuetify'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [
    vue(),
    vuetify({ autoImport: true })
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  // Enable CSS processing for Vuetify
  css: {
    preprocessorOptions: {
      scss: {
        api: 'modern-compiler'
      }
    }
  },
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: ['./src/test/setup.ts'],
    include: [
      'src/**/*.{test,spec}.{js,ts}',
      'src/**/__tests__/**/*.{js,ts}'
    ],
    exclude: [
      'node_modules',
      'dist'
    ],
    // Important: Allow Vuetify CSS to be processed
    css: true,
    // Use forks pool to avoid "Closing rpc while fetch was pending" errors
    pool: 'forks',
    // Isolate each test file to prevent state leakage
    isolate: true,
    // Allow more time for teardown to prevent pending fetch errors
    teardownTimeout: 5000,
    // Server config for proper module resolution
    server: {
      deps: {
        inline: ['vuetify']
      }
    },
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html', 'cobertura'],
      reportsDirectory: './coverage',
      include: ['src/**/*.{ts,vue}'],
      exclude: [
        'src/**/*.d.ts',
        'src/**/*.spec.ts',
        'src/**/*.test.ts',
        'src/**/test/**',
        'src/**/__tests__/**',
        'src/main.ts'
      ]
    },
    // Mock environment variables
    env: {
      VITE_API_BASE_URL: 'http://localhost:8000/api',
      VITE_ENABLE_AUTH: 'false'
    }
  }
})
