"""
Centralized logging configuration for the backend.

This module provides:
- Structured logging setup with consistent formatting
- Environment-aware log levels (DEBUG in dev, INFO in prod)
- File logging with rotation (max file size + backup count)
- Integration with Sentry for error tracking
- Helper function to get loggers for modules
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

from app.config import settings


def setup_logging(
    level: Optional[int] = None,
    format_string: Optional[str] = None,
    log_dir: str = "logs",
    log_filename: str = "app.log",
    max_bytes: int = 5 * 1024 * 1024,  # 5 MB per file
    backup_count: int = 5,             # keep 5 rotated files
) -> None:
    """
    Configure application-wide logging.

    Sets up structured logging with timestamps, log levels, and module info.
    In debug mode, logs at DEBUG level; otherwise at INFO level.

    Args:
        level: Override log level (default: based on settings.debug)
        format_string: Override log format (default: structured format)
        log_dir: Directory for log files (created if missing)
        log_filename: Name of the log file
        max_bytes: Max size per log file before rotation (default 5 MB)
        backup_count: Number of rotated files to keep (default 5)
    """
    if level is None:
        level = logging.DEBUG if settings.debug else logging.INFO

    if format_string is None:
        format_string = (
            "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
        )

    formatter = logging.Formatter(
        fmt=format_string,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # --- stdout handler ---
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    stdout_handler.setLevel(level)
    root_logger.addHandler(stdout_handler)

    # --- rotating file handler ---
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_filename)

    file_handler = RotatingFileHandler(
        filename=log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    root_logger.addHandler(file_handler)

    # Configure library loggers to reduce noise
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured: level={logging.getLevelName(level)}, file={log_path}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.

    Usage:
        from app.core.logging import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened")
        logger.error("Something went wrong", exc_info=True)
    """
    return logging.getLogger(name)


DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL