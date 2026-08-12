#!/bin/bash
set -e

# Wait for database to be ready
echo "Waiting for PostgreSQL..."
while ! pg_isready -h ${DATABASE_HOST:-postgres} -p ${DATABASE_PORT:-5432} -U ${DATABASE_USER:-dev_user} > /dev/null 2>&1; do
    sleep 1
done
echo "PostgreSQL is ready!"

# Run database migrations
echo "Running database migrations..."
alembic -c /app/migrations/alembic.ini upgrade head

# Set AUTH_PROVIDER based on mode
if [ "$MODE" = "production" ]; then
    export AUTH_PROVIDER="local"
else
    echo "Seeding development data..."
    python /app/scripts/seed_dev_data.py
fi

# Start application based on MODE environment variable
MODE=${MODE:-development}

if [ "$MODE" = "production" ]; then
    echo "Starting in production mode with uvicorn..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
else
    echo "Starting in development mode with auto-reload..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
fi
