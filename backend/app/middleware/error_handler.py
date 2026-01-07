"""
Global error handler middleware
Catches all exceptions and returns standardized error responses
"""
import logging
import traceback
from typing import Callable
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException, ErrorCode, http_exception_to_app_exception

logger = logging.getLogger(__name__)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """
    Handle AppException - our custom exceptions

    Returns user-friendly message to client, logs detailed internal message
    """
    # Log internal details (may contain sensitive info)
    logger.error(
        f"AppException: {exc.error_code.value} - {exc.internal_message}",
        extra={
            "error_code": exc.error_code.value,
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method,
            "user_message": exc.user_message,
            "details": exc.details
        }
    )

    # Return safe user-facing response
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle FastAPI HTTPException

    Convert to AppException format for consistency
    """
    app_exc = http_exception_to_app_exception(exc)

    logger.warning(
        f"HTTPException: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method,
            "detail": exc.detail
        }
    )

    return JSONResponse(
        status_code=app_exc.status_code,
        content=app_exc.to_dict()
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle Pydantic validation errors

    Returns user-friendly field-specific error messages
    """
    errors = exc.errors()

    # Extract field names and messages
    field_errors = []
    for error in errors:
        field = ".".join(str(loc) for loc in error["loc"] if loc != "body")
        message = error["msg"]
        field_errors.append({
            "field": field,
            "message": message
        })

    logger.warning(
        f"Validation error on {request.url.path}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "errors": field_errors
        }
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "code": ErrorCode.INVALID_INPUT.value,
                "message": "输入数据验证失败",
                "details": {
                    "fields": field_errors
                }
            }
        }
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all handler for unexpected exceptions

    Logs full stack trace but returns generic message to user
    """
    # Log full stack trace for debugging
    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {str(exc)}",
        exc_info=True,
        extra={
            "path": request.url.path,
            "method": request.method,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "traceback": traceback.format_exc()
        }
    )

    # Return generic error to user (don't expose internal details)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": ErrorCode.INTERNAL_SERVER_ERROR.value,
                "message": "服务器内部错误，请稍后重试",
                "details": {}
            }
        }
    )


def setup_exception_handlers(app):
    """
    Register all exception handlers with the FastAPI app

    Call this in main.py after creating the app
    """
    # Custom AppException
    app.add_exception_handler(AppException, app_exception_handler)

    # FastAPI HTTPException
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    # Validation errors
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # Catch-all for any other exceptions
    app.add_exception_handler(Exception, generic_exception_handler)

    logger.info("Exception handlers registered")
