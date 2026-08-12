"""
Resilience module for external service calls.

This module provides reusable retry decorators for handling transient failures
when communicating with external services like HTTP APIs and SMTP servers.

Usage:
    from app.core.resilience import retry_http, retry_smtp

    @retry_http
    async def call_external_api():
        ...

    @retry_smtp
    async def send_email():
        ...

Configuration:
    The retry parameters (attempts, wait times) can be customized per project
    by modifying the decorator definitions below or by creating project-specific
    decorators with different settings.

    Parameters explained:
    - stop_after_attempt(n): Maximum number of retry attempts
    - wait_exponential(multiplier, min, max): Exponential backoff timing
      - multiplier: Base multiplier for wait time
      - min: Minimum wait time in seconds
      - max: Maximum wait time in seconds
    - retry_if_exception_type: Tuple of exception types to retry on
"""

import logging
import smtplib

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


# Retry-Decorator für externe HTTP-Aufrufe
# Retries up to 3 times with exponential backoff (1s, 2s, 4s, max 10s)
# Customize: Adjust stop_after_attempt for more/fewer retries
# Customize: Adjust wait_exponential params for different backoff timing
retry_http = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
    before_sleep=lambda retry_state: logger.warning(
        f"Retry {retry_state.attempt_number} for {retry_state.fn.__name__}: "
        f"{retry_state.outcome.exception()}"
    ),
)


# Retry-Decorator für SMTP-Aufrufe
# Retries up to 3 times with exponential backoff (2s, 4s, 8s, max 30s)
# SMTP connections often need longer wait times due to server load
# Customize: Adjust stop_after_attempt for more/fewer retries
# Customize: Adjust wait_exponential params for different backoff timing
retry_smtp = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(
        (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, ConnectionError)
    ),
    before_sleep=lambda retry_state: logger.warning(
        f"SMTP retry {retry_state.attempt_number}: {retry_state.outcome.exception()}"
    ),
)
