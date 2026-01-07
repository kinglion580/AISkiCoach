"""
Authentication domain models (Database tables)
Extracted from app.models - User, UserAuth, UserSession
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import field_validator
from sqlalchemy import Column, Index
from sqlalchemy.dialects.postgresql import JSON as PostgresJSON
from sqlmodel import Field, Relationship, SQLModel

# =============================================================================
# User Models
# =============================================================================

class UserBase(SQLModel):
    """User base model"""
    phone: str = Field(unique=True, index=True, max_length=20, description="手机号")
    nickname: Optional[str] = Field(default=None, max_length=50, description="昵称")
    avatar_url: Optional[str] = Field(default=None, description="头像URL")
    preferred_foot: Optional[str] = Field(
        default=None,
        description="惯用脚设置：goofy(右脚在前) 或 regular(左脚在前)"
    )
    level: str = Field(default="Dexter", max_length=20, description="用户滑雪等级")
    level_description: Optional[str] = Field(default=None, description="等级描述")
    total_skiing_days: int = Field(default=0, ge=0, description="总滑雪天数")
    total_skiing_hours: Decimal = Field(
        default=Decimal("0.0"),
        ge=0,
        max_digits=10,
        decimal_places=2,
        description="总滑雪时长(小时)"
    )
    total_skiing_sessions: int = Field(default=0, ge=0, description="总滑雪次数")
    average_speed: Decimal = Field(
        default=Decimal("0.0"),
        ge=0,
        max_digits=5,
        decimal_places=2,
        description="平均速度(km/h)"
    )
    is_active: bool = Field(default=True, description="账户是否激活")

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
        # Simple phone number format validation
        clean_phone = v.replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
        if not clean_phone.isdigit():
            raise ValueError('Invalid phone number format')
        return v


class User(UserBase, table=True):
    """User database table"""
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)
    last_login_at: Optional[datetime] = Field(default=None)

    # Relationships
    auth_records: list["UserAuth"] = Relationship(
        back_populates="user",
        cascade_delete=True
    )
    sessions: list["UserSession"] = Relationship(
        back_populates="user",
        cascade_delete=True
    )


# =============================================================================
# UserAuth Models (Authentication records)
# =============================================================================

class UserAuthBase(SQLModel):
    """User authentication base model"""
    phone: str = Field(max_length=20, description="手机号")
    verification_code: Optional[str] = Field(default=None, max_length=6, description="验证码")
    code_attempts: int = Field(default=0, ge=0, description="验证码尝试次数")
    is_verified: bool = Field(default=False, description="是否已验证")


class UserAuth(UserAuthBase, table=True):
    """User authentication database table"""
    __tablename__ = "user_auth"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    code_expires_at: Optional[datetime] = Field(default=None, description="验证码过期时间")
    last_attempt_at: Optional[datetime] = Field(default=None, description="最后尝试时间")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)

    # Relationships
    user: User = Relationship(back_populates="auth_records")


# =============================================================================
# UserSession Models (Login sessions)
# =============================================================================

class UserSessionBase(SQLModel):
    """User session base model"""
    session_token: str = Field(unique=True, max_length=255, description="会话令牌")
    ip_address: Optional[str] = Field(default=None, max_length=45, description="IP地址")
    is_active: bool = Field(default=True, description="会话是否活跃")


class UserSession(UserSessionBase, table=True):
    """User session database table"""
    __tablename__ = "user_sessions"
    __table_args__ = (
        Index(
            "ix_user_sessions_user_active_expires",
            "user_id", "is_active", "expires_at",
            postgresql_where="is_active = true"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    expires_at: datetime = Field(description="过期时间")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity_at: datetime = Field(default_factory=datetime.utcnow, description="最后活动时间")

    # Device information fields
    device_type: Optional[str] = Field(default=None, max_length=50, description="设备类型")
    device_model: Optional[str] = Field(default=None, max_length=100, description="设备型号")
    os_type: Optional[str] = Field(default=None, max_length=20, description="操作系统类型")
    os_version: Optional[str] = Field(default=None, max_length=50, description="操作系统版本")
    app_version: Optional[str] = Field(default=None, max_length=20, description="应用版本")
    user_agent: Optional[str] = Field(default=None, max_length=500, description="用户代理")

    # Extended device info (JSON format)
    device_info: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column(PostgresJSON),
        description="扩展设备信息JSON"
    )

    # Relationships
    user: User = Relationship(back_populates="sessions")
