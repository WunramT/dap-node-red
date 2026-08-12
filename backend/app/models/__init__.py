"""
Database models package.

Import all models here to ensure they are registered with SQLAlchemy.
"""
from app.models.person import Person
from app.models.role import Role, RoleEnum
from app.models.person_role import PersonRole

__all__ = [
    "Person",
    "Role",
    "RoleEnum",
    "PersonRole",
]
