/**
 * Axios HTTP client configuration with authentication
 * Supports Azure AD (MSAL), Local DB, Master-Password, Passwordless, and Development Mode
 */
import axios, { type AxiosInstance, type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import type { ApiError } from '@/types/common'
import { useAuthStore } from '@/stores/auth'

// Build API base URL from Vite's BASE_URL
const getApiBaseUrl = (): string => {
  const basePath = import.meta.env.BASE_URL || '/'
  return basePath.replace(/\/$/, '') + '/api'
}

const apiBaseUrl = getApiBaseUrl()

// Create axios instance
const apiClient: AxiosInstance = axios.create({
  baseURL: apiBaseUrl,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  },
  paramsSerializer: {
    indexes: null
  }
})

// Request interceptor - Add JWT token or dev role header to requests
apiClient.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    const authStore = useAuthStore()

    // Debug logging for requests
    console.log('[AXIOS] Request:', config.method?.toUpperCase(), config.url)
    if (config.data) {
      console.log('[AXIOS] Request Data:', JSON.stringify(config.data, null, 2))
    }

    // In development mode, add X-Dev-Role header for testing
    if (authStore.isDevelopmentMode) {
      config.headers['X-Dev-Role'] = authStore.devRole
      return config
    }

    // Production modes: Use backend JWT token from auth store
    if (authStore.accessToken) {
      config.headers.Authorization = `Bearer ${authStore.accessToken}`
    }

    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor - Handle errors and token refresh
apiClient.interceptors.response.use(
  (response) => {
    return response
  },
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }
    const authStore = useAuthStore()

    // Handle token expiration with refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      // Try to refresh the token
      const newToken = await authStore.refreshAccessToken()

      if (newToken && originalRequest.headers) {
        // Retry the original request with new token
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        return apiClient(originalRequest)
      } else if (!authStore.isDevelopmentMode) {
        // Refresh failed and not in development mode, redirect to login
        const basePath = import.meta.env.BASE_URL || '/'
        const loginPath = basePath.replace(/\/$/, '') + '/login'
        if (!window.location.pathname.endsWith('/login') && !window.location.pathname.endsWith('/auth/callback')) {
          window.location.href = loginPath
        }
      }
    }

    // Handle other errors
    const apiError: ApiError = {
      message: 'An unexpected error occurred',
      status: error.response?.status,
      code: error.code
    }

    if (error.response) {
      // Server responded with error
      const data = error.response.data as Record<string, unknown>
      apiError.message = (data?.detail as string) || (data?.message as string) || error.message

      // Handle specific error codes
      if (error.response.status === 401) {
        apiError.message = 'Not authorized. Please log in.'
      } else if (error.response.status === 403) {
        apiError.message = 'Access denied. Missing permission.'
      } else if (error.response.status === 404) {
        apiError.message = 'Resource not found'
      } else if (error.response.status === 409) {
        apiError.message = (data?.detail as string) || 'Conflict: Resource already exists'
      } else if (error.response.status === 422) {
        apiError.message = 'Validation error'
        if (data?.detail && Array.isArray(data.detail)) {
          apiError.validationErrors = data.detail
        }
      } else if (error.response.status >= 500) {
        apiError.message = 'Server error. Please try again later.'
      }
    } else if (error.request) {
      // Request made but no response
      apiError.message = 'No connection to server'
    }

    return Promise.reject(apiError)
  }
)

export default apiClient
