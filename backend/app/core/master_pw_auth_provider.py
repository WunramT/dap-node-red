"""
Master-password authentication provider.

Supports two authentication levels:
- Admin access: Requires password validation against MASTER_PASSWORD_ADMIN env var
- User access:  Optionally validates against MASTER_PASSWORD_USER env var
"""
from typing import Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth_provider import AuthProvider
from app.config import settings


class MasterPasswordAuthProvider(AuthProvider):
    """
    Master-password authentication provider.

    Checks a single plain-text password against the configured
    MASTER_PASSWORD_ADMIN (→ role admin) and, optionally,
    MASTER_PASSWORD_USER (→ role user).
    The actual Person records are the generic system users
    (admin@dev.com / user@dev.com) that are seeded at startup.
    """

    def __init__(self, db: AsyncSession):
        super().__init__(db)

    async def authenticate(self, credentials: Dict[str, Any]):
        """
        Authenticate via master password.

        Args:
            credentials: Dict with 'password' key (plain text).

        Returns:
            Person object for admin or user role, or None on failure.
        """
        password = credentials.get("password", "")

        # Try admin password first
        if password and password == settings.master_password_admin:
            return await self._get_person_by_role("admin")

        # Try optional user password
        if password and settings.master_password_user and password == settings.master_password_user:
            return await self._get_person_by_role("user")

        return None

    async def _get_person_by_role(self, role_name: str):
        """Return the first active person that has the given role."""
        from app.models.person import Person
        from app.models.role import Role
        from app.models.person_role import PersonRole

        stmt = (
            select(Person)
            .join(PersonRole, PersonRole.person_id == Person.id)
            .join(Role, Role.id == PersonRole.role_id)
            .where(Role.name == role_name)
            .where(Person.is_active)
            .where(Person.deleted_at.is_(None))
            .options(selectinload(Person.roles))
            .limit(1)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_roles(self, person) -> List[str]:
        """Get roles for the authenticated person."""
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
        return False
