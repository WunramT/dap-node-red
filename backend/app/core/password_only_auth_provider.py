"""
Password-only authentication provider for simple deployments.

This provider supports two user types:
- Admin: Requires password authentication
- User: No password required (automatic access)
"""
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth_provider import AuthProvider
from app.core.security import verify_password
from app.config import settings


class PasswordOnlyAuthProvider(AuthProvider):
    """
    Password-only authentication provider.

    Supports two authentication modes:
    1. Admin access: Requires password validation against ADMIN_PASSWORD env var
    2. User access: No password required, grants default user role
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize password-only auth provider.

        Args:
            db: AsyncSession for database operations
        """
        super().__init__(db)

    async def authenticate(self, credentials: Dict[str, Any]):
        """
        Authenticate user based on role and optional password.

        For admin role: validates password against ADMIN_PASSWORD
        For user role: no password required, returns default user

        Args:
            credentials: Dict with 'role' and optional 'password' keys

        Returns:
            Person object if authentication successful, None otherwise
        """
        from app.models.person import Person

        role = credentials.get("role", "user")
        password = credentials.get("password")

        if role == "admin":
            # Admin requires password
            if not password:
                return None

            # Verify against configured admin password
            if password != settings.admin_password:
                return None

            # Get admin user
            stmt = (
                select(Person)
                .where(Person.email == "admin@polipol.de")
                .where(Person.is_active == True)
                .where(Person.deleted_at.is_(None))
                .options(selectinload(Person.roles))
            )

        else:
            # User role - no password required
            stmt = (
                select(Person)
                .where(Person.email == "user@polipol.de")
                .where(Person.is_active == True)
                .where(Person.deleted_at.is_(None))
                .options(selectinload(Person.roles))
            )

        result = await self.db.execute(stmt)
        person = result.scalar_one_or_none()

        return person

    async def get_user_roles(self, person) -> List[str]:
        """
        Get roles for authenticated person.

        Args:
            person: Person object

        Returns:
            List of role names
        """
        from app.models.person_role import PersonRole
        from app.models.role import Role

        stmt = (
            select(Role)
            .join(PersonRole)
            .where(PersonRole.person_id == person.id)
        )

        result = await self.db.execute(stmt)
        roles = result.scalars().all()

        return [role.name for role in roles]

    async def supports_registration(self) -> bool:
        """
        Check if this provider supports user registration.

        Returns:
            False - password-only mode does not support user registration
        """
        return False
