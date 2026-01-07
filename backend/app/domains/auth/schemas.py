"""
Authentication domain schemas (Request/Response models)
Pydantic models for API requests and responses
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import field_validator
from sqlmodel import Field, SQLModel

# =============================================================================
# User Schemas
# =============================================================================

class UserCreate(SQLModel):
    """Create user model"""
    phone: str = Field(max_length=20, description="手机号")
    nickname: Optional[str] = Field(default=None, max_length=50, description="昵称")
    preferred_foot: Optional[str] = Field(default=None, description="惯用脚设置")

    @field_validator('preferred_foot')
    @classmethod
    def validate_preferred_foot(cls, v: Optional[str]) -> Optional[str]:
        """Validate preferred foot value (goofy or regular)."""
        if v is not None and v not in ['goofy', 'regular']:
            raise ValueError('preferred_foot must be either "goofy" or "regular"')
        return v

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone number format."""
        clean_phone = v.replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
        if not clean_phone.isdigit():
            raise ValueError('Invalid phone number format')
        return v


class UserUpdate(SQLModel):
    """Update user model"""
    nickname: Optional[str] = Field(default=None, max_length=50)
    avatar_url: Optional[str] = Field(default=None)
    preferred_foot: Optional[str] = Field(default=None)
    level: Optional[str] = Field(default=None, max_length=20)
    level_description: Optional[str] = Field(default=None)


class UserUpdateMe(SQLModel):
    """User self-update model"""
    nickname: Optional[str] = Field(default=None, max_length=50)
    avatar_url: Optional[str] = Field(default=None)
    preferred_foot: Optional[str] = Field(default=None)


class UserPublic(SQLModel):
    """Public user information"""
    id: uuid.UUID
    phone: str
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    preferred_foot: Optional[str] = None
    level: str
    level_description: Optional[str] = None
    total_skiing_days: int
    total_skiing_hours: Decimal
    total_skiing_sessions: int
    average_speed: Decimal
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None


class UsersPublic(SQLModel):
    """List of public users"""
    data: list[UserPublic]
    count: int


# =============================================================================
# Verification Code Schemas
# =============================================================================

class SendCodeRequest(SQLModel):
    """Send verification code request"""
    phone: str = Field(max_length=20, description="手机号")

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone number format."""
        import re
        # Chinese phone number format validation
        pattern = r'^1[3-9]\d{9}$'
        if not re.match(pattern, v):
            raise ValueError('Invalid phone number format')
        return v


class SendCodeResponse(SQLModel):
    """Send verification code response"""
    success: bool = Field(description="是否发送成功")
    message: str = Field(description="响应消息")
    expires_in: int = Field(description="验证码有效期（秒）")


class VerificationCodeLoginRequest(SQLModel):
    """Verification code login request"""
    phone: str = Field(max_length=20, description="手机号")
    code: str = Field(max_length=6, description="验证码", alias="verification_code")

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone number format."""
        import re
        pattern = r'^1[3-9]\d{9}$'
        if not re.match(pattern, v):
            raise ValueError('Invalid phone number format')
        return v

    @field_validator('code')
    @classmethod
    def validate_verification_code(cls, v: str) -> str:
        if not v.isdigit() or len(v) != 6:
            raise ValueError('Verification code must be 6 digits')
        return v

    class Config:
        populate_by_name = True  # Allow both 'code' and 'verification_code'


class LoginResponse(SQLModel):
    """Login response"""
    access_token: str = Field(description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(description="令牌过期时间（秒）")
    user: UserPublic = Field(description="用户信息")


# =============================================================================
# Token Schemas
# =============================================================================

class Token(SQLModel):
    """JWT token"""
    access_token: str
    token_type: str = "bearer"


class TokenPayload(SQLModel):
    """JWT token payload"""
    sub: Optional[str] = None  # User ID
    exp: Optional[int] = None  # Expiration time
    sid: Optional[str] = None  # Session ID (for session management)


# =============================================================================
# Session Schemas
# =============================================================================

class UserSessionPublic(SQLModel):
    """Public session information"""
    id: uuid.UUID
    user_id: uuid.UUID
    session_token: str
    ip_address: Optional[str] = None
    expires_at: datetime
    created_at: datetime
    last_activity_at: datetime
    is_active: bool
    device_type: Optional[str] = None
    device_model: Optional[str] = None
    os_type: Optional[str] = None
    os_version: Optional[str] = None
    app_version: Optional[str] = None
    device_info: Optional[dict[str, Any]] = None


class SessionsPublic(SQLModel):
    """List of sessions"""
    data: list[UserSessionPublic]
    count: int


class LogoutRequest(SQLModel):
    """Logout request"""
    session_id: Optional[str] = Field(default=None, description="Session ID to logout (optional)")


class LogoutResponse(SQLModel):
    """Logout response"""
    success: bool
    message: str


# =============================================================================
# Development/Debug Schemas
# =============================================================================

class VerificationCodeInfo(SQLModel):
    """Verification code info (development only)"""
    phone: str = Field(description="手机号")
    code: str = Field(description="验证码")
    created_at: str = Field(description="创建时间")
    expires_at: str = Field(description="过期时间")
    attempts: int = Field(description="尝试次数")
