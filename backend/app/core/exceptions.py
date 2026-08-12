"""Custom exceptions for the application."""
from typing import Optional, Any, Dict


class AppException(Exception):
    """Base exception class for application."""
    def __init__(self, message: str, error_code: Optional[str] = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class NotFoundException(AppException):
    """Exception raised when a resource is not found."""
    def __init__(self, message: str = "Resource not found", error_code: str = "NOT_FOUND"):
        super().__init__(message, error_code)


class ValidationException(AppException):
    """Exception raised when validation fails."""
    def __init__(
        self,
        message: str = "Validation error",
        error_code: str = "VALIDATION_ERROR",
        detail: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, error_code)
        self.detail = detail


class PermissionDeniedException(AppException):
    """Exception raised when permission is denied."""
    def __init__(self, message: str = "Permission denied", error_code: str = "PERMISSION_DENIED"):
        super().__init__(message, error_code)


class BusinessLogicException(AppException):
    """Exception raised when business logic validation fails."""
    def __init__(self, message: str = "Business logic error", error_code: str = "BUSINESS_LOGIC_ERROR"):
        super().__init__(message, error_code)


class AlreadyExistsException(AppException):
    """Exception raised when a resource already exists."""
    def __init__(self, message: str = "Resource already exists", error_code: str = "ALREADY_EXISTS"):
        super().__init__(message, error_code)
