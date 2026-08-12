"""
Person model for user data management.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import TimestampMixin, SoftDeleteMixin


class Person(Base, TimestampMixin, SoftDeleteMixin):
    """
    Person model representing users.

    Attributes:
        id: Primary key
        first_name: First name
        last_name: Last name
        email: Email address (unique)
        is_active: Whether user is currently active
        password_hash: Hashed password for local authentication
        last_login_at: Last login timestamp
        entra_object_id: Entra ID object ID (for Azure AD integration)
        auth_source: Authentication source ('local' or 'entra_id')
    """
    __tablename__ = "person"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    first_name = Column(String(100), nullable=False, comment="First name")
    last_name = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Last name"
    )
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Email address"
    )
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether user is currently active"
    )

    # Authentication fields
    password_hash = Column(
        String(255),
        nullable=True,
        info={"audit_ignore": True},  # Never include password hash in audit logs
        comment="Hashed password for local authentication"
    )
    last_login_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last login timestamp"
    )

    # Entra ID fields
    entra_object_id = Column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
        comment="Entra ID object ID"
    )

    # Auth source tracking
    auth_source = Column(
        String(50),
        default="local",
        index=True,
        comment="Authentication source: 'local' or 'entra_id'"
    )

    # Relationships
    # Note: explicit foreign_keys to avoid ambiguity from self-referencing FKs
    # (deleted_by, updated_by point back to person.id)
    roles = relationship(
        "PersonRole",
        back_populates="person",
        cascade="all, delete-orphan",
        foreign_keys="[PersonRole.person_id]"
    )

    # Indexes
    __table_args__ = (
        Index("idx_person_email", "email"),
        Index("idx_person_last_name", "last_name"),
        Index("idx_person_is_active", "is_active"),
        Index("idx_person_auth_source", "auth_source"),
    )

    def __repr__(self) -> str:
        return f"<Person {self.first_name} {self.last_name} ({self.email})>"

    @property
    def full_name(self) -> str:
        """Get full name of person."""
        return f"{self.first_name} {self.last_name}"
