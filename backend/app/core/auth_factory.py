"""
Authentication provider factory for selecting the appropriate auth provider(s).
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_provider import AuthProvider
from app.core.local_auth_provider import LocalAuthProvider
from app.config import settings


def get_auth_provider(db: AsyncSession, provider_name: Optional[str] = None) -> Optional[AuthProvider]:
    """
    Get a specific authentication provider by name.

    In development mode this always returns None (no provider needed).

    Args:
        db: AsyncSession for database operations
        provider_name: One of "azure", "local_db", "master_pw", "passwordless".
                       When None, returns the first active provider (legacy behaviour).

    Returns:
        AuthProvider instance, or None for development mode / no match.

    Raises:
        ValueError: If an unknown provider name is requested.
    """
    if settings.is_development:
        # Development mode: authentication is handled by the role switcher
        return None

    if provider_name is None:
        # Legacy: return the first active provider
        if settings.auth_provider_local_db:
            return LocalAuthProvider(db)
        if settings.auth_provider_azure:
            from app.core.entra_auth_provider import EntraAuthProvider
            return EntraAuthProvider(db)
        if settings.auth_provider_master_pw:
            from app.core.master_pw_auth_provider import MasterPasswordAuthProvider
            return MasterPasswordAuthProvider(db)
        if settings.user_passwordless:
            from app.core.passwordless_auth_provider import PasswordlessAuthProvider
            return PasswordlessAuthProvider(db)
        return None

    if provider_name == "local_db":
        if not settings.auth_provider_local_db:
            raise ValueError("AUTH_PROVIDER_LOCAL_DB is not enabled")
        return LocalAuthProvider(db)

    if provider_name == "azure":
        if not settings.auth_provider_azure:
            raise ValueError("AUTH_PROVIDER_AZURE is not enabled")
        from app.core.entra_auth_provider import EntraAuthProvider
        return EntraAuthProvider(db)

    if provider_name == "master_pw":
        if not settings.auth_provider_master_pw:
            raise ValueError("AUTH_PROVIDER_MASTER_PW is not enabled")
        from app.core.master_pw_auth_provider import MasterPasswordAuthProvider
        return MasterPasswordAuthProvider(db)

    if provider_name == "passwordless":
        if not settings.user_passwordless:
            raise ValueError("USER_PASSWORDLESS is not enabled")
        from app.core.passwordless_auth_provider import PasswordlessAuthProvider
        return PasswordlessAuthProvider(db)

    raise ValueError(f"Unknown provider name: {provider_name}")

