"""
Base model mixins providing common functionality.
"""
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID
from sqlalchemy import Column, DateTime, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import declared_attr
from sqlalchemy.inspection import inspect


class TimestampMixin:
    """
    Mixin providing created_at and updated_at timestamp columns.

    These columns are automatically set on record creation and update.
    """
    # Required for Python 3.14+ compatibility with SQLAlchemy type annotations
    __allow_unmapped__ = True

    @declared_attr
    def created_at(cls):
        return Column(
            DateTime(timezone=True),
            default=lambda: datetime.now(timezone.utc),
            nullable=False,
            comment="Record creation timestamp"
        )

    @declared_attr
    def updated_at(cls):
        return Column(
            DateTime(timezone=True),
            default=lambda: datetime.now(timezone.utc),
            onupdate=lambda: datetime.now(timezone.utc),
            nullable=False,
            comment="Last update timestamp"
        )


class ActorTrackingMixin:
    """
    Mixin providing actor tracking for create and update operations.

    Tracks which user (actor) created and last updated a record.
    Uses context variables to automatically capture the current actor ID.
    """
    # Required for Python 3.14+ compatibility with SQLAlchemy type annotations
    __allow_unmapped__ = True

    @declared_attr
    def created_by(cls):
        return Column(
            PGUUID(as_uuid=True),
            ForeignKey("person.id", ondelete="SET NULL"),
            nullable=True,
            comment="ID of user who created this record"
        )

    @declared_attr
    def updated_by(cls):
        return Column(
            PGUUID(as_uuid=True),
            ForeignKey("person.id", ondelete="SET NULL"),
            nullable=True,
            comment="ID of user who last updated this record"
        )


class SoftDeleteMixin:
    """
    Mixin providing soft delete functionality with audit information.

    Instead of actually deleting records, sets a deleted_at timestamp.
    Also tracks who deleted the record and why (optional reason).
    Query filters should exclude records where deleted_at is not None.
    """
    # Required for Python 3.14+ compatibility with SQLAlchemy type annotations
    __allow_unmapped__ = True

    @declared_attr
    def deleted_at(cls):
        return Column(
            DateTime(timezone=True),
            nullable=True,
            default=None,
            comment="Soft delete timestamp (null if not deleted)"
        )

    @declared_attr
    def deleted_by(cls):
        return Column(
            PGUUID(as_uuid=True),
            ForeignKey("person.id", ondelete="SET NULL"),
            nullable=True,
            comment="ID of user who deleted this record"
        )

    @declared_attr
    def deletion_reason(cls):
        return Column(
            String(500),
            nullable=True,
            comment="Reason for deletion (optional)"
        )

    @property
    def is_deleted(self) -> bool:
        """Check if the record is soft-deleted."""
        return self.deleted_at is not None

    @property
    def is_active(self) -> bool:
        """Check if the record is not soft-deleted."""
        return self.deleted_at is None

    def soft_delete(self, reason: Optional[str] = None) -> None:
        """
        Mark the record as soft-deleted.

        Args:
            reason: Optional reason for deletion (max 500 characters)
        """
        from app.core.context import get_actor_id

        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = get_actor_id()
        if reason:
            self.deletion_reason = reason[:500]  # Truncate to max length

    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.deleted_at = None
        self.deleted_by = None
        self.deletion_reason = None


# ============================================================================
# Audit Security Helpers
# ============================================================================


def is_audit_ignored(column: Column) -> bool:
    """
    Check if a column should be ignored in audit logs.

    Columns can be marked for audit exclusion by setting info={"audit_ignore": True}
    in their column definition. This is useful for sensitive fields like passwords
    or secrets that should never appear in audit logs.

    Example:
        password_hash = Column(String, info={"audit_ignore": True})

    Args:
        column: SQLAlchemy Column object to check

    Returns:
        True if the column should be excluded from audit logs, False otherwise
    """
    if not hasattr(column, "info"):
        return False

    return column.info.get("audit_ignore", False)


def get_auditable_columns(model) -> List[Column]:
    """
    Get list of columns from a model that should be included in audit logs.

    Filters out columns marked with info={"audit_ignore": True}.

    Args:
        model: SQLAlchemy model class or instance

    Returns:
        List of Column objects that are safe for audit logging

    Example:
        from app.models.person import Person
        columns = get_auditable_columns(Person)
        # Returns all columns except those marked with audit_ignore
    """
    mapper = inspect(model)
    all_columns = mapper.columns

    return [
        col for col in all_columns
        if not is_audit_ignored(col)
    ]
