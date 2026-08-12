"""
Request context management using contextvars.

This module provides a thread-safe way to store and access request-scoped
data such as request IDs and actor IDs throughout the application lifecycle.
"""
from contextvars import ContextVar
from typing import Optional
from uuid import UUID


# Context variables for request-scoped data
_request_id: ContextVar[Optional[UUID]] = ContextVar("request_id", default=None)
_actor_id: ContextVar[Optional[UUID]] = ContextVar("actor_id", default=None)


def get_request_id() -> Optional[UUID]:
    """
    Get the current request ID from context.

    Returns:
        Current request ID if set, None otherwise
    """
    return _request_id.get()


def set_request_id(request_id: UUID) -> None:
    """
    Set the request ID in context.

    Args:
        request_id: UUID to set as current request ID
    """
    _request_id.set(request_id)


def get_actor_id() -> Optional[UUID]:
    """
    Get the current actor ID (authenticated user ID) from context.

    Returns:
        Current actor ID if set, None otherwise
    """
    return _actor_id.get()


def set_actor_id(actor_id: Optional[UUID]) -> None:
    """
    Set the actor ID in context.

    Args:
        actor_id: UUID to set as current actor ID, or None for unauthenticated requests
    """
    _actor_id.set(actor_id)


def clear_request_context() -> None:
    """
    Clear all request context variables.

    Should be called at the end of request processing to prevent context leakage.
    """
    _request_id.set(None)
    _actor_id.set(None)
