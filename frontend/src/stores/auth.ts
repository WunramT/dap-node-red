/**
 * Pinia Store for Authentication State
 * Supports Azure AD (MSAL), Local DB, Master-Password, Passwordless, and Dev Mode authentication
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  initializeMsal,
  fetchAuthConfig,
  getCachedAuthConfig,
  isDevMode,
  isProviderActive,
  isPasswordlessActive,
  getCurrentAccount,
  loginRedirect,
  loginPopup,
  logout as msalLogout,
  getAccessToken,
  getUserInfo,
  getRolesFromClaims,
  type LocalRole,
} from '@/services/auth/authService'
import type { AccountInfo } from '@azure/msal-browser'
import type { AuthConfig } from '@/types/common'
import apiClient from '@/api/client'
import { logger } from '@/services/logger'

// Dev mode roles available for switching
export type DevRole = 'Admin' | 'User'

// Mapping from dev role display names to local role names
const DEV_ROLE_MAPPING: Record<DevRole, LocalRole[]> = {
  'Admin': ['admin'],
  'User': ['user'],
}

interface User {
  id: string
  email: string
  first_name: string
  last_name: string
  roles: string[]
  is_active: boolean
  last_login_at?: string
}

export const useAuthStore = defineStore('auth', () => {
  // State
  const authConfig = ref<AuthConfig | null>(null)
  const account = ref<AccountInfo | null>(null)
  const user = ref<User | null>(null)
  const isInitialized = ref<boolean>(false)
  const accessToken = ref<string | null>(localStorage.getItem('dapnodered_access_token'))
  const refreshToken = ref<string | null>(localStorage.getItem('dapnodered_refresh_token'))
  const loading = ref<boolean>(false)
  const error = ref<string | null>(null)

  // Passwordless: the user has a basic "user" token but no elevated login yet
  const isPasswordlessSession = ref<boolean>(false)

  // Track which provider was used for the current login session
  // Values: 'azure' | 'local_db' | 'master_pw' | 'passwordless' | null
  const storedLoginProvider = localStorage.getItem('login_provider')
  const loginProvider = ref<string | null>(storedLoginProvider)

  // Dev Mode: Store selected role in localStorage
  const storedDevRole = localStorage.getItem('dev_role') as DevRole
  const validDevRoles: DevRole[] = ['Admin', 'User']
  const initialDevRole = validDevRoles.includes(storedDevRole) ? storedDevRole : 'Admin'
  const devRole = ref<DevRole>(initialDevRole)

  // Computed: derive mode helpers from authConfig
  const isDevelopmentMode = computed(() => authConfig.value?.mode === 'development')
  const isProductionMode = computed(() => authConfig.value?.mode === 'production')

  // Computed: Check if authenticated
  const isAuthenticated = computed(() => {
    if (isDevelopmentMode.value) {
      // Dev mode: always authenticated
      return true
    }
    if (isPasswordlessSession.value) {
      // Passwordless: visitor is always considered "authenticated" as user
      return true
    }
    return account.value !== null || (!!accessToken.value && !!user.value)
  })

  // Computed: Get current roles
  const currentRoles = computed<LocalRole[]>(() => {
    if (isDevelopmentMode.value) {
      // Dev mode: use selected dev role (with fallback to admin if invalid)
      const mappedRoles = DEV_ROLE_MAPPING[devRole.value]
      if (!mappedRoles) {
        logger.warn(`Invalid devRole "${devRole.value}", falling back to admin`, { devRole: devRole.value })
        return ['admin']
      }
      return mappedRoles
    }
    // Azure AD mode: get roles from token claims
    const claimRoles = getRolesFromClaims()
    if (claimRoles.length > 0) return claimRoles
    // Fallback to user object roles
    return (user.value?.roles || ['user']) as LocalRole[]
  })

  // Computed: User info (works in all modes)
  const userInfo = computed(() => {
    if (isDevelopmentMode.value) {
      return {
        email: 'dev@localhost',
        name: `Dev ${devRole.value}`,
        username: 'dev@localhost',
      }
    }
    const info = getUserInfo()
    if (info) return info
    if (user.value) {
      return {
        email: user.value.email,
        name: `${user.value.first_name} ${user.value.last_name}`,
        username: user.value.email,
      }
    }
    return null
  })

  // Computed: Role checks
  const isAdmin = computed(() => {
    return currentRoles.value.includes('admin')
  })

  const userName = computed(() => userInfo.value?.name || 'Unknown User')
  const userEmail = computed(() => userInfo.value?.email || '')

  // Actions
  async function initialize() {
    if (isInitialized.value) return

    loading.value = true
    error.value = null

    try {
      // Fetch auth config from backend first
      authConfig.value = await fetchAuthConfig()
      logger.info(`Auth mode: ${authConfig.value.mode}`, authConfig.value)

      if (isDevelopmentMode.value) {
        // Dev mode: set mock authentication – no login needed
        isInitialized.value = true
        loading.value = false
        logger.info('Development Mode: Authentication disabled, using mock user')
        return
      }

      // Production mode
      if (authConfig.value.providers.azure) {
        // Azure Entra ID mode: Initialize MSAL
        await initializeMsal()

        // Get current account
        account.value = getCurrentAccount()

        // If authenticated via MSAL, perform token exchange
        if (account.value) {
          logger.info('MSAL account found, performing token exchange')

          const azureToken = await getAccessToken()

          if (azureToken) {
            const response = await apiClient.post('/auth/azure-login', {
              token: azureToken
            })

            accessToken.value = response.data.access_token
            refreshToken.value = response.data.refresh_token
            localStorage.setItem('dapnodered_access_token', response.data.access_token)
            localStorage.setItem('dapnodered_refresh_token', response.data.refresh_token)

            // Track that this session was authenticated via Azure
            loginProvider.value = 'azure'
            localStorage.setItem('login_provider', 'azure')

            logger.info('Token exchange successful, loading user profile')
            await loadUser()
          } else {
            logger.warn('Azure token acquisition failed, clearing stale tokens')
            accessToken.value = null
            refreshToken.value = null
            localStorage.removeItem('dapnodered_access_token')
            localStorage.removeItem('dapnodered_refresh_token')
          }
        } else if (accessToken.value) {
          await loadUser()
        }
      } else if (authConfig.value.providers.local_db) {
        // Local DB mode: check for existing token
        if (accessToken.value) {
          await loadUser()
        }
      } else if (authConfig.value.providers.master_pw || authConfig.value.passwordless) {
        // Master-PW / passwordless mode: check for existing token
        if (accessToken.value) {
          await loadUser()
        }
      }

      // Passwordless: auto-obtain a user token if not already authenticated
      if (authConfig.value.passwordless && !isAuthenticated.value) {
        await loginPasswordless()
      }

      isInitialized.value = true
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to initialize authentication'
      error.value = errorMessage
      logger.error('Auth initialization error', err)
    } finally {
      loading.value = false
    }
  }

  async function login(emailOrPopup?: string | boolean, password?: string) {
    loading.value = true
    error.value = null

    try {
      if (isDevelopmentMode.value) {
        // Dev mode: already authenticated
        return true
      }

      // Local DB mode: email/password login - check this FIRST before Azure
      // This ensures that when both providers are enabled, providing credentials uses local_db
      if (authConfig.value?.providers.local_db && typeof emailOrPopup === 'string' && password) {
        const response = await apiClient.post('/auth/login', {
          email: emailOrPopup,
          password: password
        })

        accessToken.value = response.data.access_token
        refreshToken.value = response.data.refresh_token
        localStorage.setItem('dapnodered_access_token', response.data.access_token)
        localStorage.setItem('dapnodered_refresh_token', response.data.refresh_token)

        // Track that this session is authenticated via local_db
        loginProvider.value = 'local_db'
        localStorage.setItem('login_provider', 'local_db')

        isPasswordlessSession.value = false
        await loadUser()
        return true
      }

      // Azure Entra ID login - only if no local credentials were provided
      if (authConfig.value?.providers.azure) {
        if (typeof emailOrPopup === 'boolean') {
          if (emailOrPopup) {
            await loginPopup()
            account.value = getCurrentAccount()
            // Track that this session is authenticated via Azure
            loginProvider.value = 'azure'
            localStorage.setItem('login_provider', 'azure')
            await refreshAccessToken()
          } else {
            await loginRedirect()
          }
        } else {
          await loginRedirect()
        }
        return true
      }

      return false
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Login failed'
      error.value = errorMessage
      logger.error('Login error', err)
      return false
    } finally {
      loading.value = false
    }
  }

  async function loginWithMasterPassword(password: string): Promise<boolean> {
    loading.value = true
    error.value = null

    try {
      const response = await apiClient.post('/auth/master-pw-login', { password })

      accessToken.value = response.data.access_token
      refreshToken.value = response.data.refresh_token
      localStorage.setItem('dapnodered_access_token', response.data.access_token)
      localStorage.setItem('dapnodered_refresh_token', response.data.refresh_token)

      // Track that this session is authenticated via master_pw
      loginProvider.value = 'master_pw'
      localStorage.setItem('login_provider', 'master_pw')

      isPasswordlessSession.value = false
      await loadUser()
      return true
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Login failed'
      error.value = errorMessage
      logger.error('Master-password login error', err)
      return false
    } finally {
      loading.value = false
    }
  }

  /** @deprecated Use loginWithMasterPassword – kept for backward compatibility */
  async function loginWithPassword(password: string, role: 'admin' | 'user' = 'admin'): Promise<boolean> {
    if (role === 'admin') {
      return loginWithMasterPassword(password)
    }
    return loginPasswordless()
  }

  async function loginPasswordless(): Promise<boolean> {
    loading.value = true
    error.value = null

    try {
      const response = await apiClient.post('/auth/passwordless-token')

      accessToken.value = response.data.access_token
      refreshToken.value = response.data.refresh_token
      localStorage.setItem('dapnodered_access_token', response.data.access_token)
      localStorage.setItem('dapnodered_refresh_token', response.data.refresh_token)

      // Track that this session is authenticated via passwordless
      loginProvider.value = 'passwordless'
      localStorage.setItem('login_provider', 'passwordless')

      isPasswordlessSession.value = true
      await loadUser()
      return true
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Passwordless login failed'
      error.value = errorMessage
      logger.error('Passwordless login error', err)
      return false
    } finally {
      loading.value = false
    }
  }

  /** @deprecated Use loginPasswordless */
  async function continueAsUser(): Promise<boolean> {
    return loginPasswordless()
  }

  async function logoutUser() {
    loading.value = true
    error.value = null

    try {
      // Remember which provider was used before clearing state
      const wasAzureLogin = loginProvider.value === 'azure'

      // Clear local state FIRST (before any redirects)
      account.value = null
      user.value = null
      accessToken.value = null
      refreshToken.value = null
      loginProvider.value = null
      isPasswordlessSession.value = false
      localStorage.removeItem('dapnodered_access_token')
      localStorage.removeItem('dapnodered_refresh_token')
      localStorage.removeItem('login_provider')
      isInitialized.value = false

      if (isDevelopmentMode.value) {
        // Dev mode: cannot logout, just reload
        return
      }

      // Try backend logout (fire and forget)
      try {
        await apiClient.post('/auth/logout')
      } catch {
        // Ignore logout API errors
      }

      // Azure AD logout (will redirect to Azure) - only if user logged in via Azure
      if (wasAzureLogin) {
        logger.info('Performing Azure AD logout')
        await msalLogout()
      }
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Logout failed'
      error.value = errorMessage
      logger.error('Logout error', err)
    } finally {
      loading.value = false
    }
  }

  async function loadUser(): Promise<boolean> {
    if (!accessToken.value) return false

    try {
      const response = await apiClient.get('/auth/me')
      user.value = response.data
      return true
    } catch (err) {
      logger.error('Failed to load user', err)
      await logoutUser()
      return false
    }
  }

  async function refreshAccessToken(): Promise<string | null> {
    try {
      if (!refreshToken.value) {
        logger.warn('No refresh token available')
        return null
      }

      const response = await apiClient.post('/auth/refresh', {
        refresh_token: refreshToken.value
      })

      accessToken.value = response.data.access_token
      refreshToken.value = response.data.refresh_token
      localStorage.setItem('dapnodered_access_token', response.data.access_token)
      localStorage.setItem('dapnodered_refresh_token', response.data.refresh_token)

      logger.info('Token refreshed successfully')
      return response.data.access_token
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to refresh access token'
      error.value = errorMessage
      logger.error('Token refresh error', err)
      return null
    }
  }

  async function ensureAuthenticated() {
    if (!isInitialized.value) {
      await initialize()
    }

    if (!isAuthenticated.value && !isDevelopmentMode.value) {
      await login()
    }
  }

  function clearError() {
    error.value = null
  }

  // Dev Mode: Switch role
  function switchDevRole(role: DevRole) {
    if (isDevelopmentMode.value) {
      devRole.value = role
      localStorage.setItem('dev_role', role)
      logger.info(`Dev Mode: Switched to role: ${role}`, { role })
    }
  }

  // Role check helpers
  function hasRole(role: string): boolean {
    return currentRoles.value.includes(role as LocalRole)
  }

  function hasAnyRole(roles: string[]): boolean {
    return roles.some(role => hasRole(role))
  }

  // Legacy aliases
  const logout = logoutUser
  const authMode = computed(() => authConfig.value?.mode === 'development' ? 'dev' : 'production')

  return {
    // State
    authConfig,
    authMode,  // legacy compat
    account,
    user,
    isInitialized,
    accessToken,
    refreshToken,
    loading,
    error,
    devRole,
    loginProvider,
    isPasswordlessSession,
    // Computed
    isDevelopmentMode,
    isProductionMode,
    isAuthenticated,
    currentRoles,
    userInfo,
    isAdmin,
    userName,
    userEmail,
    // Actions
    initialize,
    login,
    loginWithMasterPassword,
    loginWithPassword,
    loginPasswordless,
    continueAsUser,
    logout,
    logoutUser,
    loadUser,
    refreshAccessToken,
    ensureAuthenticated,
    clearError,
    switchDevRole,
    hasRole,
    hasAnyRole,
  }
})
