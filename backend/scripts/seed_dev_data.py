"""
Seed data script for E2E tests.

Creates test users (admin and normal user) with their roles in the database.
This script is idempotent - it can be run multiple times without creating duplicates.

Usage:
    podman compose -f docker-compose.dev.yml exec backend python scripts/seed_dev_data.py
"""

import asyncio
import sys
import uuid
from pathlib import Path

# Add backend directory to path for imports
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.person import Person
from app.models.role import Role, RoleEnum
from app.models.person_role import PersonRole
from app.core.security import get_password_hash


# Dev mode user IDs - hardcoded to match frontend expectations
# These UUIDs must match DEV_USER_ID_MAPPING in frontend/src/stores/auth.ts
# Frontend sends these IDs in X-Dev-User-Id header when role-switching in dev mode
DEV_ADMIN_USER_ID = uuid.UUID("23719599-4ed8-45d4-9541-a6e486f4bb89")
DEV_USER_USER_ID = uuid.UUID("fbf594b9-788f-4003-8e89-430c15a0164c")

# Seed data configuration
ROLES = [
    {"name": RoleEnum.ADMIN.value, "description": "Administrator with full access"},
    {"name": RoleEnum.USER.value, "description": "Standard user with limited access"},
]

USERS = [
    {
        "id": DEV_ADMIN_USER_ID,
        "email": "admin@polipol.com",
        "first_name": "Admin",
        "last_name": "User",
        "password": "Admin123!",
        "role": RoleEnum.ADMIN.value,
    },
    {
        "id": DEV_USER_USER_ID,
        "email": "user@polipol.com",
        "first_name": "Test",
        "last_name": "User",
        "password": "User123!",
        "role": RoleEnum.USER.value,
    },
]


async def create_roles(db: AsyncSession) -> dict[str, Role]:
    """
    Create roles if they don't exist.

    Returns:
        Dictionary mapping role name to Role object
    """
    roles_map = {}

    for role_data in ROLES:
        stmt = select(Role).where(Role.name == role_data["name"])
        result = await db.execute(stmt)
        role = result.scalar_one_or_none()

        if role:
            print(f"  Role '{role_data['name']}' already exists, skipping...")
        else:
            role = Role(
                id=uuid.uuid4(),
                name=role_data["name"],
                description=role_data["description"],
            )
            db.add(role)
            await db.flush()
            print(f"  Created role: {role_data['name']}")

        roles_map[role_data["name"]] = role

    return roles_map


async def create_user(
    db: AsyncSession,
    email: str,
    first_name: str,
    last_name: str,
    password: str,
    role: Role,
    user_id: uuid.UUID | None = None,
) -> Person | None:
    """
    Create a user if they don't exist and assign the role.

    Args:
        db: Database session
        email: User email
        first_name: User first name
        last_name: User last name
        password: User password (plaintext, will be hashed)
        role: Role to assign
        user_id: Optional UUID for the user (for dev mode consistency)

    Returns:
        Person object if created, None if already exists
    """
    stmt = select(Person).where(Person.email == email)
    result = await db.execute(stmt)
    person = result.scalar_one_or_none()

    if person:
        print(f"  User '{email}' already exists, skipping...")
        return None

    person = Person(
        id=user_id or uuid.uuid4(),
        email=email,
        first_name=first_name,
        last_name=last_name,
        password_hash=get_password_hash(password),
        is_active=True,
        auth_source="local",
    )
    db.add(person)
    await db.flush()

    # Assign role
    person_role = PersonRole(
        id=uuid.uuid4(),
        person_id=person.id,
        role_id=role.id,
    )
    db.add(person_role)
    await db.flush()

    print(f"  Created user: {email} with role '{role.name}'")
    return person


async def seed_all(db: AsyncSession) -> None:
    """Run all seed operations."""
    print("\n=== Seeding Database ===\n")

    print("Creating roles...")
    roles_map = await create_roles(db)

    print("\nCreating users...")
    for user_data in USERS:
        role = roles_map.get(user_data["role"])
        if not role:
            print(
                f"  ERROR: Role '{user_data['role']}' not found, skipping user {user_data['email']}"
            )
            continue

        await create_user(
            db=db,
            email=user_data["email"],
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            password=user_data["password"],
            role=role,
            user_id=user_data.get("id"),
        )

    await db.commit()
    print("\n=== Seeding Complete ===\n")


async def main() -> None:
    """Entry point for the seed script."""
    print("Connecting to database...")

    async with AsyncSessionLocal() as db:
        try:
            await seed_all(db)
        except Exception as e:
            print(f"\nERROR: Seeding failed: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(main())
