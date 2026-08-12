"""
FastAPI main application.
"""
import logging

import sentry_sdk
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from contextlib import asynccontextmanager

from app.config import settings
from app.api.v1.router import api_router
from app.core.logging import setup_logging, get_logger
from app.core.middleware import RequestContextMiddleware
from app.core.socket_manager import get_socket_manager
from app.services.scheduler_service import get_scheduler_service

# Setup logging first (before any other initialization)
setup_logging()

logger = get_logger(__name__)


def init_sentry() -> None:
    """Initialize Sentry SDK for error tracking and performance monitoring."""
    if not settings.sentry_dsn:
        logger.info("Sentry DSN not configured, skipping Sentry initialization")
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        release=f"dapnodered-backend@{settings.app_version}",
        traces_sample_rate=settings.sentry_traces_sample_rate,
        profiles_sample_rate=settings.sentry_profiles_sample_rate,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR,
            ),
        ],
        send_default_pii=False,
        enable_tracing=True,
        attach_stacktrace=True,
    )
    logger.info(
        f"Sentry initialized: environment={settings.sentry_environment}, "
        f"release=dapnodered-backend@{settings.app_version}"
    )


# Initialize Sentry before creating the app
init_sentry()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Application mode: {settings.mode}")
    logger.info(f"Sentry environment: {settings.sentry_environment}")
    logger.info("Documentation available at: /api/docs")
    logger.info("Socket.IO available at: /socket.io/")

    # Initialize database with default roles
    from app.database import AsyncSessionLocal
    from app.crud import role as role_crud
    from app.crud import person as person_crud

    async with AsyncSessionLocal() as db:
        await role_crud.get_or_create_default_roles(db)
        logger.info("Default roles initialized")

        if settings.is_development:
            # Seed development users so Swagger UI is usable out-of-the-box
            await person_crud.create_seed_users_for_dev(db)
            logger.info("Development seed users initialized")
        else:
            # Production: ensure system users exist for master_pw / passwordless
            if settings.auth_provider_master_pw or settings.user_passwordless:
                await person_crud.ensure_default_users_exist(db)
                logger.info("System users for master_pw/passwordless initialized")

    # Start the scheduler service
    scheduler = get_scheduler_service()
    await scheduler.start()

    yield  # ── Application runs ──────────────────────────────────────────────

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("Shutting down application...")
    await scheduler.shutdown()

# Create FastAPI application instance
fastapi_app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A modern FastAPI application template with Vue.js frontend and PostgreSQL database",
    root_path=settings.root_path,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    debug=settings.debug,
    lifespan=lifespan
)

# Configure CORS middleware with explicit allowed methods and headers
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Dev-Role", "X-Dev-User-Id"],
)

# Configure Request Context middleware for audit tracking
# This must be added after CORS to ensure proper request/response handling
fastapi_app.add_middleware(RequestContextMiddleware)

logger.info("Request context middleware registered for audit tracking")

# Include API router with /api prefix
fastapi_app.include_router(api_router, prefix="/api")

# Initialize Socket.IO for real-time communication
socket_manager = get_socket_manager()

# Create the combined ASGI app — socketio wraps FastAPI.
# Uvicorn must serve `app`, NOT `fastapi_app`.
app = socketio.ASGIApp(
    socketio_server=socket_manager.sio,
    other_asgi_app=fastapi_app,
    socketio_path="socket.io",
)

logger.info("Socket.IO server mounted, listening on /socket.io")

# Export both for testing purposes
__all__ = ["app", "fastapi_app"]
