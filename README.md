# dapnodered

A full-stack web application template built with FastAPI (Python) and Vue.js (TypeScript).

## Features

- **Backend**: FastAPI with async SQLAlchemy, Alembic migrations, PostgreSQL
- **Frontend**: Vue 3 with Vuetify 3, TypeScript, Pinia state management
- **Authentication**: Azure AD (Entra ID) with MSAL, dev mode bypass
- **Error Tracking**: Sentry integration for both backend and frontend
- **Background Jobs**: APScheduler for scheduled tasks
- **Testing**: pytest for backend, Vitest + Playwright for frontend
- **CI/CD**: GitLab CI/CD with multi-stage pipelines
- **DevContainers**: VS Code development containers

## Quick Start

### Prerequisites

- [Podman](https://podman.io/) or Docker
- [Podman Compose](https://github.com/containers/podman-compose) or Docker Compose

### Development Setup

1. **Clone the repository**
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process; .\create-project.ps1 {NAME}                
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your configuration values.

3. **Start the development environment**
   ```bash
   podman compose -f docker-compose.dev.yml up -d
   ```

4. **Access the application**

   Ports are randomized per project to avoid conflicts. Check `docker-compose.dev.yml` for your assigned ports, or run:
   ```bash
   podman compose -f docker-compose.dev.yml ps
   ```

   Default ports (before randomization):
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/api/docs
   - pgAdmin: http://localhost:5052

### Running Tests

**Backend Tests:**
```bash
podman compose -f docker-compose.dev.yml exec backend pytest -v
```

**Frontend Unit Tests:**
```bash
podman compose -f docker-compose.dev.yml exec frontend npm run test:run
```

**E2E Tests:**
```bash
podman compose -f docker-compose.dev.yml exec frontend npm run test:e2e
```

## Project Structure

```
dapnodered/
├── backend/
│   ├── app/
│   │   ├── api/           # API routes and endpoints
│   │   ├── core/          # Auth, security, logging
│   │   ├── crud/          # Database operations
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic schemas
│   │   └── services/      # Business logic services
│   ├── migrations/        # Alembic database migrations
│   └── tests/             # pytest tests
├── frontend/
│   ├── src/
│   │   ├── api/           # API client
│   │   ├── components/    # Vue components
│   │   ├── router/        # Vue Router configuration
│   │   ├── services/      # Auth and logging services
│   │   ├── stores/        # Pinia stores
│   │   ├── styles/        # SCSS styles
│   │   ├── types/         # TypeScript types
│   │   └── views/         # Page components
│   └── tests/             # Playwright E2E tests
├── .devcontainer/         # VS Code DevContainers
├── docker-compose.dev.yml # Development environment
└── .gitlab-ci.yml         # CI/CD pipeline
```

## Development Mode

The application supports a development mode where authentication is disabled. This allows testing different user roles without Azure AD setup.

**Enable Dev Mode:**
- Set `ENABLE_AUTH=false` in `.env`

In dev mode, use the role switcher in the navigation bar to test different user roles.

## Production Deployment

The application supports flexible deployment paths through runtime configuration:

### Base Path Configuration

The frontend can run at any URL path without rebuilding:

- **Root path (dev/testing)**: Set `VITE_BASE_PATH=/` (default)
- **Prefixed path (production)**: Set `VITE_BASE_PATH=/app/myapp/`

**Example Docker Run:**
```bash
# Development - root path
docker run -e VITE_BASE_PATH=/ frontend

# Production - custom prefix
docker run -e VITE_BASE_PATH=/app/myapp/ frontend
```

The build artifact uses a placeholder (`/__VITE_BASE_PATH__/`) that gets replaced at container startup by the entrypoint script, allowing a single build to work for all deployment scenarios.

### Backend Configuration

The backend also supports runtime configuration through environment variables:

- `BACKEND_HOST`: Backend service hostname (default: `backend`)
- `BACKEND_PORT`: Backend service port (default: `8000`)

These are substituted in the nginx configuration at container startup.

## Initial Setup

After creating a new project, configure the remaining placeholders:

```bash
python setup_project.py
```

This interactive script will guide you through setting up:
- Project domain
- Azure AD credentials
- Sentry DSN
- Brand colors
- And more...

## Documentation

- API Documentation: http://localhost:8000/api/docs (when running)

## License

[Your License Here]
