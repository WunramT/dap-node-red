#!/bin/sh
set -e

# Set defaults
BACKEND_HOST=${BACKEND_HOST:-backend}
BACKEND_PORT=${BACKEND_PORT:-8000}
VITE_BASE_PATH=${VITE_BASE_PATH:-/}
VITE_SENTRY_ENVIRONMENT=${VITE_SENTRY_ENVIRONMENT:-production}

# Substitute variables in nginx config
envsubst '${BACKEND_HOST} ${BACKEND_PORT} ${VITE_BASE_PATH} ${VITE_SENTRY_ENVIRONMENT}' < /etc/nginx/conf.d/default.conf > /etc/nginx/conf.d/default.conf.tmp
mv /etc/nginx/conf.d/default.conf.tmp /etc/nginx/conf.d/default.conf

# Substitute VITE_BASE_PATH and SENTRY_ENVIRONMENT in all static HTML/JS/CSS files
find /usr/share/nginx/html -type f \( -name "*.html" -o -name "*.js" -o -name "*.css" \) -exec sed -i "s|/__VITE_BASE_PATH__/|${VITE_BASE_PATH}|g; s|__SENTRY_ENVIRONMENT__|${VITE_SENTRY_ENVIRONMENT}|g" {} +

# Start nginx
exec nginx -g "daemon off;"