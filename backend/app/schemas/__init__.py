"""
Pydantic schemas package.
"""
from app.schemas.base import BaseSchema, TimestampSchema, SoftDeleteSchema
from app.schemas.common import PaginationParams, PaginatedResponse, MessageResponse, ErrorResponse
from app.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    AzureLoginRequest,
    TokenResponse,
    UserInfo,
)

__all__ = [
    "BaseSchema",
    "TimestampSchema",
    "SoftDeleteSchema",
    "PaginationParams",
    "PaginatedResponse",
    "MessageResponse",
    "ErrorResponse",
    "LoginRequest",
    "RefreshTokenRequest",
    "AzureLoginRequest",
    "TokenResponse",
    "UserInfo",
]
