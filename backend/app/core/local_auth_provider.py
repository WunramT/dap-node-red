"""
Local email/password authentication provider.
"""
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth_provider import AuthProvider
from app.core.security import verify_password, get_password_hash


class LocalAuthProvider(AuthProvider):
    """
    Local authentication provider using email/password.

    This provider authenticates users against the local database
    using email and password credentials.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize local auth provider.

        Args:
            db: AsyncSession for database operations
        """
        super().__init__(db)

    async def authenticate(self, credentials: Dict[str, Any]):
        """
        Authenticate user with email and password.

        Args:
            credentials: Dict with 'email' and 'password' keys

        Returns:
            Person object if authentication successful, None otherwise
        """
        from app.models.person import Person

        email = credentials.get("email")
        password = credentials.get("password")

        if not email or not password:
            return None

        # Query person with roles eagerly loaded
        stmt = (
            select(Person)
            .where(Person.email == email)
            .where(Person.is_active == True)
            .where(Person.deleted_at.is_(None))
            .options(selectinload(Person.roles))
        )

        result = await self.db.execute(stmt)
        person = result.scalar_one_or_none()

        if not person or not person.password_hash:
            return None

        # Verify password
        if not verify_password(password, person.password_hash):
            return None

        return person

    async def get_user_roles(self, person) -> List:
        """
        Get roles for authenticated person.

        Args:
            person: Person object

        Returns:
            List of Role names
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
        Local auth supports user registration.

        Returns:
            True (local auth supports registration)
        """
        return True

    async def register_user(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        **kwargs
    ):
        """
        Register a new user with local authentication.

        Args:
            email: User email
            password: Plain text password (will be hashed)
            first_name: User's first name
            last_name: User's last name
            **kwargs: Additional Person fields

        Returns:
            Person object if registration successful, None otherwise
        """
        from app.models.person import Person

        # Check if user already exists
        stmt = select(Person).where(Person.email == email)
        result = await self.db.execute(stmt)
        existing_person = result.scalar_one_or_none()

        if existing_person:
            return None

        # Create new person
        password_hash = get_password_hash(password)

        person = Person(
            email=email,
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
            auth_source="local",
            is_active=True,
            **kwargs
        )

        self.db.add(person)
        await self.db.flush()

        return person
