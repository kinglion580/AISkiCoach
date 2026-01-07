"""
验证码登录和认证相关API
Refactored to use AuthService and audit logging
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import SessionDep
from app.core.audit import audit_service
from app.core.config import settings
from app.core.exceptions import (
    AuthenticationError,
    RateLimitError,
    VerificationCodeError,
)
from app.domains.auth import AuthService
from app.domains.auth.schemas import (
    LoginResponse,
    SendCodeRequest,
    SendCodeResponse,
    VerificationCodeInfo,
    VerificationCodeLoginRequest,
)

router = APIRouter(prefix="", tags=["auth"])


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request"""
    client_ip = request.client.host if request.client else "unknown"
    # Check for reverse proxy headers
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    elif request.headers.get("X-Real-IP"):
        client_ip = request.headers.get("X-Real-IP")
    return client_ip


def get_device_info(request: Request) -> dict:
    """Extract device information from request headers"""
    user_agent = request.headers.get("User-Agent", "")

    # Try to parse device info from custom headers (if client sends them)
    return {
        "device_type": request.headers.get("X-Device-Type"),
        "device_model": request.headers.get("X-Device-Model"),
        "os_type": request.headers.get("X-OS-Type"),
        "os_version": request.headers.get("X-OS-Version"),
        "app_version": request.headers.get("X-App-Version"),
        "user_agent": user_agent
    }


@router.post("/auth/send-code", response_model=SendCodeResponse)
async def send_verification_code(
    payload: SendCodeRequest,
    request: Request,
    session: SessionDep
) -> Any:
    """
    发送验证码

    - **phone**: 手机号（11位中国手机号）

    频率限制：
    - 每个手机号: 5次/分钟
    - 每个IP地址: 10次/分钟
    """
    phone = payload.phone
    client_ip = get_client_ip(request)

    # Initialize auth service
    auth_service = AuthService(db_session=session)

    try:
        # Send verification code through service
        response = await auth_service.send_verification_code(
            phone=phone,
            ip_address=client_ip
        )

        # Log audit event
        audit_service.log_code_sent(phone=phone, ip_address=client_ip)

        return response

    except RateLimitError as e:
        # Log rate limit exceeded
        audit_service.log_rate_limit_exceeded(
            resource="send_verification_code",
            identifier=phone,
            ip_address=client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=e.user_message,
            headers={"Retry-After": str(e.retry_after)} if e.retry_after else {}
        )

    except VerificationCodeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.user_message
        )


@router.post("/auth/login", response_model=LoginResponse)
async def login_with_verification_code(
    login_request: VerificationCodeLoginRequest,
    request: Request,
    session: SessionDep
) -> Any:
    """
    验证码登录

    - **phone**: 手机号
    - **verification_code**: 验证码

    Returns JWT token with session_id for session management
    """
    phone = login_request.phone
    code = login_request.code
    client_ip = get_client_ip(request)
    device_info = get_device_info(request)

    # Initialize auth service
    auth_service = AuthService(db_session=session)

    try:
        # Verify code and login through service
        response = await auth_service.verify_and_login(
            phone=phone,
            code=code,
            ip_address=client_ip,
            **device_info
        )

        # Log successful login
        audit_service.log_login_success(
            user_id=str(response.user.id),
            phone=phone,
            ip_address=client_ip
        )

        # Log code verified
        audit_service.log_code_verified(
            phone=phone,
            user_id=str(response.user.id),
            ip_address=client_ip
        )

        return response

    except AuthenticationError as e:
        # Log failed login
        audit_service.log_login_failed(
            phone=phone,
            ip_address=client_ip,
            reason=e.internal_message
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.user_message
        )


# 开发环境专用接口
if settings.ENVIRONMENT == "local":

    @router.get("/dev/verification-codes/{phone}", response_model=VerificationCodeInfo)
    async def get_verification_code(
        phone: str,
        session: SessionDep
    ) -> Any:
        """
        获取指定手机号的当前验证码（仅开发环境）

        - **phone**: 手机号

        **安全提示**: 此端点仅供开发/测试使用，生产环境禁用
        """
        # SECURITY: Only allow in development environment
        if settings.ENVIRONMENT == "production":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Not found"
            )

        # Initialize auth service
        auth_service = AuthService(db_session=session)

        # Get code info through service
        code_info = await auth_service.get_verification_code_info(phone)

        if not code_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="未找到该手机号的验证码"
            )

        return VerificationCodeInfo(
            phone=phone,
            code=code_info["code"],
            created_at=code_info["created_at"],
            expires_at=code_info["expires_at"],
            attempts=int(code_info.get("attempts", 0))
        )
