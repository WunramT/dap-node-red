"""
Authentication-related Pydantic schemas.
"""
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, ConfigDict


# Request Schemas
class LoginRequest(BaseModel):
    """Login request with email and password (AUTH_PROVIDER_LOCAL_DB)."""
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    """Request to refresh access token."""
    refresh_token: str


class AzureLoginRequest(BaseModel):
    """Azure AD login request with Azure access token (AUTH_PROVIDER_AZURE)."""
    token: str


class MasterPasswordLoginRequest(BaseModel):
    """Master-password login request (AUTH_PROVIDER_MASTER_PW)."""
    password: str


class PasswordOnlyLoginRequest(BaseModel):
    """Kept for backward compatibility – use MasterPasswordLoginRequest instead."""
    role: str = "user"
    password: Optional[str] = None


# Response Schemas
class AuthModeResponse(BaseModel):
    """Legacy auth mode response (kept for backward compatibility)."""
    mode: str  # "development" | "production"


class AuthConfigResponse(BaseModel):
    """Full authentication configuration returned to the frontend."""
    mode: str                          # "development" | "production"
    providers: Dict[str, bool]         # {"azure": bool, "local_db": bool, "master_pw": bool}
    passwordless: bool
    available_roles: Optional[List[str]] = None  # Only populated in development mode


class TokenResponse(BaseModel):
    """Token response after successful authentication."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    """User information response."""
    id: UUID
    email: str
    first_name: str
    last_name: str
    roles: List[str]
    is_active: bool
    last_login_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str
