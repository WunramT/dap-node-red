/**
 * MSW Request Handlers
 * Define mock API responses for testing
 */
import { http, HttpResponse } from 'msw'

export const handlers = [
  // Health check endpoint
  http.get('/api/health', () => {
    return HttpResponse.json({
      status: 'healthy',
      database: 'connected',
      environment: 'test',
      version: '1.0.0',
    })
  }),

  // Auth me endpoint
  http.get('/api/auth/me', () => {
    return HttpResponse.json({
      id: 'test-user-id',
      email: 'test@example.com',
      first_name: 'Test',
      last_name: 'User',
      is_active: true,
      roles: ['user'],
    })
  }),

  // Add more handlers as needed
]
