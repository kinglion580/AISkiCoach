"""
Authentication domain
Handles user authentication, verification codes, and sessions
"""
from .cache import SessionCache
from .models import User, UserAuth, UserSession
from .repository import (
    SessionRepository,
    UserAuthRepository,
    UserRepository,
    VerificationCodeRepository,
)
from .schemas import (
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    SendCodeRequest,
    SendCodeResponse,
    SessionsPublic,
    Token,
    TokenPayload,
    UserCreate,
    UserPublic,
    UserSessionPublic,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
    VerificationCodeInfo,
    VerificationCodeLoginRequest,
)
from .service import AuthService

__all__ = [
    # Models
    "User",
    "UserAuth",
    "UserSession",
    # Schemas
    "UserCreate",
    "UserUpdate",
    "UserUpdateMe",
    "UserPublic",
    "UsersPublic",
    "SendCodeRequest",
    "SendCodeResponse",
    "VerificationCodeLoginRequest",
    "LoginResponse",
    "Token",
    "TokenPayload",
    "UserSessionPublic",
    "SessionsPublic",
    "LogoutRequest",
    "LogoutResponse",
    "VerificationCodeInfo",
    # Service
    "AuthService",
    # Repositories
    "VerificationCodeRepository",
    "UserRepository",
    "UserAuthRepository",
    "SessionRepository",
    # Cache
    "SessionCache",
]
