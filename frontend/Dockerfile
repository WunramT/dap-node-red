# Multi-stage build for production

# Build stage
FROM node:25-alpine AS builder

WORKDIR /app

# Build arguments for Vite environment variables
# These are embedded at build time, not runtime!
ARG AUTH_PROVIDER=local
ARG VITE_AZURE_CLIENT_ID=
ARG VITE_AZURE_TENANT_ID=
ARG VITE_SENTRY_DSN=
ARG VITE_SENTRY_ENVIRONMENT='__SENTRY_ENVIRONMENT__'
ARG VITE_APP_VERSION=1.0.0
ARG VITE_BASE_PATH='/__VITE_BASE_PATH__/'
ARG VITE_ENABLE_AUTH
ARG MODE=production

# Set as environment variables for the build process
ENV VITE_ENABLE_AUTH=$VITE_ENABLE_AUTH
ENV VITE_AZURE_CLIENT_ID=$VITE_AZURE_CLIENT_ID
ENV VITE_AZURE_TENANT_ID=$VITE_AZURE_TENANT_ID
ENV VITE_SENTRY_DSN=$VITE_SENTRY_DSN
ENV VITE_SENTRY_ENVIRONMENT=$VITE_SENTRY_ENVIRONMENT
ENV VITE_APP_VERSION=$VITE_APP_VERSION
ENV VITE_BASE_PATH=$VITE_BASE_PATH
ENV VITE_ENABLE_AUTH=$VITE_ENABLE_AUTH
ENV NODE_ENV=production

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
# Fix for Rollup optional dependencies on Alpine Linux (npm bug #4828)
RUN rm -f package-lock.json && \
    npm install && \
    npm rebuild

# Copy source code
COPY frontend/ .

# Build application (uses VITE_* env vars)
RUN npm run build

# Production stage
FROM nginx:1.30-alpine

# Copy built files from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Install gettext for envsubst (environment variable substitution)
RUN apk add --no-cache gettext

COPY frontend/entrypoint.sh /docker-entrypoint-custom.sh
RUN chmod +x /docker-entrypoint-custom.sh

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

# Use custom entrypoint
CMD ["/docker-entrypoint-custom.sh"]