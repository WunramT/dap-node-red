"""
Pytest configuration and shared fixtures for backend tests.

This is the main conftest.py file that provides:
- Async test client for API testing
- Database fixtures
- Authentication mocking
- Common test utilities
"""
import os
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

# Set test environment before importing app
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-32chars!")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("MODE", "production")
os.environ.setdefault("AUTH_PROVIDER_MASTER_PW", "T")#Change depending on project plan

from app.main import app, fastapi_app
from app.api.deps import get_db, get_current_user
from app.models.person import Person

# Import fixtures from fixtures package
from tests.fixtures.db import (
    db_engine,
    db_session,
    db,
    TestAsyncSessionLocal,
    override_get_db,
)
from tests.fixtures.models import (
    test_person,
    admin_person,
    create_test_person,
    create_test_role,
)


# =============================================================================
# HTTP Client Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Create an async HTTP client for API testing.

    Automatically overrides the database dependency to use the test session.
    """
    # Override dependencies on fastapi_app, not the wrapped app
    fastapi_app.dependency_overrides[get_db] = override_get_db(db_session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Clean up overrides
    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authenticated_client(
    db_session: AsyncSession,
    test_person: Person,
) -> AsyncGenerator[AsyncClient, None]:
    """
    Create an async HTTP client with authenticated user.

    The test_person will be returned as the current user for all requests.
    """
    # Override dependencies on fastapi_app
    fastapi_app.dependency_overrides[get_db] = override_get_db(db_session)

    async def override_current_user():
        test_person._dev_role = "user"
        return test_person

    fastapi_app.dependency_overrides[get_current_user] = override_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Clean up overrides
    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def user_client(
    db_session: AsyncSession,
    test_person: Person,
) -> AsyncGenerator[AsyncClient, None]:
    """
    Create an async HTTP client authenticated as a non-admin (regular user).

    Used to verify that admin-only endpoints correctly return 403.
    """
    fastapi_app.dependency_overrides[get_db] = override_get_db(db_session)

    async def override_current_user():
        return test_person

    fastapi_app.dependency_overrides[get_current_user] = override_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_client(
    db_session: AsyncSession,
    admin_person: Person,
) -> AsyncGenerator[AsyncClient, None]:
    """
    Create an async HTTP client with admin user.

    The admin_person will be returned as the current user for all requests.
    This user has admin role and can access all endpoints.
    """
    # Override dependencies on fastapi_app
    fastapi_app.dependency_overrides[get_db] = override_get_db(db_session)

    async def override_current_user():
        # Set admin role for dev mode
        admin_person._dev_role = "admin"
        return admin_person

    fastapi_app.dependency_overrides[get_current_user] = override_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Clean up overrides
    fastapi_app.dependency_overrides.clear()


# =============================================================================
# Test Utilities
# =============================================================================
@pytest.fixture(autouse=True, scope="session")
def _disable_sentry():
    """Disable Sentry during tests to avoid shutdown noise."""
    sentry_sdk.init(dsn=None)
    yield
@pytest.fixture(scope="session")
def event_loop():
    """
    Create a session-scoped event loop for async fixtures.

    Required for session-scoped async fixtures like db_engine.
    """
    import asyncio
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def anyio_backend():
    """Specify asyncio as the async backend."""
    return "asyncio"


# Re-export fixtures for easier imports in test files
__all__ = [
    # Client fixtures
    "async_client",
    "authenticated_client",
    "user_client",
    "admin_client",
    # Database fixtures
    "db_engine",
    "db_session",
    "db",
    # Model fixtures
    "test_person",
    "admin_person",
    # Factory functions
    "create_test_person",
    "create_test_role",
]
