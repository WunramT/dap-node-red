"""
Person management endpoints (for local auth mode).
"""

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.api.deps import get_db, get_current_user
from app.crud import person as person_crud
from app.core.security import get_password_hash
from app.models.person import Person
from app.schemas.person import PersonCreate, PersonUpdate, PersonResponse

router = APIRouter()


async def require_admin(
    current_user: Person = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Person:
    """
    Dependency to require admin role.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Current user if admin

    Raises:
        HTTPException: If user is not admin
    """
    # Reload user with roles eagerly loaded to avoid lazy loading issues
    stmt = (
        select(Person)
        .where(Person.id == current_user.id)
        .options(selectinload(Person.roles).selectinload(person_crud.PersonRole.role))
    )
    result = await db.execute(stmt)
    user_with_roles = result.scalar_one_or_none()

    if not user_with_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User not found"
        )

    # Check if user has admin role
    if not any(role.role.name == "admin" for role in user_with_roles.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )

    return user_with_roles


@router.get("/", response_model=List[PersonResponse], status_code=status.HTTP_200_OK)
async def list_persons(
    skip: int = 0,
    limit: int = 100,
    include_inactive: bool = False,
    current_user: Person = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    List all persons (admin only).

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        include_inactive: Include inactive users
        current_user: Current authenticated admin user
        db: Database session

    Returns:
        List of persons
    """
    # Build query with eager loading of roles
    stmt = select(Person).options(
        selectinload(Person.roles).selectinload(person_crud.PersonRole.role)
    )

    if not include_inactive:
        stmt = stmt.where(Person.is_active == True, Person.deleted_at.is_(None))

    stmt = stmt.offset(skip).limit(limit)

    result = await db.execute(stmt)
    persons = result.scalars().all()

    # Convert to response format with roles
    response = []
    for person in persons:
        roles = [pr.role.name for pr in person.roles]
        person_data = PersonResponse(
            id=person.id,
            email=person.email,
            first_name=person.first_name,
            last_name=person.last_name,
            is_active=person.is_active,
            roles=roles,
            auth_source=person.auth_source,
            created_at=person.created_at,
            last_login_at=person.last_login_at,
        )
        response.append(person_data)

    return response


@router.post("/", response_model=PersonResponse, status_code=status.HTTP_201_CREATED)
async def create_person(
    person_data: PersonCreate,
    current_user: Person = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new person (admin only).

    Args:
        person_data: Person creation data
        current_user: Current authenticated admin user
        db: Database session

    Returns:
        Created person

    Raises:
        HTTPException: If email already exists
    """
    # Check if email already exists
    existing = await person_crud.get_by_email(db, person_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Hash password if provided
    password_hash = None
    if person_data.password:
        password_hash = get_password_hash(person_data.password)

    # Create person with first role
    primary_role = person_data.roles[0] if person_data.roles else "user"
    person = await person_crud.create_with_role(
        db=db,
        email=person_data.email,
        first_name=person_data.first_name,
        last_name=person_data.last_name,
        role_name=primary_role,
        password_hash=password_hash,
        auth_source="local",
    )

    # Add additional roles if provided
    if len(person_data.roles) > 1:
        await person_crud.update_roles(db, person, person_data.roles)
        # Refresh to get updated roles with eager loading
        await db.refresh(person, ["roles"])

    # Reload person with roles eagerly loaded
    stmt = (
        select(Person)
        .where(Person.id == person.id)
        .options(selectinload(Person.roles).selectinload(person_crud.PersonRole.role))
    )
    result = await db.execute(stmt)
    person = result.scalar_one()

    # Convert to response format
    roles = [pr.role.name for pr in person.roles]
    return PersonResponse(
        id=person.id,
        email=person.email,
        first_name=person.first_name,
        last_name=person.last_name,
        is_active=person.is_active,
        roles=roles,
        auth_source=person.auth_source,
        created_at=person.created_at,
        last_login_at=person.last_login_at,
    )


@router.patch(
    "/{person_id}", response_model=PersonResponse, status_code=status.HTTP_200_OK
)
async def update_person(
    person_id: UUID,
    person_data: PersonUpdate,
    current_user: Person = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a person (admin only).

    Args:
        person_id: Person UUID
        person_data: Person update data
        current_user: Current authenticated admin user
        db: Database session

    Returns:
        Updated person

    Raises:
        HTTPException: If person not found
    """
    person = await person_crud.get_by_id(db, person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Person not found"
        )

    # Update basic fields
    if person_data.first_name is not None:
        person.first_name = person_data.first_name
    if person_data.last_name is not None:
        person.last_name = person_data.last_name
    if person_data.is_active is not None:
        person.is_active = person_data.is_active

    # Update roles if provided
    if person_data.roles is not None:
        await person_crud.update_roles(db, person, person_data.roles)

    await db.commit()

    # Reload person with roles eagerly loaded
    stmt = (
        select(Person)
        .where(Person.id == person_id)
        .options(selectinload(Person.roles).selectinload(person_crud.PersonRole.role))
    )
    result = await db.execute(stmt)
    person = result.scalar_one()

    # Convert to response format
    roles = [pr.role.name for pr in person.roles]
    return PersonResponse(
        id=person.id,
        email=person.email,
        first_name=person.first_name,
        last_name=person.last_name,
        is_active=person.is_active,
        roles=roles,
        auth_source=person.auth_source,
        created_at=person.created_at,
        last_login_at=person.last_login_at,
    )


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_person(
    person_id: UUID,
    current_user: Person = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Soft delete a person (admin only).

    Args:
        person_id: Person UUID
        current_user: Current authenticated admin user
        db: Database session

    Raises:
        HTTPException: If person not found or trying to delete self
    """
    person = await person_crud.get_by_id(db, person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Person not found"
        )

    # Prevent self-deletion
    if person.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    # Soft delete
    from datetime import datetime, timezone

    person.deleted_at = datetime.now(timezone.utc)
    person.is_active = False

    await db.commit()
