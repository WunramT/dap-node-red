"""
Person-related Pydantic schemas.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, ConfigDict


class PersonBase(BaseModel):
    """Base person schema with common fields."""
    email: EmailStr
    first_name: str
    last_name: str


class PersonCreate(PersonBase):
    """Schema for creating a new person."""
    password: Optional[str] = None
    roles: List[str] = ["user"]  # List of role names


class PersonUpdate(BaseModel):
    """Schema for updating a person."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: Optional[bool] = None
    roles: Optional[List[str]] = None


class PersonResponse(PersonBase):
    """Schema for person response."""
    id: UUID
    is_active: bool
    roles: List[str]
    auth_source: str
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
