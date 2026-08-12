"""
PersonRole association model for many-to-many relationship between Person and Role.
"""
import uuid
from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import TimestampMixin


class PersonRole(Base, TimestampMixin):
    """
    Association model linking Person to Role.

    This enables many-to-many relationship where one person can have
    multiple roles and one role can be assigned to multiple persons.

    Attributes:
        id: Primary key
        person_id: Foreign key to Person
        role_id: Foreign key to Role
    """
    __tablename__ = "person_roles"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    person_id = Column(
        UUID(as_uuid=True),
        ForeignKey("person.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Person ID"
    )
    role_id = Column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Role ID"
    )

    # Relationships
    # Note: explicit foreign_keys to avoid ambiguity from self-referencing FKs on Person
    person = relationship("Person", back_populates="roles", foreign_keys=[person_id])
    role = relationship("Role", back_populates="person_roles")

    # Table constraints
    __table_args__ = (
        UniqueConstraint('person_id', 'role_id', name='uq_person_role'),
        {"comment": "Person-Role association table"}
    )

    def __repr__(self) -> str:
        return f"<PersonRole person_id={self.person_id} role_id={self.role_id}>"
