"""
Model fixtures for testing.

Provides factory functions and fixtures for creating test data.
"""
import uuid
from typing import Optional

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.person import Person
from app.models.role import Role
from app.models.person_role import PersonRole
from app.core.security import get_password_hash


async def create_test_role(
    db: AsyncSession,
    name: str = "user",
    description: str = "Test role"
) -> Role:
    """Create a test role, returning the existing one on name conflict."""
    try:
        async with db.begin_nested():
            role = Role(id=uuid.uuid4(), name=name, description=description)
            db.add(role)
            await db.flush()
        return role
    except IntegrityError:
        result = await db.execute(select(Role).where(Role.name == name))
        return result.scalar_one()


async def create_test_person(
    db: AsyncSession,
    email: Optional[str] = None,
    first_name: str = "Test",
    last_name: str = "User",
    is_active: bool = True,
    password: Optional[str] = "testpassword123",
    role_name: Optional[str] = None,
) -> Person:
    """
    Factory function to create a test person.

    If a person with the given email already exists (e.g. from seed data),
    the existing record is returned instead of raising IntegrityError.

    Args:
        db: Database session
        email: Email address (auto-generated if not provided)
        first_name: First name
        last_name: Last name
        is_active: Whether person is active
        password: Plain text password (hashed automatically)
        role_name: Optional role to assign

    Returns:
        Created or existing Person object
    """
    if email is None:
        email = f"test_{uuid.uuid4().hex[:8]}@example.com"

    password_hash = get_password_hash(password) if password else None

    try:
        async with db.begin_nested():
            person = Person(
                id=uuid.uuid4(),
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_active=is_active,
                password_hash=password_hash,
                auth_source="local",
            )
            db.add(person)
            await db.flush()
    except IntegrityError:
        result = await db.execute(
            select(Person).where(Person.email == email)
        )
        person = result.scalar_one()

    # Assign role if specified
    if role_name:
        result = await db.execute(select(Role).where(Role.name == role_name))
        role = result.scalar_one_or_none()

        if not role:
            role = await create_test_role(db, name=role_name)

        try:
            async with db.begin_nested():
                person_role = PersonRole(
                    id=uuid.uuid4(),
                    person_id=person.id,
                    role_id=role.id,
                )
                db.add(person_role)
                await db.flush()
        except IntegrityError:
            pass  # Role already assigned (e.g. seeded PersonRole)

    return person


@pytest_asyncio.fixture
async def test_person(db_session: AsyncSession) -> Person:
    """
    Create a test person with user role.

    This is the default authenticated user for most tests.
    """
    return await create_test_person(
        db_session,
        email="testuser@example.com",
        first_name="Test",
        last_name="User",
        role_name="user",
    )


@pytest_asyncio.fixture
async def admin_person(db_session: AsyncSession) -> Person:
    """
    Create an admin person.

    This user has full access to all endpoints.
    """
    return await create_test_person(
        db_session,
        email="admin@example.com",
        first_name="Admin",
        last_name="User",
        role_name="admin",
    )
