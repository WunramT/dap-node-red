/**
 * Azure AD Authentication Service using MSAL
 * Handles authentication flow with Microsoft Entra ID
 */
import {
  PublicClientApplication,
  AccountInfo,
  AuthenticationResult,
  InteractionRequiredAuthError,
  SilentRequest,
  RedirectRequest,
  PopupRequest,
} from '@azure/msal-browser'
import { logger } from '@/services/logger'
import type { AuthConfig, AppMode } from '@/types/common'
import apiClient from '@/api/client'

// App Roles type definition
export type AppRole = 'Admin' | 'User'

// Local role names (matching backend)
export type LocalRole = 'admin' | 'user'

// Azure AD role to local role mapping
const ROLE_MAPPING: Record<AppRole, LocalRole> = {
  'Admin': 'admin',
  'User': 'user',
}

// Auth config cached value
let cachedAuthConfig: AuthConfig | null = null

/**
 * Fetch full authentication configuration from backend (/auth/config).
 */
export async function fetchAuthConfig(): Promise<AuthConfig> {
  if (cachedAuthConfig) {
    return cachedAuthConfig
  }

  try {
    const response = await apiClient.get<AuthConfig>('/auth/config')
    cachedAuthConfig = response.data
    return cachedAuthConfig
  } catch (error) {
    logger.error('Failed to fetch auth config, falling back to development mode', error)
    // Safe fallback – treat as development mode so the app still starts
    cachedAuthConfig = {
      mode: 'development',
      providers: { azure: false, local_db: false, master_pw: false },
      passwordless: false,
      available_roles: ['admin', 'user'],
    }
    return cachedAuthConfig
  }
}

/** @deprecated Use fetchAuthConfig instead */
export async function fetchAuthMode(): Promise<string> {
  const cfg = await fetchAuthConfig()
  return cfg.mode === 'development' ? 'dev' : 'production'
}

/**
 * Get cached auth config (returns null if not fetched yet)
 */
export function getCachedAuthConfig(): AuthConfig | null {
  return cachedAuthConfig
}

/** @deprecated Use getCachedAuthConfig instead */
export function getCachedAuthMode(): string | null {
  const cfg = cachedAuthConfig
  if (!cfg) return null
  return cfg.mode === 'development' ? 'dev' : 'production'
}

/**
 * Check if in development mode
 */
export function isDevMode(mode?: AppMode | string): boolean {
  if (mode) return mode === 'development' || mode === 'dev'
  return cachedAuthConfig?.mode === 'development'
}

/**
 * Check if a specific provider is active
 */
export function isProviderActive(provider: 'azure' | 'local_db' | 'master_pw'): boolean {
  return cachedAuthConfig?.providers[provider] ?? false
}

/**
 * Check if passwordless mode is active
 */
export function isPasswordlessActive(): boolean {
  return cachedAuthConfig?.passwordless ?? false
}

/** @deprecated Use isProviderActive('master_pw') */
export function isPasswordOnlyMode(mode?: string): boolean {
  return isProviderActive('master_pw')
}

/** @deprecated Use isProviderActive('local_db') */
export function isLocalMode(mode?: string): boolean {
  return isProviderActive('local_db')
}

/** @deprecated Use isProviderActive('azure') */
export function isEntraIdMode(mode?: string): boolean {
  return isProviderActive('azure')
}

/**
 * Check if authentication is enabled (any non-dev setup)
 * @deprecated Use specific provider checks instead
 */
export function isAuthEnabled(): boolean {
  return !isDevMode()
}

// MSAL Configuration
// Dynamic redirect URI detection for reverse proxy deployment
const getRedirectUri = (): string => {
  const origin = window.location.origin
  const basePath = import.meta.env.BASE_URL || '/'

  // Use the base path from Vite configuration
  // This is set at build time via VITE_BASE_PATH and replaced at runtime
  // - Dev: '/' -> redirects to /auth/callback
  // - Prod: '/app/xxx/' -> redirects to /app/xxx/auth/callback
  const redirectPath = basePath.endsWith('/') ? `${basePath}auth/callback` : `${basePath}/auth/callback`
  return `${origin}${redirectPath}`
}

const msalConfig = {
  auth: {
    clientId: import.meta.env.VITE_AZURE_CLIENT_ID || '',
    authority: `https://login.microsoftonline.com/${import.meta.env.VITE_AZURE_TENANT_ID || 'common'}`,
    redirectUri: getRedirectUri(),
  },
  cache: {
    cacheLocation: 'localStorage' as const,
    storeAuthStateInCookie: true,
  },
}

// Scopes for API access
const loginRequest: RedirectRequest = {
  scopes: [`api://${import.meta.env.VITE_AZURE_CLIENT_ID}/User_Read`],
}

// Create MSAL instance
let msalInstance: PublicClientApplication | null = null

/**
 * Initialize MSAL instance
 * Must be called before using any auth functions
 */
export async function initializeMsal(): Promise<PublicClientApplication> {
  if (msalInstance) {
    return msalInstance
  }

  msalInstance = new PublicClientApplication(msalConfig)
  await msalInstance.initialize()

  // Handle redirect promise (important for callback handling)
  await msalInstance.handleRedirectPromise()

  return msalInstance
}

/**
 * Get MSAL instance
 * Returns null if not initialized
 */
export function getMsalInstance(): PublicClientApplication | null {
  return msalInstance
}

/**
 * Get current authenticated account
 */
export function getCurrentAccount(): AccountInfo | null {
  if (!msalInstance) return null

  const accounts = msalInstance.getAllAccounts()
  if (accounts.length === 0) return null

  return accounts[0]
}

/**
 * Check if user is authenticated
 */
export function isAuthenticated(): boolean {
  if (isDevMode()) return true // Dev mode: always authenticated

  const account = getCurrentAccount()
  return account !== null
}

/**
 * Login with redirect
 * User will be redirected to Azure AD login page
 */
export async function loginRedirect(): Promise<void> {
  if (!msalInstance) {
    throw new Error('MSAL not initialized. Call initializeMsal() first.')
  }

  await msalInstance.loginRedirect(loginRequest)
}

/**
 * Login with popup
 * Opens Azure AD login in a popup window
 */
export async function loginPopup(): Promise<AuthenticationResult> {
  if (!msalInstance) {
    throw new Error('MSAL not initialized. Call initializeMsal() first.')
  }

  const request: PopupRequest = {
    ...loginRequest,
  }

  return await msalInstance.loginPopup(request)
}

/**
 * Logout
 * Clears all tokens and redirects to Azure AD logout page
 */
export async function logout(): Promise<void> {
  if (!msalInstance) return

  const account = getCurrentAccount()
  if (!account) return

  await msalInstance.logoutRedirect({
    account: account,
  })
}

/**
 * Get access token silently
 * Uses refresh token to get new access token without user interaction
 */
export async function getAccessTokenSilent(): Promise<string | null> {
  if (isDevMode()) {
    // Dev mode: return mock token
    return 'dev-mock-token'
  }

  if (!msalInstance) {
    throw new Error('MSAL not initialized')
  }

  const account = getCurrentAccount()
  if (!account) {
    throw new Error('No active account. Please login first.')
  }

  const request: SilentRequest = {
    ...loginRequest,
    account: account,
  }

  try {
    const response = await msalInstance.acquireTokenSilent(request)
    return response.accessToken
  } catch (error) {
    logger.warn('Silent token acquisition failed', error)

    if (error instanceof InteractionRequiredAuthError ||
        (error instanceof Error && error.name === 'BrowserAuthError')) {
      logger.info('Redirecting to interactive login due to auth error')
      await loginRedirect()
      return null
    }
    throw error
  }
}

/**
 * Get access token with fallback to interactive login
 */
export async function getAccessToken(): Promise<string | null> {
  try {
    return await getAccessTokenSilent()
  } catch (error) {
    logger.error('Failed to get access token', error)
    return null
  }
}

/**
 * Get user information from account
 */
export function getUserInfo(): {
  email: string
  name: string
  username: string
} | null {
  if (isDevMode()) {
    // Dev mode: return mock user
    return {
      email: 'dev@localhost',
      name: 'Dev User',
      username: 'dev@localhost',
    }
  }

  const account = getCurrentAccount()
  if (!account) return null

  return {
    email: account.username || '',
    name: account.name || '',
    username: account.username || '',
  }
}

/**
 * Handle redirect callback
 * Call this in the callback route component
 */
export async function handleRedirectCallback(): Promise<AuthenticationResult | null> {
  if (!msalInstance) {
    throw new Error('MSAL not initialized')
  }

  const response = await msalInstance.handleRedirectPromise()
  return response
}

/**
 * Get ID token claims
 * Contains user roles and other claims from Azure AD
 */
export function getIdTokenClaims(): Record<string, unknown> | null {
  const account = getCurrentAccount()
  if (!account) return null

  return account.idTokenClaims as Record<string, unknown>
}

/**
 * Get roles from token claims
 * Returns local role names (mapped from Azure App Roles)
 */
export function getRolesFromClaims(): LocalRole[] {
  if (isDevMode()) {
    // Dev mode: roles handled by store
    return []
  }

  const claims = getIdTokenClaims()
  if (!claims) return []
  if (!claims.roles) return ['user']

  const azureRoles = claims.roles as string[]
  const localRoles: LocalRole[] = []

  for (const azureRole of azureRoles) {
    const mapped = ROLE_MAPPING[azureRole as AppRole]
    if (mapped) {
      localRoles.push(mapped)
    }
  }

  return localRoles.length > 0 ? localRoles : ['user']
}

/**
 * Check if user has specific role
 */
export function hasRole(roleName: LocalRole): boolean {
  if (isDevMode()) {
    return true
  }

  const roles = getRolesFromClaims()
  return roles.includes(roleName)
}

/**
 * Check if user is admin
 */
export function isAdmin(): boolean {
  return hasRole('admin')
}

export default {
  initializeMsal,
  getMsalInstance,
  isAuthEnabled,
  getCurrentAccount,
  isAuthenticated,
  loginRedirect,
  loginPopup,
  logout,
  getAccessToken,
  getAccessTokenSilent,
  getUserInfo,
  handleRedirectCallback,
  getIdTokenClaims,
  getRolesFromClaims,
  hasRole,
  isAdmin,
}
