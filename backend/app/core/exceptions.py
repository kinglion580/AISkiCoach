"""
Custom exceptions and error codes for the application
Separates user-facing messages from internal logging
"""
from enum import Enum
from typing import Any, Dict, Optional

from fastapi import HTTPException, status


class ErrorCode(str, Enum):
    """Standard error codes for the application"""

    # Authentication & Authorization (1xxx)
    INVALID_CREDENTIALS = "AUTH_1001"
    TOKEN_EXPIRED = "AUTH_1002"
    INVALID_TOKEN = "AUTH_1003"
    INSUFFICIENT_PERMISSIONS = "AUTH_1004"

    # Verification Code (2xxx)
    INVALID_PHONE_FORMAT = "VCODE_2001"
    VERIFICATION_CODE_EXPIRED = "VCODE_2002"
    VERIFICATION_CODE_INVALID = "VCODE_2003"
    VERIFICATION_CODE_MAX_ATTEMPTS = "VCODE_2004"
    VERIFICATION_CODE_SEND_FAILED = "VCODE_2005"
    VERIFICATION_CODE_STORAGE_FAILED = "VCODE_2006"

    # Rate Limiting (3xxx)
    RATE_LIMIT_EXCEEDED = "RATE_3001"

    # Database (4xxx)
    DATABASE_ERROR = "DB_4001"
    RECORD_NOT_FOUND = "DB_4002"
    DUPLICATE_RECORD = "DB_4003"

    # External Services (5xxx)
    REDIS_CONNECTION_FAILED = "EXT_5001"
    SMS_SERVICE_FAILED = "EXT_5002"
    EMAIL_SERVICE_FAILED = "EXT_5003"

    # Validation (6xxx)
    INVALID_INPUT = "VAL_6001"
    MISSING_REQUIRED_FIELD = "VAL_6002"

    # Internal Errors (9xxx)
    INTERNAL_SERVER_ERROR = "SYS_9001"
    SERVICE_UNAVAILABLE = "SYS_9002"


class AppException(Exception):
    """
    Base exception for application errors

    Separates user-facing message from internal details:
    - user_message: Safe message shown to users
    - internal_message: Detailed message for logs (may contain sensitive info)
    - error_code: Standard error code for tracking
    """

    def __init__(
        self,
        user_message: str,
        error_code: ErrorCode,
        internal_message: Optional[str] = None,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        self.user_message = user_message
        self.internal_message = internal_message or user_message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}

        super().__init__(self.internal_message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response"""
        return {
            "error": {
                "code": self.error_code.value,
                "message": self.user_message,
                "details": self.details
            }
        }


# Specific exception classes for common scenarios

class AuthenticationError(AppException):
    """Authentication failed"""
    def __init__(self, user_message: str = "认证失败", internal_message: Optional[str] = None):
        super().__init__(
            user_message=user_message,
            error_code=ErrorCode.INVALID_CREDENTIALS,
            internal_message=internal_message,
            status_code=status.HTTP_401_UNAUTHORIZED
        )


class TokenExpiredError(AppException):
    """Token has expired"""
    def __init__(self, user_message: str = "登录已过期，请重新登录"):
        super().__init__(
            user_message=user_message,
            error_code=ErrorCode.TOKEN_EXPIRED,
            status_code=status.HTTP_401_UNAUTHORIZED
        )


class PermissionDeniedError(AppException):
    """Insufficient permissions"""
    def __init__(self, user_message: str = "权限不足"):
        super().__init__(
            user_message=user_message,
            error_code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            status_code=status.HTTP_403_FORBIDDEN
        )


class ValidationError(AppException):
    """Input validation failed"""
    def __init__(
        self,
        user_message: str,
        field: Optional[str] = None,
        internal_message: Optional[str] = None
    ):
        details = {"field": field} if field else {}
        super().__init__(
            user_message=user_message,
            error_code=ErrorCode.INVALID_INPUT,
            internal_message=internal_message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details
        )


class VerificationCodeError(AppException):
    """Verification code related errors"""
    def __init__(
        self,
        user_message: str,
        error_code: ErrorCode = ErrorCode.VERIFICATION_CODE_INVALID,
        internal_message: Optional[str] = None
    ):
        super().__init__(
            user_message=user_message,
            error_code=error_code,
            internal_message=internal_message,
            status_code=status.HTTP_400_BAD_REQUEST
        )


class RateLimitError(AppException):
    """Rate limit exceeded"""
    def __init__(
        self,
        user_message: str = "请求过于频繁，请稍后再试",
        internal_message: Optional[str] = None,
        retry_after: Optional[int] = None
    ):
        self.retry_after = retry_after
        details = {"retry_after": retry_after} if retry_after else {}
        super().__init__(
            user_message=user_message,
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            internal_message=internal_message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details
        )


class DatabaseError(AppException):
    """Database operation failed"""
    def __init__(
        self,
        user_message: str = "数据库操作失败，请稍后重试",
        internal_message: Optional[str] = None
    ):
        super().__init__(
            user_message=user_message,
            error_code=ErrorCode.DATABASE_ERROR,
            internal_message=internal_message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class RecordNotFoundError(AppException):
    """Database record not found"""
    def __init__(
        self,
        user_message: str = "记录不存在",
        resource: Optional[str] = None
    ):
        details = {"resource": resource} if resource else {}
        super().__init__(
            user_message=user_message,
            error_code=ErrorCode.RECORD_NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details
        )


class ExternalServiceError(AppException):
    """External service (Redis, SMS, etc.) failed"""
    def __init__(
        self,
        user_message: str,
        error_code: ErrorCode,
        internal_message: Optional[str] = None
    ):
        super().__init__(
            user_message=user_message,
            error_code=error_code,
            internal_message=internal_message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )


class RedisError(ExternalServiceError):
    """Redis connection or operation failed"""
    def __init__(
        self,
        user_message: str = "服务暂时不可用，请稍后重试",
        internal_message: Optional[str] = None
    ):
        super().__init__(
            user_message=user_message,
            error_code=ErrorCode.REDIS_CONNECTION_FAILED,
            internal_message=internal_message
        )


class SMSServiceError(ExternalServiceError):
    """SMS service failed"""
    def __init__(
        self,
        user_message: str = "短信发送失败，请稍后重试",
        internal_message: Optional[str] = None
    ):
        super().__init__(
            user_message=user_message,
            error_code=ErrorCode.SMS_SERVICE_FAILED,
            internal_message=internal_message
        )


# Helper function to convert standard HTTPException to AppException
def http_exception_to_app_exception(exc: HTTPException) -> AppException:
    """Convert FastAPI HTTPException to AppException"""

    # Map status codes to error codes
    status_to_error_code = {
        401: ErrorCode.INVALID_CREDENTIALS,
        403: ErrorCode.INSUFFICIENT_PERMISSIONS,
        404: ErrorCode.RECORD_NOT_FOUND,
        429: ErrorCode.RATE_LIMIT_EXCEEDED,
        500: ErrorCode.INTERNAL_SERVER_ERROR,
        503: ErrorCode.SERVICE_UNAVAILABLE,
    }

    error_code = status_to_error_code.get(exc.status_code, ErrorCode.INTERNAL_SERVER_ERROR)

    return AppException(
        user_message=str(exc.detail),
        error_code=error_code,
        status_code=exc.status_code
    )
