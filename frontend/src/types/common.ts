/**
 * Common types and interfaces for the application
 */

// Application mode
export type AppMode = 'development' | 'production'

// Authentication configuration returned by /auth/config
export interface AuthConfig {
  mode: AppMode
  providers: {
    azure: boolean
    local_db: boolean
    master_pw: boolean
  }
  passwordless: boolean
  available_roles?: string[]  // Only present in development mode
}

// Legacy type kept for backward compatibility
export type AuthMode = 'dev' | 'local' | 'entra_id' | 'password_only'

// Pagination
export interface PaginationParams {
  skip?: number
  limit?: number
  page?: number
  page_size?: number
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  skip: number
  limit: number
}

// Common response types
export interface MessageResponse {
  message: string
}

export interface ErrorResponse {
  detail: string
  error_code?: string
}

// Base timestamp interface
export interface Timestamps {
  created_at: string
  updated_at: string
}

// API Error type
export interface ApiError {
  message: string
  status?: number
  code?: string
  validationErrors?: Record<string, string[]>
}

// User types
export interface User {
  id: string
  email: string
  first_name: string
  last_name: string
  is_active: boolean
  roles: string[]
  created_at?: string
  updated_at?: string
}

// Role types
export interface Role {
  id: string
  name: string
  description?: string
}
