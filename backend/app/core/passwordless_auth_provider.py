"""
Passwordless authentication provider.

Grants every visitor the role "user" without requiring any credentials.
A JWT with provider=passwordless is issued automatically.
"""
from typing import Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth_provider import AuthProvider


class PasswordlessAuthProvider(AuthProvider):
    """
    Passwordless authentication provider.

    Returns the first active person with the "user" role.
    If no such person exists the caller should ensure that
    seed users have been created at startup.
    """

    def __init__(self, db: AsyncSession):
        super().__init__(db)

    async def authenticate(self, credentials: Dict[str, Any]):
        """
        Authenticate without any credentials – returns the default user.

        Args:
            credentials: Not used; accepted for interface compatibility.

        Returns:
            Person object with role "user", or None if not found.
        """
        from app.models.person import Person
        from app.models.role import Role
        from app.models.person_role import PersonRole

        stmt = (
            select(Person)
            .join(PersonRole, PersonRole.person_id == Person.id)
            .join(Role, Role.id == PersonRole.role_id)
            .where(Role.name == "user")
            .where(Person.is_active)
            .where(Person.deleted_at.is_(None))
            .options(selectinload(Person.roles))
            .limit(1)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_roles(self, person) -> List[str]:
        """Return roles for the authenticated person."""
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
