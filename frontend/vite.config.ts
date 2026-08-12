import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vuetify from 'vite-plugin-vuetify'
import { fileURLToPath, URL } from 'node:url'

// Helper to get base path - handles empty string correctly
const getBasePath = (): string => {
  const envPath = process.env.VITE_BASE_PATH
  // If VITE_BASE_PATH is explicitly set (even to empty string), use it
  // Only fall back to placeholder if the env var is undefined
  if (envPath !== undefined) {
    // Ensure path ends with / for proper base URL behavior
    return envPath === '' ? '/' : (envPath.endsWith('/') ? envPath : `${envPath}/`)
  }
  // Placeholder for production builds - will be replaced at container runtime
  return '/__VITE_BASE_PATH__/'
}

const basePath = getBasePath()

// https://vite.dev/config/
export default defineConfig({
  // Base path: Configurable via VITE_BASE_PATH environment variable
  base: basePath,
  define: {
    'import.meta.env.AUTH_PROVIDER': JSON.stringify(
        process.env.MODE === 'production' ? 'local' : 'none'
    ),
  },
  plugins: [
    vue(),
    vuetify({ autoImport: true })
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    host: '0.0.0.0',
    port: 3000,
    hmr: {
      port: 24678,  // Internal port - stays fixed
      clientPort: parseInt(process.env.VITE_HMR_CLIENT_PORT || '24678'),  // External mapped port
    },
    watch: {
      usePolling: true,
      interval: 1000
    },
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
        timeout: 600000
      },
      // API with dynamic base path (dev only - matches Nginx config in prod)
      [`${basePath}api/`]: {
        target: 'http://backend:8000',
        changeOrigin: true,
        timeout: 600000,
        rewrite: (path) => path.replace(new RegExp(`^${basePath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`), '/')
      },
      '/socket.io/': {
        target: 'http://backend:8000',
        changeOrigin: true,
        ws: true
      },
      // Socket.IO with dynamic base path (dev only - matches Nginx config in prod)
      [`${basePath}socket.io/`]: {
        target: 'http://backend:8000',
        changeOrigin: true,
        ws: true,
        rewrite: (path) => path.replace(new RegExp(`^${basePath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`), '/')
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    minify: 'esbuild',
    chunkSizeWarningLimit: 1000
  }
})
