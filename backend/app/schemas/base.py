"""Base schemas with common fields."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class TimestampSchema(BaseSchema):
    """Schema with timestamp fields."""
    created_at: datetime
    updated_at: datetime


class SoftDeleteSchema(TimestampSchema):
    """Schema with soft delete support."""
    deleted_at: Optional[datetime] = None
