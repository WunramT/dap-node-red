"""
FastAPI dependency injection functions.
"""
from typing import AsyncGenerator, List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.database import AsyncSessionLocal
from app.core.security import decode_access_token
from app.models.person import Person
from app.models.person_role import PersonRole
from app.models.role import Role
from app.config import settings


# Security scheme - auto_error=False allows dev mode to work without token
security = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Database session dependency.

    Yields a database session and ensures it's closed after use.

    Usage:
        @router.get("/users")
        async def list_users(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_dev_role: Optional[str] = Header(None, alias="X-Dev-Role"),
    x_dev_user_id: Optional[str] = Header(None, alias="X-Dev-User-Id"),
    db: AsyncSession = Depends(get_db)
) -> Person:
    """
    Get current authenticated user from JWT token or development mode.

    In development mode (MODE="development"):
    - Returns a user from the database based on X-Dev-User-Id header
    - Falls back to first active user if no header provided
    - Uses X-Dev-Role header to determine the role for filtering (optional)

    In production modes (MODE="production"):
    - Validates JWT token and returns the authenticated user

    Args:
        credentials: HTTP Authorization header with Bearer token
        x_dev_role: Optional header for development mode role selection
        x_dev_user_id: Optional header for development mode user selection (UUID)
        db: Database session

    Returns:
        Person object of authenticated user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    # Dev mode: return mock user without authentication
    if settings.is_development:
        dev_user = None

        # If X-Dev-User-Id is provided, use that specific user
        if x_dev_user_id:
            try:
                user_id = UUID(x_dev_user_id)
                stmt = (
                    select(Person)
                    .where(Person.id == user_id)
                    .where(Person.is_active == True)
                    .where(Person.deleted_at.is_(None))
                )
                result = await db.execute(stmt)
                dev_user = result.scalar_one_or_none()
            except (ValueError, Exception):
                pass  # Invalid UUID, fall through to default

        # Fallback: Get the first active user from database
        if not dev_user:
            stmt = (
                select(Person)
                .where(Person.is_active == True)
                .where(Person.deleted_at.is_(None))
                .limit(1)
            )
            result = await db.execute(stmt)
            dev_user = result.scalar_one_or_none()

        if not dev_user:
            # Create a minimal mock person if none exists
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No active users found in database for dev mode. Please run migrations with seed data.",
            )

        # Store the dev role in the user object for later use
        # This allows the endpoint to know which role to use for filtering
        dev_user._dev_role = x_dev_role or settings.dev_user_role  # type: ignore

        return dev_user

    # Production mode: require valid token
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    person_id = payload.get("sub")
    if not person_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Query person with roles
    stmt = (
        select(Person)
        .where(Person.id == UUID(person_id))
        .where(Person.is_active == True)
        .where(Person.deleted_at.is_(None))
    )

    result = await db.execute(stmt)
    person = result.scalar_one_or_none()

    if not person:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return person


async def get_current_user_roles(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[str]:
    """
    Get roles of current authenticated user.

    In development mode, uses the X-Dev-Role header to determine the role.
    This allows testing different role-based access without changing users.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of role names
    """
    # Development mode: use role from header
    if settings.is_development:
        dev_role = getattr(current_user, '_dev_role', settings.dev_user_role)
        # Map role names to local role names
        role_mapping = {
            'Admin': 'admin',
            'User': 'user',
            # Also accept lowercase versions
            'admin': 'admin',
            'user': 'user',
        }
        mapped_role = role_mapping.get(dev_role, 'admin')
        return [mapped_role]

    # Production mode: get roles from database
    stmt = (
        select(Role)
        .join(PersonRole)
        .where(PersonRole.person_id == current_user.id)
    )

    result = await db.execute(stmt)
    roles = result.scalars().all()

    return [role.name for role in roles]


def require_roles(required_roles: List[str]):
    """
    Dependency factory for role-based access control.

    Args:
        required_roles: List of role names that are allowed

    Returns:
        Dependency function that checks for required roles

    Usage:
        @router.get("/admin/users")
        async def admin_users(user: Person = Depends(require_roles(["admin"]))):
            ...
    """
    async def role_checker(
        current_user: Person = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> Person:
        user_roles = await get_current_user_roles(current_user, db)

        if not any(role in user_roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )

        return current_user

    return role_checker


# Helper dependencies for common role requirements
async def require_admin(
    current_user: Person = Depends(require_roles(["admin"]))
) -> Person:
    """Require admin role."""
    return current_user
