import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { authGuard } from './guards'

/**
 * Get the router base path from Vite's BASE_URL.
 * This is set at build time via VITE_BASE_PATH environment variable.
 * The placeholder /__VITE_BASE_PATH__/ is replaced at container runtime.
 * - Dev: '/' (default)
 * - Prod: '/app/xxx/' (set via VITE_BASE_PATH environment variable)
 */
const getRouterBasePath = (): string => {
  return import.meta.env.BASE_URL || '/'
}

// Extend RouteMeta to include auth-related fields
declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    requiresAuth?: boolean
    requiresRoles?: string[]
  }
}

const routes: RouteRecordRaw[] = [
  // Public routes
  {
    path: '/auth/callback',
    name: 'AuthCallback',
    component: () => import('@/views/auth/Callback.vue'),
    meta: { title: 'Authentication', requiresAuth: false }
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/components/auth/LoginSelector.vue'),
    meta: { title: 'Anmeldung', requiresAuth: false }
  },
  {
    path: '/unauthorized',
    name: 'unauthorized',
    component: () => import('@/views/Unauthorized.vue'),
    meta: { title: 'Access Denied', requiresAuth: false }
  },

  // Protected routes (require authentication)
  {
    path: '/',
    name: 'home',
    component: () => import('@/components/HomePage.vue'),
    meta: { title: 'Home', requiresAuth: true }
  },

  // Add your routes here
  // Example:
  // {
  //   path: '/dashboard',
  //   name: 'Dashboard',
  //   component: () => import('@/views/DashboardView.vue'),
  //   meta: { title: 'Dashboard', requiresAuth: true }
  // },
  // {
  //   path: '/admin/users',
  //   name: 'AdminUsers',
  //   component: () => import('@/views/admin/UserListView.vue'),
  //   meta: {
  //     title: 'User Management',
  //     requiresAuth: true,
  //     requiresRoles: ['admin']
  //   }
  // },
]

const router = createRouter({
  history: createWebHistory(getRouterBasePath()),
  routes
})

// Auth guard - must come before title guard
router.beforeEach(authGuard)

// Navigation guard to update page title
router.beforeEach((to, from, next) => {
  const title = to.meta.title as string
  if (title) {
    document.title = `${title} | dapnodered`
  }
  next()
})

export default router
