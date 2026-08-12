"""
Middleware for request context management.

This module provides middleware to automatically inject request IDs and actor IDs
into the request context for audit logging and tracing purposes.
"""
import uuid
from typing import Callable, Optional
from uuid import UUID

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.context import set_request_id, set_actor_id, clear_request_context
from app.core.security import decode_access_token
from app.core.logging import get_logger

logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that injects request context for audit tracking.

    For each request:
    1. Generates a unique request ID (UUID)
    2. Extracts actor ID from JWT token if present
    3. Stores both in context variables accessible throughout the request
    4. Adds X-Request-ID header to response
    5. Cleans up context after request completion
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and inject context.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler

        Returns:
            The HTTP response with added X-Request-ID header
        """
        # Generate unique request ID
        request_id = uuid.uuid4()
        set_request_id(request_id)

        # Try to extract actor ID from Authorization header
        actor_id = self._extract_actor_id(request)
        set_actor_id(actor_id)

        # Log request start (useful for debugging)
        logger.debug(
            f"Request started: {request.method} {request.url.path} "
            f"[request_id={request_id}, actor_id={actor_id}]"
        )

        try:
            # Process request
            response = await call_next(request)

            # Add request ID to response headers for client-side tracking
            response.headers["X-Request-ID"] = str(request_id)

            return response

        finally:
            # Always clean up context to prevent leakage between requests
            clear_request_context()

    def _extract_actor_id(self, request: Request) -> Optional[UUID]:
        """
        Extract actor ID from JWT token in Authorization header.

        Args:
            request: The incoming HTTP request

        Returns:
            Actor UUID if token is valid and contains 'sub' claim, None otherwise
        """
        try:
            # Check for Authorization header
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                return None

            # Extract token (format: "******")
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != "bearer":
                return None

            token = parts[1]

            # Decode token to extract subject (actor ID)
            payload = decode_access_token(token)
            if not payload:
                return None

            # Extract 'sub' claim (subject = user ID)
            sub = payload.get("sub")
            if not sub:
                return None

            # Convert to UUID
            return UUID(sub)

        except (ValueError, Exception) as e:
            # Invalid token format or UUID - log but don't fail request
            logger.debug(f"Failed to extract actor ID from token: {e}")
            return None
