# Multi-stage build for production
FROM python:3.13-slim AS builder

WORKDIR /app


# Install build dependencies for compiling Python packages from source
# Python 3.13 is new and many packages lack prebuilt wheels, requiring compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    # Build essentials - Complete toolchain for compiling packages
    build-essential \
    # PostgreSQL development headers - Required for psycopg2/psycopg compilation
    libpq-dev \
    # Foreign Function Interface library - Required for cryptography package
    libffi-dev \
    # OpenSSL development headers - Required for cryptography and SSL support
    libssl-dev \
    # Rust toolchain - Required for cryptography v46+ (uses Rust backend)
    cargo \
    rustc \
    # Version control for package installations from git if needed
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.13-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 appuser

# Copy Python packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY backend/ .

# Set environment variables
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Change ownership to non-root user
RUN chown -R appuser:appuser /app

USER appuser

# Expose port (FastAPI convention: 8000)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Run application with uvicorn (ASGI server)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
