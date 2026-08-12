/**
 * MSW Server Setup
 * Used for mocking API requests in unit tests
 */
import { setupServer } from 'msw/node'
import { handlers } from './handlers'

export const server = setupServer(...handlers)
