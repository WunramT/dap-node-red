"""
CRUD operations for Role model.
"""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import Role, RoleEnum


async def get_by_name(db: AsyncSession, name: str) -> Optional[Role]:
    """
    Get role by name.

    Args:
        db: Database session
        name: Role name

    Returns:
        Role object if found, None otherwise
    """
    stmt = select(Role).where(Role.name == name)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_or_create_default_roles(db: AsyncSession) -> None:
    """
    Create default roles (ADMIN, USER) if they don't exist.

    This is called on application startup to ensure
    the default roles are always available.

    Args:
        db: Database session
    """
    for role_enum in RoleEnum:
        existing_role = await get_by_name(db, role_enum.value)
        
        if not existing_role:
            # Create the role
            new_role = Role(
                name=role_enum.value,
                description=f"Default {role_enum.value} role"
            )
            db.add(new_role)
    
    await db.commit()
