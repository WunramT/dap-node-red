"""
Email service for sending transactional emails.

This service provides a reusable interface for sending emails via SMTP
with built-in retry logic for handling transient failures.

Usage:
    from app.services.email_service import EmailService

    email_service = EmailService()
    await email_service.send_email(
        to="user@example.com",
        subject="Welcome",
        body="Hello!"
    )

Configuration:
    Configure SMTP settings via environment variables or app settings:
    - SMTP_HOST: SMTP server hostname
    - SMTP_PORT: SMTP server port (default: 587)
    - SMTP_USER: SMTP authentication username
    - SMTP_PASSWORD: SMTP authentication password
    - SMTP_FROM: Default sender email address
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.config import settings
from app.core.logging import get_logger
from app.core.resilience import retry_smtp

logger = get_logger(__name__)


class EmailService:
    """
    Service for sending emails via SMTP.

    Uses the retry_smtp decorator to automatically retry on transient
    SMTP failures with exponential backoff.

    Developers can customize retry behavior by:
    1. Modifying retry_smtp parameters in app/core/resilience.py
    2. Creating a custom retry decorator for specific use cases
    3. Overriding the decorator on individual methods

    Example with custom retry settings:
        from tenacity import retry, stop_after_attempt, wait_fixed

        custom_retry = retry(stop=stop_after_attempt(5), wait=wait_fixed(5))

        class CustomEmailService(EmailService):
            @custom_retry
            async def send_email(self, to: str, subject: str, body: str):
                return await super().send_email(to, subject, body)
    """

    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        smtp_from: Optional[str] = None,
    ):
        """
        Initialize the email service.

        Args:
            smtp_host: SMTP server hostname (defaults to settings.smtp_host)
            smtp_port: SMTP server port (defaults to settings.smtp_port)
            smtp_user: SMTP username (defaults to settings.smtp_user)
            smtp_password: SMTP password (defaults to settings.smtp_password)
            smtp_from: Default sender email (defaults to settings.smtp_from)
        """
        self.smtp_host = smtp_host or getattr(settings, "smtp_host", "localhost")
        self.smtp_port = smtp_port or getattr(settings, "smtp_port", 587)
        self.smtp_user = smtp_user or getattr(settings, "smtp_user", None)
        self.smtp_password = smtp_password or getattr(settings, "smtp_password", None)
        self.smtp_from = smtp_from or getattr(settings, "smtp_from", "noreply@example.com")

    @retry_smtp
    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        from_email: Optional[str] = None,
    ) -> bool:
        """
        Send an email via SMTP.

        This method is decorated with @retry_smtp which automatically retries
        on transient SMTP failures (SMTPServerDisconnected, SMTPConnectError,
        ConnectionError) up to 3 times with exponential backoff.

        Args:
            to: Recipient email address
            subject: Email subject line
            body: Plain text email body
            html_body: Optional HTML email body
            from_email: Sender email (defaults to self.smtp_from)

        Returns:
            True if email was sent successfully

        Raises:
            smtplib.SMTPException: If sending fails after all retries
        """
        sender = from_email or self.smtp_from

        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to

        # Attach plain text body
        msg.attach(MIMEText(body, "plain"))

        # Attach HTML body if provided
        if html_body:
            msg.attach(MIMEText(html_body, "html"))

        logger.info(f"Sending email to {to}: {subject}")

        # Send email via SMTP
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            if self.smtp_user and self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)
            server.sendmail(sender, [to], msg.as_string())

        logger.info(f"Email sent successfully to {to}")
        return True


# Singleton instance (optional, for convenience)
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Get or create the email service singleton."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
