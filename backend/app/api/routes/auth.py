"""
验证码登录和认证相关API
"""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, status, Depends
from sqlmodel import Session, select

from app.api.deps import SessionDep
from app.core.config import settings
from app.core.security import create_access_token
from app.models import (
    SendCodeRequest, 
    SendCodeResponse, 
    VerificationCodeLoginRequest, 
    LoginResponse,
    VerificationCodeInfo,
    User,
    UserCreate
)
from app.core.verification_code import verification_code_service, sms_service

router = APIRouter(prefix="", tags=["auth"])


@router.post("/auth/send-code", response_model=SendCodeResponse)
def send_verification_code(
    request: SendCodeRequest,
    session: SessionDep
) -> Any:
    """
    发送验证码
    
    - **phone**: 手机号（11位中国手机号）
    """
    
    phone = request.phone
    
    # 验证手机号格式
    if not verification_code_service.validate_phone(phone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="手机号格式不正确"
        )
    
    # 检查发送频率限制
    if not verification_code_service.check_rate_limit(phone):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"发送过于频繁，请{settings.VERIFICATION_CODE_RATE_LIMIT_MINUTES}分钟后再试"
        )
    
    # 生成验证码
    code = verification_code_service.generate_code()
    
    # 开发环境使用固定验证码
    if settings.ENVIRONMENT == "local":
        code = "123456"
    
    # 存储验证码
    if not verification_code_service.store_code(phone, code):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="验证码存储失败"
        )
    
    # 发送短信
    if not sms_service.send_verification_code(phone, code):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="验证码发送失败"
        )
    
    return SendCodeResponse(
        success=True,
        message="验证码发送成功",
        expires_in=settings.VERIFICATION_CODE_EXPIRE_MINUTES * 60
    )


@router.post("/auth/login", response_model=LoginResponse)
def login_with_verification_code(
    request: VerificationCodeLoginRequest,
    session: SessionDep
) -> Any:
    """
    验证码登录
    
    - **phone**: 手机号
    - **verification_code**: 验证码
    """
    
    phone = request.phone
    verification_code = request.verification_code
    
    # 验证验证码
    if not verification_code_service.verify_code(phone, verification_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码错误或已过期"
        )
    
    # 查找用户
    user = session.exec(select(User).where(User.phone == phone)).first()
    
    if not user:
        # 创建新用户
        user = User(
            phone=phone,
            nickname=f"用户{phone[-4:]}"  # 使用手机号后4位作为默认昵称
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    
    # 检查用户是否激活
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户账户已被禁用"
        )
    
    # 生成访问令牌
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=str(user.id), expires_delta=access_token_expires
    )
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user
    )


# 开发环境专用接口
if settings.ENVIRONMENT == "local":
    
    @router.post("/dev/test-verify-code")
    def test_verify_code(
        request: VerificationCodeLoginRequest
    ) -> Any:
        """
        测试验证码验证（仅开发环境）
        """
        phone = request.phone
        verification_code = request.verification_code
        
        # 验证验证码
        result = verification_code_service.verify_code(phone, verification_code)
        
        return {
            "phone": phone,
            "verification_code": verification_code,
            "verify_result": result
        }
    
    @router.post("/dev/test-create-user")
    def test_create_user(
        request: SendCodeRequest,
        session: SessionDep
    ) -> Any:
        """
        测试用户创建（仅开发环境）
        """
        phone = request.phone
        
        try:
            # 查找用户
            user = session.exec(select(User).where(User.phone == phone)).first()
            
            if not user:
                # 创建新用户
                user = User(
                    phone=phone,
                    nickname=f"用户{phone[-4:]}"  # 使用手机号后4位作为默认昵称
                )
                session.add(user)
                session.commit()
                session.refresh(user)
            
            return {
                "phone": phone,
                "user_id": str(user.id),
                "nickname": user.nickname,
                "is_active": user.is_active
            }
        except Exception as e:
            return {
                "error": str(e),
                "phone": phone
            }
    
    @router.get("/dev/verification-codes/{phone}", response_model=VerificationCodeInfo)
    def get_verification_code(
        phone: str
    ) -> Any:
        """
        获取指定手机号的当前验证码（仅开发环境）
        
        - **phone**: 手机号
        """
        if not verification_code_service.validate_phone(phone):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="手机号格式不正确"
            )
        
        code_info = verification_code_service.get_stored_code(phone)
        if not code_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="未找到该手机号的验证码"
            )
        
        # 计算过期时间
        created_at = datetime.fromisoformat(code_info["created_at"])
        expires_at = created_at + timedelta(seconds=settings.VERIFICATION_CODE_EXPIRE_MINUTES * 60)
        
        return VerificationCodeInfo(
            phone=phone,
            code=code_info["code"],
            created_at=code_info["created_at"],
            expires_at=expires_at.isoformat(),
            attempts=code_info["attempts"]
        )
    
    @router.post("/dev/send-test-code", response_model=SendCodeResponse)
    def send_test_code(
        request: SendCodeRequest,
        session: SessionDep
    ) -> Any:
        """
        发送测试验证码（仅开发环境）
        
        - **phone**: 手机号
        """
        phone = request.phone
        
        # 验证手机号格式
        if not verification_code_service.validate_phone(phone):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="手机号格式不正确"
            )
        
        # 使用固定测试验证码
        test_code = "123456"
        
        # 存储验证码
        if not verification_code_service.store_code(phone, test_code):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="验证码存储失败"
            )
        
        return SendCodeResponse(
            success=True,
            message=f"测试验证码已发送到 {phone}: {test_code}",
            expires_in=settings.VERIFICATION_CODE_EXPIRE_MINUTES * 60
        )
