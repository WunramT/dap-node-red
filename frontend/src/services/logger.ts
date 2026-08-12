/**
 * Centralized logging service for the frontend.
 *
 * This module provides:
 * - Structured logging with consistent formatting
 * - Integration with Sentry for error tracking
 * - Breadcrumbs for debugging context
 * - Environment-aware logging (verbose in dev, minimal in prod)
 */

import * as Sentry from '@sentry/vue'

type LogLevel = 'debug' | 'info' | 'warn' | 'error'

interface LogContext {
  [key: string]: unknown
}

const isDev = import.meta.env.DEV

/**
 * Format a log message with optional context
 */
function formatMessage(level: LogLevel, message: string, context?: LogContext): string {
  const timestamp = new Date().toISOString()
  const contextStr = context ? ` | ${JSON.stringify(context)}` : ''
  return `[${timestamp}] [${level.toUpperCase()}] ${message}${contextStr}`
}

/**
 * Logger service with Sentry integration
 */
export const logger = {
  /**
   * Log debug information (only in development)
   */
  debug(message: string, context?: LogContext): void {
    if (isDev) {
      console.debug(formatMessage('debug', message, context))
    }
    // Debug logs are not sent to Sentry
  },

  /**
   * Log general information
   * Creates a Sentry breadcrumb for context
   */
  info(message: string, context?: LogContext): void {
    if (isDev) {
      console.log(formatMessage('info', message, context))
    }
    Sentry.addBreadcrumb({
      category: 'app',
      message,
      level: 'info',
      data: context,
    })
  },

  /**
   * Log warnings
   * Creates a Sentry breadcrumb for context
   */
  warn(message: string, context?: LogContext): void {
    console.warn(formatMessage('warn', message, context))
    Sentry.addBreadcrumb({
      category: 'app',
      message,
      level: 'warning',
      data: context,
    })
  },

  /**
   * Log errors and send to Sentry
   * If an Error object is provided, it's captured as an exception
   */
  error(message: string, error?: Error | unknown, context?: LogContext): void {
    console.error(formatMessage('error', message, context), error)

    if (error instanceof Error) {
      Sentry.captureException(error, {
        extra: {
          message,
          ...context,
        },
      })
    } else if (error) {
      Sentry.captureMessage(message, {
        level: 'error',
        extra: {
          error,
          ...context,
        },
      })
    } else {
      Sentry.captureMessage(message, {
        level: 'error',
        extra: context,
      })
    }
  },

  /**
   * Log API request/response for debugging
   */
  api(method: string, url: string, status?: number, context?: LogContext): void {
    const message = `${method} ${url}${status ? ` -> ${status}` : ''}`
    if (isDev) {
      console.log(formatMessage('info', `[API] ${message}`, context))
    }
    Sentry.addBreadcrumb({
      category: 'http',
      message,
      level: status && status >= 400 ? 'error' : 'info',
      data: {
        method,
        url,
        status,
        ...context,
      },
    })
  },

  /**
   * Log user actions for debugging
   */
  action(action: string, context?: LogContext): void {
    if (isDev) {
      console.log(formatMessage('info', `[ACTION] ${action}`, context))
    }
    Sentry.addBreadcrumb({
      category: 'user',
      message: action,
      level: 'info',
      data: context,
    })
  },

  /**
   * Log navigation events
   */
  navigation(from: string, to: string): void {
    const message = `${from} -> ${to}`
    if (isDev) {
      console.log(formatMessage('info', `[NAV] ${message}`))
    }
    Sentry.addBreadcrumb({
      category: 'navigation',
      message,
      level: 'info',
      data: { from, to },
    })
  },

  /**
   * Set user context for Sentry (call after login)
   */
  setUser(user: { id: string; email?: string; username?: string }): void {
    Sentry.setUser(user)
    if (isDev) {
      console.log(formatMessage('info', '[USER] Context set', { userId: user.id }))
    }
  },

  /**
   * Clear user context (call after logout)
   */
  clearUser(): void {
    Sentry.setUser(null)
    if (isDev) {
      console.log(formatMessage('info', '[USER] Context cleared'))
    }
  },

  /**
   * Add a custom tag to all future events
   */
  setTag(key: string, value: string): void {
    Sentry.setTag(key, value)
  },
}

export default logger
