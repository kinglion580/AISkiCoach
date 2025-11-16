import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, Any, List

from pydantic import EmailStr, Field, field_validator
from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy import Column, JSON
from sqlalchemy.dialects.postgresql import JSON as PostgresJSON


# =============================================================================
# 滑雪应用用户模型 (Skiing App User Models)
# =============================================================================

# 滑雪用户基础属性
class UserBase(SQLModel):
    """滑雪用户基础信息模型"""
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
        if v is not None and v not in ['goofy', 'regular']:
            raise ValueError('preferred_foot must be either "goofy" or "regular"')
        return v

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        # 简单的手机号格式验证
        clean_phone = v.replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
        if not clean_phone.isdigit():
            raise ValueError('Invalid phone number format')
        return v


# 滑雪用户创建模型（通过手机验证码注册，无需密码）
class UserCreate(SQLModel):
    """创建滑雪用户时使用的模型"""
    phone: str = Field(max_length=20, description="手机号")
    nickname: Optional[str] = Field(default=None, max_length=50, description="昵称")
    preferred_foot: Optional[str] = Field(default=None, description="惯用脚设置")

    @field_validator('preferred_foot')
    @classmethod
    def validate_preferred_foot(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ['goofy', 'regular']:
            raise ValueError('preferred_foot must be either "goofy" or "regular"')
        return v

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        # 简单的手机号格式验证
        clean_phone = v.replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
        if not clean_phone.isdigit():
            raise ValueError('Invalid phone number format')
        return v


# 滑雪用户更新模型
class UserUpdate(SQLModel):
    """更新滑雪用户信息的模型"""
    nickname: Optional[str] = Field(default=None, max_length=50)
    avatar_url: Optional[str] = Field(default=None)
    preferred_foot: Optional[str] = Field(default=None)
    level: Optional[str] = Field(default=None, max_length=20)
    level_description: Optional[str] = Field(default=None)


class UserUpdateMe(SQLModel):
    """用户自行更新个人信息"""
    nickname: Optional[str] = Field(default=None, max_length=50)
    avatar_url: Optional[str] = Field(default=None)
    preferred_foot: Optional[str] = Field(default=None)


# 手机验证码相关模型
class VerificationCodeRequest(SQLModel):
    """验证码请求模型"""
    phone: str = Field(max_length=20, description="手机号")

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        # 简单的手机号格式验证
        clean_phone = v.replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
        if not clean_phone.isdigit():
            raise ValueError('Invalid phone number format')
        return v


class VerificationCodeVerify(SQLModel):
    """验证码验证模型"""
    phone: str = Field(max_length=20, description="手机号")
    code: str = Field(max_length=6, description="验证码")

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        # 简单的手机号格式验证
        clean_phone = v.replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
        if not clean_phone.isdigit():
            raise ValueError('Invalid phone number format')
        return v


# 滑雪用户数据库模型
class User(UserBase, table=True):
    """滑雪用户数据库表模型"""
    __tablename__ = "users"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)
    last_login_at: Optional[datetime] = Field(default=None)
    
    # 滑雪应用关系
    auth_records: list["UserAuth"] = Relationship(
        back_populates="user", 
        cascade_delete=True
    )
    sessions: list["UserSession"] = Relationship(
        back_populates="user", 
        cascade_delete=True
    )
    user_devices: list["UserDevice"] = Relationship(
        back_populates="user", 
        cascade_delete=True
    )
    device_calibrations: list["DeviceCalibration"] = Relationship(
        back_populates="user", 
        cascade_delete=True
    )
    skiing_sessions: list["SkiingSession"] = Relationship(
        back_populates="user", 
        cascade_delete=True
    )
    imu_data: list["IMUData"] = Relationship(
        back_populates="user", 
        cascade_delete=True
    )
    gps_data: list["GPSData"] = Relationship(
        back_populates="user", 
        cascade_delete=True
    )
    barometer_data: list["BarometerData"] = Relationship(
        back_populates="user", 
        cascade_delete=True
    )
    skiing_metrics: list["SkiingMetric"] = Relationship(
        back_populates="user", 
        cascade_delete=True
    )
    ai_analyses: list["AIAnalysis"] = Relationship(
        back_populates="user", 
        cascade_delete=True
    )
    
    # 保持与现有架构的兼容性（临时保留Item关系）
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)


# 滑雪用户公开信息模型
class UserPublic(UserBase):
    """通过API返回的滑雪用户公开信息"""
    id: uuid.UUID
    created_at: datetime
    last_login_at: Optional[datetime] = None


class UsersPublic(SQLModel):
    """滑雪用户列表响应"""
    data: list[UserPublic]
    count: int


# =============================================================================
# 用户认证和会话管理模型 (User Authentication & Session Models)
# =============================================================================

# 用户认证基础模型
class UserAuthBase(SQLModel):
    """用户认证基础模型"""
    phone: str = Field(max_length=20, description="手机号")
    verification_code: Optional[str] = Field(default=None, max_length=6, description="验证码")
    code_attempts: int = Field(default=0, ge=0, description="验证码尝试次数")
    is_verified: bool = Field(default=False, description="是否已验证")


class UserAuthCreate(SQLModel):
    """创建用户认证记录"""
    phone: str = Field(max_length=20, description="手机号")
    verification_code: str = Field(max_length=6, description="验证码")

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        clean_phone = v.replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
        if not clean_phone.isdigit():
            raise ValueError('Invalid phone number format')
        return v


class UserAuth(UserAuthBase, table=True):
    """用户认证数据库表"""
    __tablename__ = "user_auth"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    code_expires_at: Optional[datetime] = Field(default=None, description="验证码过期时间")
    last_attempt_at: Optional[datetime] = Field(default=None, description="最后尝试时间")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)

    # 关系
    user: User = Relationship(back_populates="auth_records")


# 用户会话基础模型
class UserSessionBase(SQLModel):
    """用户会话基础模型"""
    session_token: str = Field(unique=True, max_length=255, description="会话令牌")
    ip_address: Optional[str] = Field(default=None, max_length=45, description="IP地址")


class UserSessionCreate(SQLModel):
    """创建用户会话"""
    session_token: str = Field(unique=True, max_length=255, description="会话令牌")
    ip_address: Optional[str] = Field(default=None, max_length=45, description="IP地址")
    device_info: Optional[dict[str, Any]] = Field(default=None, description="设备信息")
    expires_at: datetime = Field(description="过期时间")


class UserSession(UserSessionBase, table=True):
    """用户会话数据库表"""
    __tablename__ = "user_sessions"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    expires_at: datetime = Field(description="过期时间")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity_at: datetime = Field(default_factory=datetime.utcnow, description="最后活动时间")
    
    # 设备信息字段（从device_info dict拆分）
    device_type: Optional[str] = Field(default=None, max_length=50, description="设备类型")
    device_model: Optional[str] = Field(default=None, max_length=100, description="设备型号")
    os_type: Optional[str] = Field(default=None, max_length=20, description="操作系统类型")
    os_version: Optional[str] = Field(default=None, max_length=50, description="操作系统版本")
    app_version: Optional[str] = Field(default=None, max_length=20, description="应用版本")
    user_agent: Optional[str] = Field(default=None, max_length=500, description="用户代理")
    
    # 扩展设备信息（JSON格式，符合文档要求）
    device_info: Optional[dict[str, Any]] = Field(
        default=None, 
        sa_column=Column(PostgresJSON), 
        description="扩展设备信息JSON"
    )

    # 关系
    user: User = Relationship(back_populates="sessions")


class UserSessionPublic(UserSessionBase):
    """用户会话公开信息"""
    id: uuid.UUID
    user_id: uuid.UUID
    expires_at: datetime
    created_at: datetime
    last_activity_at: datetime
    device_info: Optional[dict[str, Any]] = Field(default=None, description="设备信息")


# 认证响应模型
class AuthResponse(SQLModel):
    """认证响应模型"""
    user: UserPublic
    token: "Token"
    session_info: dict[str, Any] = Field(description="会话信息")


class LoginRequest(SQLModel):
    """登录请求模型"""
    phone: str = Field(max_length=20, description="手机号")
    verification_code: str = Field(max_length=6, description="验证码")

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        clean_phone = v.replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
        if not clean_phone.isdigit():
            raise ValueError('Invalid phone number format')
        return v


# =============================================================================
# 验证码相关模型 (Verification Code Models)
# =============================================================================

class SendCodeRequest(SQLModel):
    """发送验证码请求"""
    phone: str = Field(max_length=20, description="手机号")

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        import re
        # 中国手机号格式验证
        pattern = r'^1[3-9]\d{9}$'
        if not re.match(pattern, v):
            raise ValueError('Invalid phone number format')
        return v


class SendCodeResponse(SQLModel):
    """发送验证码响应"""
    success: bool = Field(description="是否发送成功")
    message: str = Field(description="响应消息")
    expires_in: int = Field(description="验证码有效期（秒）")


class VerificationCodeLoginRequest(SQLModel):
    """验证码登录请求"""
    phone: str = Field(max_length=20, description="手机号")
    verification_code: str = Field(max_length=6, description="验证码")

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        import re
        pattern = r'^1[3-9]\d{9}$'
        if not re.match(pattern, v):
            raise ValueError('Invalid phone number format')
        return v

    @field_validator('verification_code')
    @classmethod
    def validate_verification_code(cls, v: str) -> str:
        if not v.isdigit() or len(v) != 6:
            raise ValueError('Verification code must be 6 digits')
        return v


class LoginResponse(SQLModel):
    """登录响应"""
    access_token: str = Field(description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(description="令牌过期时间（秒）")
    user: UserPublic = Field(description="用户信息")


class VerificationCodeInfo(SQLModel):
    """验证码信息（开发环境使用）"""
    phone: str = Field(description="手机号")
    code: str = Field(description="验证码")
    created_at: str = Field(description="创建时间")
    expires_at: str = Field(description="过期时间")
    attempts: int = Field(description="尝试次数")


# =============================================================================
# 设备管理模型 (Device Management Models)
# =============================================================================

# 设备基础模型
class DeviceBase(SQLModel):
    """HeyGo滑雪设备基础模型"""
    device_id: str = Field(unique=True, max_length=20, description="设备ID，如382EL22G、590EL49Q")
    device_type: str = Field(max_length=20, description="设备类型：HeyGo A1/R1/R2")
    device_name: str = Field(max_length=50, description="设备名称")
    firmware_version: Optional[str] = Field(default=None, max_length=20, description="固件版本")
    battery_level: Optional[int] = Field(default=None, ge=0, le=100, description="电量百分比")
    connection_status: str = Field(default="disconnected", max_length=20, description="连接状态")

    @field_validator('device_type')
    @classmethod
    def validate_device_type(cls, v: str) -> str:
        if v not in ['HeyGo A1', 'HeyGo R1', 'HeyGo R2']:
            raise ValueError('device_type must be one of: HeyGo A1, HeyGo R1, HeyGo R2')
        return v

    @field_validator('connection_status')
    @classmethod
    def validate_connection_status(cls, v: str) -> str:
        if v not in ['connected', 'disconnected', 'connecting', 'error']:
            raise ValueError('connection_status must be one of: connected, disconnected, connecting, error')
        return v


class DeviceCreate(SQLModel):
    """创建设备"""
    device_id: str = Field(max_length=20, description="设备ID")
    device_type: str = Field(max_length=20, description="设备类型")
    device_name: str = Field(max_length=50, description="设备名称")
    firmware_version: Optional[str] = Field(default=None, max_length=20)

    @field_validator('device_type')
    @classmethod
    def validate_device_type(cls, v: str) -> str:
        if v not in ['HeyGo A1', 'HeyGo R1', 'HeyGo R2']:
            raise ValueError('device_type must be one of: HeyGo A1, HeyGo R1, HeyGo R2')
        return v


class DeviceUpdate(SQLModel):
    """更新设备信息"""
    device_name: Optional[str] = Field(default=None, max_length=50)
    firmware_version: Optional[str] = Field(default=None, max_length=20)
    battery_level: Optional[int] = Field(default=None, ge=0, le=100)
    connection_status: Optional[str] = Field(default=None, max_length=20)


class Device(DeviceBase, table=True):
    """HeyGo设备数据库表"""
    __tablename__ = "devices"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    last_seen_at: Optional[datetime] = Field(default=None, description="最后在线时间")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)

    # 关系
    user_devices: list["UserDevice"] = Relationship(
        back_populates="device", 
        cascade_delete=True
    )
    calibrations: list["DeviceCalibration"] = Relationship(
        back_populates="device", 
        cascade_delete=True
    )

    @field_validator('device_type')
    @classmethod
    def validate_device_type(cls, v: str) -> str:
        if v not in ['HeyGo A1', 'HeyGo R1', 'HeyGo R2']:
            raise ValueError('device_type must be one of: HeyGo A1, HeyGo R1, HeyGo R2')
        return v

    @field_validator('connection_status')
    @classmethod
    def validate_connection_status(cls, v: str) -> str:
        if v not in ['connected', 'disconnected', 'connecting', 'error']:
            raise ValueError('connection_status must be one of: connected, disconnected, connecting, error')
        return v


class DevicePublic(DeviceBase):
    """设备公开信息"""
    id: uuid.UUID
    last_seen_at: Optional[datetime] = None
    created_at: datetime


# 用户设备关联模型
class UserDeviceBase(SQLModel):
    """用户设备关联基础模型"""
    is_primary: bool = Field(default=False, description="是否为主设备")


class UserDeviceCreate(SQLModel):
    """创建用户设备关联"""
    device_id: uuid.UUID = Field(description="设备ID")
    is_primary: bool = Field(default=False, description="是否为主设备")


class UserDevice(UserDeviceBase, table=True):
    """用户设备关联表"""
    __tablename__ = "user_devices"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    device_id: uuid.UUID = Field(foreign_key="devices.id", index=True)
    connected_at: Optional[datetime] = Field(default=None, description="连接时间")
    disconnected_at: Optional[datetime] = Field(default=None, description="断开连接时间")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # 关系
    user: User = Relationship(back_populates="user_devices")
    device: Device = Relationship(back_populates="user_devices")


# 设备校准模型
class DeviceCalibrationBase(SQLModel):
    """设备校准基础模型"""
    calibration_step: int = Field(ge=1, le=4, description="校准步骤(1-4)")
    calibration_status: str = Field(default="pending", max_length=20, description="校准状态")

    @field_validator('calibration_status')
    @classmethod
    def validate_calibration_status(cls, v: str) -> str:
        if v not in ['pending', 'in_progress', 'completed', 'failed']:
            raise ValueError('calibration_status must be one of: pending, in_progress, completed, failed')
        return v


class DeviceCalibrationCreate(SQLModel):
    """创建设备校准记录"""
    device_id: uuid.UUID = Field(description="设备ID")
    calibration_step: int = Field(ge=1, le=4, description="校准步骤")
    calibration_status: str = Field(default="pending", max_length=20, description="校准状态")


class DeviceCalibration(DeviceCalibrationBase, table=True):
    """设备校准数据表"""
    __tablename__ = "device_calibrations"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    device_id: uuid.UUID = Field(foreign_key="devices.id", index=True)
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # 校准数据字段（用于存储偏移量等基础数据）
    # 加速度计偏移
    acc_offset_x: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=6, description="加速度计X轴偏移")
    acc_offset_y: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=6, description="加速度计Y轴偏移")
    acc_offset_z: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=6, description="加速度计Z轴偏移")
    # 陀螺仪偏移
    gyro_offset_x: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=6, description="陀螺仪X轴偏移")
    gyro_offset_y: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=6, description="陀螺仪Y轴偏移")
    gyro_offset_z: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=6, description="陀螺仪Z轴偏移")
    # 磁力计校准
    mag_offset_x: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=6, description="磁力计X轴偏移")
    mag_offset_y: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=6, description="磁力计Y轴偏移")
    mag_offset_z: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=6, description="磁力计Z轴偏移")
    # 校准精度
    calibration_accuracy: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="校准精度评分")
    
    # 新增：结构化校准结果字段
    # 旋转矩阵（3x3矩阵，存储为JSON）
    rotation_matrix: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column(PostgresJSON),
        description="旋转矩阵 R_board_to_imu (3x3)"
    )
    # 安装角度（3个角度值，存储为JSON数组）
    installation_angles: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column(PostgresJSON),
        description="安装角度 [x, y, z]"
    )
    # 纯度分数
    purity: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=6, description="校准纯度分数")
    # 静态窗口索引
    static_window_start: Optional[int] = Field(default=None, description="静态窗口起始索引")
    static_window_end: Optional[int] = Field(default=None, description="静态窗口结束索引")
    # 旋转窗口索引
    rotation_window_start: Optional[int] = Field(default=None, description="旋转窗口起始索引")
    rotation_window_end: Optional[int] = Field(default=None, description="旋转窗口结束索引")
    # 算法参数
    static_window_size: Optional[int] = Field(default=None, description="静态窗口大小")
    rotation_window_size: Optional[int] = Field(default=None, description="旋转窗口大小")
    rotation_purity_threshold: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="旋转纯度阈值")
    # 统计信息
    total_samples: Optional[int] = Field(default=None, description="总样本数")
    sample_rate: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=2, description="采样率(Hz)")
    # 失败原因
    failure_reason: Optional[str] = Field(default=None, description="校准失败原因")

    # 关系
    user: User = Relationship(back_populates="device_calibrations")
    device: Device = Relationship(back_populates="calibrations")
    samples: list["DeviceCalibrationSample"] = Relationship(
        back_populates="calibration",
        cascade_delete=True
    )


class DeviceCalibrationSample(SQLModel, table=True):
    """设备校准原始数据样本表"""
    __tablename__ = "device_calibration_samples"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    calibration_id: uuid.UUID = Field(foreign_key="device_calibrations.id", index=True, description="校准记录ID")
    sample_index: int = Field(index=True, description="样本在序列中的索引")
    timestamp: Optional[datetime] = Field(default=None, index=True, description="时间戳")
    # 加速度数据（单位：g）
    acc_x: Decimal = Field(max_digits=10, decimal_places=6, description="加速度X (g)")
    acc_y: Decimal = Field(max_digits=10, decimal_places=6, description="加速度Y (g)")
    acc_z: Decimal = Field(max_digits=10, decimal_places=6, description="加速度Z (g)")
    # 陀螺仪数据（单位：rad/s）
    gyro_x: Decimal = Field(max_digits=10, decimal_places=6, description="陀螺仪X (rad/s)")
    gyro_y: Decimal = Field(max_digits=10, decimal_places=6, description="陀螺仪Y (rad/s)")
    gyro_z: Decimal = Field(max_digits=10, decimal_places=6, description="陀螺仪Z (rad/s)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # 关系
    calibration: "DeviceCalibration" = Relationship(back_populates="samples")


class DeviceCalibrationPublic(SQLModel):
    """设备校准公开信息"""
    id: uuid.UUID
    user_id: uuid.UUID
    device_id: uuid.UUID
    calibration_step: int
    calibration_status: str
    # 结构化校准结果
    rotation_matrix: Optional[List[List[float]]] = None
    installation_angles: Optional[List[float]] = None
    purity: Optional[Decimal] = None
    static_window_start: Optional[int] = None
    static_window_end: Optional[int] = None
    rotation_window_start: Optional[int] = None
    rotation_window_end: Optional[int] = None
    total_samples: Optional[int] = None
    sample_rate: Optional[Decimal] = None
    failure_reason: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


# 设备连接请求模型
class DeviceConnectionRequest(SQLModel):
    """设备连接请求"""
    device_id: str = Field(max_length=20, description="设备ID")
    device_type: str = Field(max_length=20, description="设备类型")
    device_name: Optional[str] = Field(default=None, max_length=50, description="设备名称")


class DeviceConnectionResponse(SQLModel):
    """设备连接响应"""
    device: DevicePublic
    connection_status: str = Field(description="连接状态")
    connection_info: dict[str, Any] = Field(description="连接信息")


# =============================================================================
# 滑雪会话和数据采集模型 (Skiing Session & Data Collection Models)
# =============================================================================

# 滑雪会话基础模型
class SkiingSessionBase(SQLModel):
    """滑雪会话基础模型"""
    session_name: str = Field(max_length=100, description="会话名称")
    location_name: Optional[str] = Field(default=None, max_length=100, description="滑雪场名称")
    session_status: str = Field(default="active", max_length=20, description="会话状态")

    @field_validator('session_status')
    @classmethod
    def validate_session_status(cls, v: str) -> str:
        if v not in ['active', 'paused', 'completed', 'cancelled']:
            raise ValueError('session_status must be one of: active, paused, completed, cancelled')
        return v


class SkiingSessionCreate(SQLModel):
    """创建滑雪会话"""
    session_name: str = Field(max_length=100, description="会话名称")
    location: Optional[str] = Field(default=None, max_length=100, description="滑雪地点")
    weather_conditions: Optional[str] = Field(default=None, max_length=50, description="天气条件")
    snow_conditions: Optional[str] = Field(default=None, max_length=50, description="雪况")
    difficulty_level: Optional[str] = Field(default=None, max_length=20, description="难度等级")


class SkiingSessionUpdate(SQLModel):
    """更新滑雪会话"""
    session_name: Optional[str] = Field(default=None, max_length=100)
    location: Optional[str] = Field(default=None, max_length=100)
    weather_conditions: Optional[str] = Field(default=None, max_length=50)
    snow_conditions: Optional[str] = Field(default=None, max_length=50)
    difficulty_level: Optional[str] = Field(default=None, max_length=20)
    session_status: Optional[str] = Field(default=None, max_length=20)


class SkiingSession(SkiingSessionBase, table=True):
    """滑雪会话数据库表"""
    __tablename__ = "skiing_sessions"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    device_id: Optional[uuid.UUID] = Field(default=None, foreign_key="devices.id", index=True)
    start_time: datetime = Field(default_factory=datetime.utcnow, description="开始时间")
    end_time: Optional[datetime] = Field(default=None, description="结束时间")
    duration_seconds: Optional[int] = Field(default=None, ge=0, description="滑行时长(秒)")
    max_edge_angle: Optional[Decimal] = Field(
        default=None, 
        ge=0, 
        le=90, 
        max_digits=5, 
        decimal_places=2, 
        description="最大立刃角度"
    )
    edge_time_ratio: Optional[Decimal] = Field(
        default=None, 
        ge=0, 
        max_digits=5, 
        decimal_places=2, 
        description="立刃时间占比"
    )
    total_distance: Optional[Decimal] = Field(
        default=None, 
        ge=0, 
        max_digits=10, 
        decimal_places=2, 
        description="总距离(米)"
    )
    max_speed: Optional[Decimal] = Field(
        default=None, 
        ge=0, 
        max_digits=5, 
        decimal_places=2, 
        description="最大速度(km/h)"
    )
    average_speed: Optional[Decimal] = Field(
        default=None, 
        ge=0, 
        max_digits=5, 
        decimal_places=2, 
        description="平均速度(km/h)"
    )
    # 会话元数据字段（从metadata dict拆分）
    weather_condition: Optional[str] = Field(default=None, max_length=50, description="天气条件")
    snow_type: Optional[str] = Field(default=None, max_length=20, description="雪质类型")
    difficulty_level: Optional[str] = Field(default=None, max_length=20, description="难度等级")
    slope_condition: Optional[str] = Field(default=None, max_length=20, description="坡面状况")
    temperature: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="温度(°C)")
    wind_speed: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="风速(m/s)")
    
    # 扩展会话元数据（JSON格式，符合文档要求）
    session_metadata: Optional[dict[str, Any]] = Field(
        default=None, 
        sa_column=Column(PostgresJSON), 
        description="扩展会话元数据JSON"
    )
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)

    # 关系
    user: User = Relationship(back_populates="skiing_sessions")
    device: Optional[Device] = Relationship()
    imu_data: list["IMUData"] = Relationship(back_populates="session", cascade_delete=True)
    gps_data: list["GPSData"] = Relationship(back_populates="session", cascade_delete=True)
    barometer_data: list["BarometerData"] = Relationship(back_populates="session", cascade_delete=True)
    skiing_metrics: list["SkiingMetric"] = Relationship(back_populates="session", cascade_delete=True)
    ai_analyses: list["AIAnalysis"] = Relationship(back_populates="session", cascade_delete=True)


class SkiingSessionPublic(SkiingSessionBase):
    """滑雪会话公开信息"""
    id: uuid.UUID
    user_id: uuid.UUID
    device_id: Optional[uuid.UUID] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    total_distance: Optional[Decimal] = None
    max_speed: Optional[Decimal] = None
    avg_speed: Optional[Decimal] = None
    created_at: datetime


# IMU传感器数据模型
class IMUDataBase(SQLModel):
    """IMU传感器数据基础模型"""
    timestamp: datetime = Field(description="时间戳")
    source_id: int = Field(description="数据源模块ID")
    # 硬件原始数据（BLE传输）
    acc_x: Decimal = Field(max_digits=10, decimal_places=6, description="加速度X (m/s²) - 硬件原始数据")
    acc_y: Decimal = Field(max_digits=10, decimal_places=6, description="加速度Y (m/s²) - 硬件原始数据")
    acc_z: Decimal = Field(max_digits=10, decimal_places=6, description="加速度Z (m/s²) - 硬件原始数据")
    gyro_x: Decimal = Field(max_digits=10, decimal_places=6, description="陀螺仪X (rad/s) - 硬件原始数据")
    gyro_y: Decimal = Field(max_digits=10, decimal_places=6, description="陀螺仪Y (rad/s) - 硬件原始数据")
    gyro_z: Decimal = Field(max_digits=10, decimal_places=6, description="陀螺仪Z (rad/s) - 硬件原始数据")
    mag_x: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=6, description="磁力计X (μT) - 硬件原始数据")
    mag_y: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=6, description="磁力计Y (μT) - 硬件原始数据")
    mag_z: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=6, description="磁力计Z (μT) - 硬件原始数据")
    # 算法处理数据（前端计算）
    quaternion_w: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=6, description="四元数W - 算法计算")
    quaternion_x: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=6, description="四元数X - 算法计算")
    quaternion_y: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=6, description="四元数Y - 算法计算")
    quaternion_z: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=6, description="四元数Z - 算法计算")
    euler_x: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=6, description="欧拉角X (度) - 算法计算")
    euler_y: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=6, description="欧拉角Y (度) - 算法计算")
    euler_z: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=6, description="欧拉角Z (度) - 算法计算")
    # 设备状态数据
    temperature: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="温度(°C) - IMU内置温度传感器")
    battery_level: Optional[int] = Field(default=None, ge=0, le=100, description="电量(%) - 设备电池监测")


class IMUDataCreate(SQLModel):
    """创建IMU数据批量"""
    session_id: uuid.UUID = Field(description="会话ID")
    data_points: list[dict[str, Any]] = Field(description="IMU数据点数组")


class IMUData(IMUDataBase, table=True):
    """IMU传感器数据表（时序数据，使用TimescaleDB优化）"""
    __tablename__ = "imu_data"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    device_id: uuid.UUID = Field(foreign_key="devices.id", index=True)
    session_id: uuid.UUID = Field(foreign_key="skiing_sessions.id", index=True)

    # 关系
    user: User = Relationship(back_populates="imu_data")
    device: Device = Relationship()
    session: SkiingSession = Relationship(back_populates="imu_data")


# GPS位置数据模型
class GPSDataBase(SQLModel):
    """GPS位置数据基础模型"""
    timestamp: datetime = Field(description="时间戳")
    source_id: int = Field(description="数据源模块ID")
    latitude: Decimal = Field(max_digits=10, decimal_places=8, description="纬度")
    longitude: Decimal = Field(max_digits=11, decimal_places=8, description="经度")
    altitude: Optional[Decimal] = Field(
        default=None, 
        max_digits=8, 
        decimal_places=2, 
        description="海拔(m)"
    )
    speed: Optional[Decimal] = Field(
        default=None, 
        ge=0, 
        max_digits=6, 
        decimal_places=2, 
        description="速度(m/s)"
    )
    accuracy: Optional[Decimal] = Field(
        default=None, 
        ge=0, 
        max_digits=6, 
        decimal_places=2, 
        description="精度(m)"
    )


class GPSDataCreate(SQLModel):
    """创建GPS数据批量"""
    session_id: uuid.UUID = Field(description="会话ID")
    data_points: list[dict[str, Any]] = Field(description="GPS数据点数组")


class GPSData(GPSDataBase, table=True):
    """GPS位置数据表（时序数据，使用TimescaleDB优化）"""
    __tablename__ = "gps_data"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    device_id: uuid.UUID = Field(foreign_key="devices.id", index=True)
    session_id: uuid.UUID = Field(foreign_key="skiing_sessions.id", index=True)

    # 关系
    user: User = Relationship(back_populates="gps_data")
    device: Device = Relationship()
    session: SkiingSession = Relationship(back_populates="gps_data")


# 气压计传感器数据模型
class BarometerDataBase(SQLModel):
    """气压计传感器数据基础模型"""
    timestamp: datetime = Field(description="时间戳")
    source_id: int = Field(description="数据源模块ID")
    pressure: Decimal = Field(max_digits=10, decimal_places=2, description="气压值")
    temperature: Optional[Decimal] = Field(
        default=None, 
        max_digits=5, 
        decimal_places=2, 
        description="温度(°C)"
    )


class BarometerDataCreate(SQLModel):
    """创建气压计数据批量"""
    session_id: uuid.UUID = Field(description="会话ID")
    data_points: list[dict[str, Any]] = Field(description="气压计数据点数组")


class BarometerData(BarometerDataBase, table=True):
    """气压计传感器数据表（时序数据，使用TimescaleDB优化）"""
    __tablename__ = "barometer_data"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    device_id: uuid.UUID = Field(foreign_key="devices.id", index=True)
    session_id: uuid.UUID = Field(foreign_key="skiing_sessions.id", index=True)

    # 关系
    user: User = Relationship(back_populates="barometer_data")
    device: Device = Relationship()
    session: SkiingSession = Relationship(back_populates="barometer_data")


# 滑雪指标数据模型（算法处理后的数据）
class SkiingMetricBase(SQLModel):
    """滑雪指标数据基础模型"""
    timestamp: datetime = Field(description="时间戳")
    # UI界面显示的核心指标
    edge_angle: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="立刃角度(度)")
    edge_angle_front: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="前刃角度(度)")
    edge_angle_back: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="后刃角度(度)")
    edge_angle_speed: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="立刃速度(度/秒) - UI显示需要")
    edge_angle_speed_front: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="前刃立刃速度(度/秒)")
    edge_angle_speed_back: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="后刃立刃速度(度/秒)")
    edge_displacement: Optional[Decimal] = Field(default=None, max_digits=8, decimal_places=2, description="走刃位移(米)")
    edge_displacement_front: Optional[Decimal] = Field(default=None, max_digits=8, decimal_places=2, description="前刃位移(米)")
    edge_displacement_back: Optional[Decimal] = Field(default=None, max_digits=8, decimal_places=2, description="后刃位移(米)")
    edge_time_ratio: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="立刃时间占比(%)")
    edge_duration_seconds: Optional[int] = Field(default=None, description="走刃维持时间(秒)")
    turn_detected: bool = Field(default=False, description="是否检测到转弯")
    turn_direction: Optional[str] = Field(default=None, max_length=10, description="转弯方向")
    turn_radius: Optional[Decimal] = Field(default=None, max_digits=8, decimal_places=2, description="转弯半径(米)")
    turn_duration_seconds: Optional[int] = Field(default=None, description="转弯时长(秒)")
    speed_kmh: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="速度(km/h)")
    slope_angle: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="坡面角度(度)")


class SkiingMetricCreate(SQLModel):
    """创建滑雪指标数据批量"""
    session_id: uuid.UUID = Field(description="会话ID")
    data_points: list[dict[str, Any]] = Field(description="指标数据点数组")


class SkiingMetric(SkiingMetricBase, table=True):
    """滑雪指标数据表（时序数据，使用TimescaleDB优化）"""
    __tablename__ = "skiing_metrics"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    device_id: uuid.UUID = Field(foreign_key="devices.id", index=True)
    session_id: uuid.UUID = Field(foreign_key="skiing_sessions.id", index=True)

    # 关系
    user: User = Relationship(back_populates="skiing_metrics")
    device: Device = Relationship()
    session: SkiingSession = Relationship(back_populates="skiing_metrics")


# =============================================================================
# AI分析模型 (AI Analysis Models)
# =============================================================================

# AI分析基础模型
class AIAnalysisBase(SQLModel):
    """AI分析基础模型"""
    analysis_type: str = Field(max_length=50, description="分析类型")
    performance_evaluation: Optional[str] = Field(default=None, description="表现评价")
    improvement_points: Optional[str] = Field(default=None, description="待提升点")
    advanced_suggestions: Optional[str] = Field(default=None, description="进阶建议")
    technical_insights: Optional[str] = Field(default=None, description="技术洞察")
    confidence_score: Optional[Decimal] = Field(
        default=None, 
        ge=0, 
        le=1, 
        max_digits=3, 
        decimal_places=2, 
        description="置信度分数"
    )


class AIAnalysisCreate(SQLModel):
    """创建AI分析"""
    session_id: uuid.UUID = Field(description="会话ID")
    analysis_type: str = Field(max_length=50, description="分析类型")
    performance_evaluation: Optional[str] = Field(default=None, description="表现评价")
    improvement_points: Optional[str] = Field(default=None, description="待提升点")
    advanced_suggestions: Optional[str] = Field(default=None, description="进阶建议")
    technical_insights: Optional[str] = Field(default=None, description="技术洞察")
    analysis_data: Optional[dict[str, Any]] = Field(default=None, description="详细分析数据")
    confidence_score: Optional[Decimal] = Field(default=None, ge=0, le=1, max_digits=3, decimal_places=2)


class AIAnalysisUpdate(SQLModel):
    """更新AI分析"""
    analysis_type: Optional[str] = Field(default=None, max_length=50)
    performance_evaluation: Optional[str] = Field(default=None)
    improvement_points: Optional[str] = Field(default=None)
    advanced_suggestions: Optional[str] = Field(default=None)
    technical_insights: Optional[str] = Field(default=None)
    confidence_score: Optional[Decimal] = Field(default=None, ge=0, le=1, max_digits=3, decimal_places=2)


class AIAnalysis(AIAnalysisBase, table=True):
    """AI分析结果数据库表"""
    __tablename__ = "ai_analyses"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    session_id: uuid.UUID = Field(foreign_key="skiing_sessions.id", index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # 核心分析指标字段（从analysis_data dict拆分）
    avg_edge_angle: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="平均立刃角度")
    turn_count: Optional[int] = Field(default=None, ge=0, description="转弯次数")
    technique_score: Optional[Decimal] = Field(default=None, max_digits=3, decimal_places=1, description="技术评分")
    balance_score: Optional[Decimal] = Field(default=None, max_digits=3, decimal_places=1, description="平衡评分")
    speed_consistency: Optional[Decimal] = Field(default=None, max_digits=3, decimal_places=1, description="速度一致性")
    edge_control_score: Optional[Decimal] = Field(default=None, max_digits=3, decimal_places=1, description="立刃控制评分")
    turn_quality_score: Optional[Decimal] = Field(default=None, max_digits=3, decimal_places=1, description="转弯质量评分")
    
    # 详细分析数据（JSON格式，符合文档要求）
    analysis_data: Optional[dict[str, Any]] = Field(
        default=None, 
        sa_column=Column(PostgresJSON), 
        description="详细分析数据JSON"
    )

    # 关系
    user: User = Relationship(back_populates="ai_analyses")
    session: SkiingSession = Relationship(back_populates="ai_analyses")


class AIAnalysisPublic(AIAnalysisBase):
    """AI分析公开信息"""
    id: uuid.UUID
    session_id: uuid.UUID
    user_id: uuid.UUID
    analysis_data: Optional[dict[str, Any]] = None
    created_at: datetime


class AIAnalysesPublic(SQLModel):
    """AI分析列表响应"""
    data: list[AIAnalysisPublic]
    count: int


# =============================================================================
# 临时保留的Item模型（向后兼容，未来将替换为滑雪设备或会话相关模型）
# =============================================================================

class ItemBase(SQLModel):
    """临时Item基础模型"""
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


class ItemCreate(ItemBase):
    """创建Item"""
    pass


class ItemUpdate(ItemBase):
    """更新Item"""
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore


class Item(ItemBase, table=True):
    """临时Item数据库模型"""
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="users.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


class ItemPublic(ItemBase):
    """Item公开信息"""
    id: uuid.UUID
    owner_id: uuid.UUID


class ItemsPublic(SQLModel):
    """Item列表响应"""
    data: list[ItemPublic]
    count: int


# =============================================================================
# 通用模型 (Generic Models)
# =============================================================================

class Message(SQLModel):
    """通用消息模型"""
    message: str


class Token(SQLModel):
    """认证令牌模型"""
    access_token: str
    token_type: str = "bearer"


class TokenPayload(SQLModel):
    """JWT令牌负载"""
    sub: str | None = None
