"""
CRUD operations for Person model.
"""
from typing import Optional, List
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.person import Person
from app.models.role import Role
from app.models.person_role import PersonRole
from app.crud import role as role_crud


async def get_by_email(db: AsyncSession, email: str) -> Optional[Person]:
    """
    Get person by email address.

    Args:
        db: Database session
        email: Email address

    Returns:
        Person object if found, None otherwise
    """
    stmt = (
        select(Person)
        .where(Person.email == email)
        .where(Person.deleted_at.is_(None))
        .options(selectinload(Person.roles))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, person_id: UUID) -> Optional[Person]:
    """
    Get person by ID.

    Args:
        db: Database session
        person_id: Person UUID

    Returns:
        Person object if found, None otherwise
    """
    stmt = (
        select(Person)
        .where(Person.id == person_id)
        .where(Person.deleted_at.is_(None))
        .options(selectinload(Person.roles))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_with_role(
    db: AsyncSession,
    email: str,
    first_name: str,
    last_name: str,
    role_name: str,
    password_hash: Optional[str] = None,
    auth_source: str = "local"
) -> Person:
    """
    Create a new person with a specific role.

    Args:
        db: Database session
        email: Email address
        first_name: First name
        last_name: Last name
        role_name: Role name (e.g., "admin", "user")
        password_hash: Optional password hash
        auth_source: Authentication source (default: "local")

    Returns:
        Created Person object
    """
    # Create person
    person = Person(
        email=email,
        first_name=first_name,
        last_name=last_name,
        password_hash=password_hash,
        auth_source=auth_source,
        is_active=True
    )
    db.add(person)
    await db.flush()

    # Get or create role
    role = await role_crud.get_by_name(db, role_name)
    if not role:
        role = Role(name=role_name, description=f"{role_name} role")
        db.add(role)
        await db.flush()

    # Assign role to person
    person_role = PersonRole(person_id=person.id, role_id=role.id)
    db.add(person_role)

    await db.commit()
    await db.refresh(person)

    return person


async def ensure_default_users_exist(db: AsyncSession) -> None:
    """
    Ensure default users for master-password mode exist.

    Creates two system users if they don't exist:
    - admin@dev.com with admin role
    - user@dev.com  with user role

    Called at application startup when AUTH_PROVIDER_MASTER_PW or
    USER_PASSWORDLESS is enabled.

    Args:
        db: Database session
    """
    admin_user = await get_by_email(db, "admin@dev.com")
    if not admin_user:
        await create_with_role(
            db=db,
            email="admin@dev.com",
            first_name="Admin",
            last_name="User",
            role_name="admin",
            password_hash=None,
            auth_source="master_pw"
        )

    regular_user = await get_by_email(db, "user@dev.com")
    if not regular_user:
        await create_with_role(
            db=db,
            email="user@dev.com",
            first_name="Default",
            last_name="User",
            role_name="user",
            password_hash=None,
            auth_source="passwordless"
        )


async def create_seed_users_for_dev(db: AsyncSession) -> None:
    """
    Create seed users for development mode.

    Seeds one user per default role so that Swagger UI can be used
    immediately without any manual setup.

    | E-Mail          | Password | Role  |
    |-----------------|----------|-------|
    | admin@dev.com | admin    | admin |
    | user@dev.com  | user     | user  |

    Args:
        db: Database session
    """
    from app.core.security import get_password_hash

    seed_data = [
        ("admin@dev.com", "Admin", "Dev", "admin", "admin"),
        ("user@dev.com",  "User",  "Dev", "user",  "user"),
    ]

    for email, first, last, role, plain_pw in seed_data:
        existing = await get_by_email(db, email)
        if not existing:
            await create_with_role(
                db=db,
                email=email,
                first_name=first,
                last_name=last,
                role_name=role,
                password_hash=get_password_hash(plain_pw),
                auth_source="local"
            )


async def get_all(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    include_inactive: bool = False
) -> List[Person]:
    """
    Get all persons with pagination.

    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        include_inactive: Include inactive users

    Returns:
        List of Person objects
    """
    stmt = (
        select(Person)
        .where(Person.deleted_at.is_(None))
        .options(selectinload(Person.roles))
        .offset(skip)
        .limit(limit)
    )

    if not include_inactive:
        stmt = stmt.where(Person.is_active == True)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_roles(
    db: AsyncSession,
    person: Person,
    role_names: List[str]
) -> Person:
    """
    Update person's roles.

    Args:
        db: Database session
        person: Person object to update
        role_names: List of role names to assign

    Returns:
        Updated Person object
    """
    # Remove existing roles
    stmt = select(PersonRole).where(PersonRole.person_id == person.id)
    result = await db.execute(stmt)
    existing_person_roles = result.scalars().all()

    for pr in existing_person_roles:
        await db.delete(pr)

    # Add new roles
    for role_name in role_names:
        role = await role_crud.get_by_name(db, role_name)
        if role:
            person_role = PersonRole(person_id=person.id, role_id=role.id)
            db.add(person_role)

    await db.commit()
    await db.refresh(person)

    return person
