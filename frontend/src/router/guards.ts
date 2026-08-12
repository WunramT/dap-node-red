import type { NavigationGuardNext, RouteLocationNormalized } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { logger } from '@/services/logger'

export async function authGuard(
  to: RouteLocationNormalized,
  _from: RouteLocationNormalized,
  next: NavigationGuardNext
) {
  const authStore = useAuthStore()

  // Initialize auth store if not already initialized
  try {
    if (!authStore.isInitialized) {
      await authStore.initialize()
    }
  } catch (err) {
    logger.error('Auth initialization failed in guard', err)
    // Clear stale tokens and trigger re-login
    localStorage.removeItem('dapnodered_access_token')
    localStorage.removeItem('dapnodered_refresh_token')
    if (!authStore.isDevelopmentMode) {
      await authStore.login()
      return
    }
  }

  // Allow access to public routes
  if (!to.meta.requiresAuth) {
    return next()
  }

  // Development mode: always allow access (roles handled by store)
  if (authStore.isDevelopmentMode) {
    // Check role requirements even in dev mode
    if (to.meta.requiresRoles) {
      const requiredRoles = to.meta.requiresRoles as string[]
      const hasRequiredRole = authStore.hasAnyRole(requiredRoles)

      if (!hasRequiredRole) {
        return next({ name: 'unauthorized' })
      }
    }
    return next()
  }

  // Production mode: check authentication
  if (to.meta.requiresAuth) {
    // Passwordless: visitors are always "authenticated" as user
    if (authStore.isAuthenticated) {
      // Check role requirements
      if (to.meta.requiresRoles) {
        const requiredRoles = to.meta.requiresRoles as string[]
        const hasRequiredRole = authStore.hasAnyRole(requiredRoles)

        if (!hasRequiredRole) {
          return next({ name: 'unauthorized' })
        }
      }
      return next()
    }

    // Not authenticated – try to load user from stored token
    if (!authStore.isAuthenticated && authStore.accessToken) {
      const loaded = await authStore.loadUser()
      if (!loaded) {
        return next({ name: 'login' })
      }
    }

    // Still not authenticated → redirect to login
    if (!authStore.isAuthenticated) {
      const config = authStore.authConfig
      if (config?.providers.azure) {
        await authStore.login()
        return
      }
      return next({ name: 'login' })
    }

    // Check role requirements
    if (to.meta.requiresRoles) {
      const requiredRoles = to.meta.requiresRoles as string[]
      const hasRequiredRole = authStore.hasAnyRole(requiredRoles)

      if (!hasRequiredRole) {
        return next({ name: 'unauthorized' })
      }
    }
  }

  next()
}
