"""
Role model for RBAC (Role-Based Access Control).
"""
import uuid
from enum import Enum
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import TimestampMixin


class RoleEnum(str, Enum):
    """
    Predefined role types.

    Azure AD App Roles mapping:
    - Admin -> admin (full access)
    - User -> user (standard user access)
    """
    ADMIN = "admin"
    USER = "user"


class Role(Base, TimestampMixin):
    """
    Role model for defining user roles and permissions.

    Attributes:
        id: Primary key
        name: Unique role name
        description: Role description
        entra_group_id: Optional Entra ID group mapping
    """
    __tablename__ = "roles"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    name = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique role name"
    )
    description = Column(
        String(255),
        nullable=True,
        comment="Role description"
    )
    entra_group_id = Column(
        String(255),
        nullable=True,
        comment="Entra ID group ID for mapping"
    )

    # Relationships
    person_roles = relationship(
        "PersonRole",
        back_populates="role",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Role {self.name}>"
