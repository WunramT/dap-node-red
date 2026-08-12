"""
Database fixtures for testing.

Provides isolated database sessions for each test.
Uses the same database and schema as the app with data cleanup between tests.
"""

import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text

from app.config import settings
from app.database import Base

# Use same database and schema as app
# Tables already exist from Alembic migrations
# Priority: TEST_DATABASE_URL > DATABASE_URL > constructed from settings
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    os.environ.get(
        "DATABASE_URL",
        f"postgresql+asyncpg://{settings.database_user}:{settings.database_password}"
        f"@postgres:{settings.database_port}/{settings.database_name}",
    ),
)

# Use the app's schema
APP_SCHEMA = settings.database_schema

# Connection args to set search_path
test_connect_args = {"server_settings": {"search_path": f"{APP_SCHEMA},public"}}

# Create test engine with NullPool to avoid connection issues in tests
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=NullPool,
    connect_args=test_connect_args,
)

# Test session factory
TestAsyncSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# Explicitly set loop_scope="session" on the session-scoped fixture.
# This tells pytest-asyncio that this specific fixture needs a session-scoped event loop.
# Otherwise:
# Your db_engine fixture in tests/fixtures/db.py has scope="session"
# Your pytest.ini sets asyncio_default_fixture_loop_scope = function
# In pytest-asyncio 1.0+, async fixtures cannot have a broader scope than the event loop
@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine():
    """
    Get the test database engine.

    Session-scoped: uses existing schema/tables from Alembic migrations.
    No table creation needed - tables already exist.
    """
    # Just verify connection works
    async with test_engine.begin() as conn:
        await conn.execute(text("SELECT 1"))

    yield test_engine


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create isolated database session for each test.

    Each test gets its own transaction that is rolled back after the test.
    This ensures complete test isolation without actually deleting data.
    """
    # Start a connection
    connection = await test_engine.connect()

    # Begin a transaction first
    transaction = await connection.begin()

    # Set search_path within the transaction
    await connection.execute(text(f"SET search_path TO {APP_SCHEMA}, public"))

    # Create session bound to this transaction
    session = AsyncSession(bind=connection, expire_on_commit=False)

    try:
        yield session
    finally:
        await session.close()
        # Rollback the transaction - all test data disappears
        await transaction.rollback()
        await connection.close()


@pytest_asyncio.fixture(scope="function")
async def db(db_session: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    """
    Alias for db_session for convenience.
    """
    yield db_session


def override_get_db(session: AsyncSession):
    """
    Create a dependency override for get_db.

    Usage in tests:
        app.dependency_overrides[get_db] = override_get_db(db_session)
    """

    async def _override():
        yield session

    return _override
