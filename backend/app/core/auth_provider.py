"""
Abstract authentication provider interface for supporting multiple auth methods.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession


class AuthProvider(ABC):
    """
    Abstract authentication provider interface.

    This allows for easy switching between different authentication methods
    (local, Entra ID, OAuth, etc.) by implementing this interface.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the auth provider with a database session.

        Args:
            db: AsyncSession for database operations
        """
        self.db = db

    @abstractmethod
    async def authenticate(self, credentials: Dict[str, Any]):
        """
        Authenticate user and return Person object.

        Args:
            credentials: Dictionary containing authentication credentials
                        (e.g., email/password for local, token for OAuth)

        Returns:
            Person object if authentication successful, None otherwise
        """
        pass

    @abstractmethod
    async def get_user_roles(self, person):
        """
        Get roles for authenticated person.

        Args:
            person: Person object to get roles for

        Returns:
            List of Role objects assigned to the person
        """
        pass

    @abstractmethod
    async def supports_registration(self) -> bool:
        """
        Check if this provider supports user registration.

        Returns:
            True if registration is supported, False otherwise
        """
        pass
