"""Base CRUD operations."""
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from datetime import datetime
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import Base


ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Base class for CRUD operations."""

    def __init__(self, model: Type[ModelType]):
        """Initialize CRUD object with model."""
        self.model = model

    def _has_soft_delete(self) -> bool:
        """Check if the model supports soft delete."""
        return hasattr(self.model, 'deleted_at')

    def _apply_soft_delete_filter(self, query):
        """Apply soft delete filter to query if model supports it."""
        if self._has_soft_delete():
            query = query.where(self.model.deleted_at.is_(None))
        return query

    async def get(self, db: AsyncSession, id: Any) -> Optional[ModelType]:
        """Get a single record by ID (excluding soft-deleted records)."""
        query = select(self.model).where(self.model.id == id)
        query = self._apply_soft_delete_filter(query)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        """Get multiple records with pagination and filters (excluding soft-deleted records)."""
        query = select(self.model)

        # Apply soft delete filter
        query = self._apply_soft_delete_filter(query)

        # Apply filters if provided
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    query = query.where(getattr(self.model, key) == value)

        # Apply pagination
        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def count(
        self,
        db: AsyncSession,
        filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """Count records with optional filters (excluding soft-deleted records)."""
        query = select(func.count()).select_from(self.model)

        # Apply soft delete filter
        if self._has_soft_delete():
            query = query.where(self.model.deleted_at.is_(None))

        # Apply filters if provided
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    query = query.where(getattr(self.model, key) == value)

        result = await db.execute(query)
        return result.scalar_one()

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: CreateSchemaType
    ) -> ModelType:
        """Create a new record."""
        obj_in_data = obj_in.model_dump() if hasattr(obj_in, 'model_dump') else obj_in.dict()
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """Update a record."""
        obj_data = db_obj.__dict__

        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True) if hasattr(obj_in, 'model_dump') else obj_in.dict(exclude_unset=True)

        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])

        # Update timestamp
        if hasattr(db_obj, 'updated_at'):
            db_obj.updated_at = datetime.utcnow()

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def delete(
        self,
        db: AsyncSession,
        *,
        id: Any,
        soft: bool = True
    ) -> Optional[ModelType]:
        """Delete a record (soft or hard delete)."""
        db_obj = await self.get(db, id)
        if not db_obj:
            return None

        if soft and hasattr(db_obj, 'deleted_at'):
            # Soft delete
            db_obj.deleted_at = datetime.utcnow()
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
        else:
            # Hard delete
            await db.delete(db_obj)
            await db.commit()

        return db_obj

    async def restore(
        self,
        db: AsyncSession,
        *,
        id: Any
    ) -> Optional[ModelType]:
        """Restore a soft-deleted record."""
        result = await db.execute(
            select(self.model).where(self.model.id == id)
        )
        db_obj = result.scalar_one_or_none()

        if not db_obj or not hasattr(db_obj, 'deleted_at'):
            return None

        db_obj.deleted_at = None
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
