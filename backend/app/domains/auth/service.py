"""
Authentication domain service
Business logic layer for authentication operations
"""
import secrets
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from redis import Redis
from sqlmodel import Session

from app.core.config import settings
from app.core.exceptions import (
    AuthenticationError,
    RateLimitError,
    VerificationCodeError,
)
from app.core.security import create_access_token

from .models import User, UserSession
from .repository import (
    SessionRepository,
    UserAuthRepository,
    UserRepository,
    VerificationCodeRepository,
)
from .schemas import LoginResponse, SendCodeResponse, UserPublic


class AuthService:
    """
    Authentication service implementing business logic
    Coordinates between repositories to handle auth operations
    """

    def __init__(
        self,
        db_session: Session,
        redis_client: Optional[Redis] = None
    ):
        """
        Initialize auth service with dependencies

        Args:
            db_session: Database session
            redis_client: Redis client (optional)
        """
        self.db_session = db_session
        self.redis_client = redis_client

        # Initialize repositories
        self.vcode_repo = VerificationCodeRepository(redis_client)
        self.user_repo = UserRepository(db_session)
        self.auth_repo = UserAuthRepository(db_session)
        self.session_repo = SessionRepository(db_session, redis_client)

        # Configuration
        self.code_length = 6
        self.code_ttl = 300  # 5 minutes
        self.max_attempts = 3

    def _generate_verification_code(self) -> str:
        """
        Generate a random 6-digit verification code

        Returns:
            6-digit string
        """
        return ''.join([str(secrets.randbelow(10)) for _ in range(self.code_length)])

    async def send_verification_code(
        self,
        phone: str,
        ip_address: str
    ) -> SendCodeResponse:
        """
        Send verification code to phone number
        Checks rate limits before sending

        Args:
            phone: Phone number (validated)
            ip_address: Client IP address

        Returns:
            SendCodeResponse with success status

        Raises:
            RateLimitError: If rate limit exceeded
            VerificationCodeError: If code generation/storage fails
        """
        # Rate limiting: Basic time-based check (60s minimum between sends)
        # For advanced rate limiting (IP-based, phone-based), see app/core/rate_limiter.py
        existing_code = self.vcode_repo.get_code(phone)
        if existing_code:
            # Check if it's too soon to resend
            created_at = datetime.fromisoformat(existing_code["created_at"])
            elapsed = (datetime.utcnow() - created_at).total_seconds()
            if elapsed < 60:  # Must wait 60 seconds between sends
                raise RateLimitError(
                    user_message=f"请等待 {int(60 - elapsed)} 秒后再重新发送",
                    internal_message=f"Rate limit: {elapsed}s elapsed, need 60s",
                    retry_after=int(60 - elapsed)
                )

        # Generate code
        code = self._generate_verification_code()

        # Store code
        success = self.vcode_repo.store_code(
            phone=phone,
            code=code,
            ttl=self.code_ttl,
            attempts=0
        )

        if not success:
            raise VerificationCodeError(
                user_message="验证码发送失败，请稍后重试",
                internal_message="Failed to store verification code"
            )

        # SMS integration: Using mock for development
        # Production: Integrate SMS service (Twilio, Aliyun, or custom provider)
        print(f"[DEV MODE] Verification code for {phone}: {code}")

        return SendCodeResponse(
            success=True,
            message="验证码已发送",
            expires_in=self.code_ttl
        )

    async def verify_and_login(
        self,
        phone: str,
        code: str,
        ip_address: str,
        device_type: Optional[str] = None,
        device_model: Optional[str] = None,
        os_type: Optional[str] = None,
        os_version: Optional[str] = None,
        app_version: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> LoginResponse:
        """
        Verify code and perform login
        Creates user if doesn't exist, creates session, generates JWT

        Args:
            phone: Phone number
            code: Verification code to verify
            ip_address: Client IP address
            device_type: Device type
            device_model: Device model
            os_type: OS type
            os_version: OS version
            app_version: App version
            user_agent: User agent string

        Returns:
            LoginResponse with token and user info

        Raises:
            AuthenticationError: If verification fails
        """
        # 1. Retrieve code data
        code_data = self.vcode_repo.get_code(phone)

        if not code_data:
            raise AuthenticationError(
                user_message="验证码不存在或已过期",
                internal_message=f"No verification code found for {phone}"
            )

        # 2. Check attempts
        attempts = int(code_data.get("attempts", 0))
        if attempts >= self.max_attempts:
            # Delete code after max attempts
            self.vcode_repo.delete_code(phone)
            raise AuthenticationError(
                user_message="验证码尝试次数过多，请重新获取",
                internal_message=f"Max attempts ({self.max_attempts}) exceeded"
            )

        # 3. Verify code
        if code_data.get("code") != code:
            # Increment attempts
            self.vcode_repo.increment_attempts(phone)
            remaining = self.max_attempts - attempts - 1
            raise AuthenticationError(
                user_message=f"验证码错误，还剩 {remaining} 次机会",
                internal_message=f"Invalid code, attempts: {attempts + 1}"
            )

        # 4. Code is valid - delete it
        self.vcode_repo.delete_code(phone)

        # 5. Get or create user
        user = await self.user_repo.get_by_phone(phone)
        if not user:
            user = await self.user_repo.create(phone=phone)

        # 6. Update last login (pass user object to avoid redundant query)
        await self.user_repo.update_last_login(user)

        # 7. Create auth record
        await self.auth_repo.create_auth_record(
            user_id=user.id,
            phone=phone,
            verification_code=code
        )

        # 8. Create session
        session_token = secrets.token_urlsafe(32)
        session = await self.session_repo.create_session(
            user_id=user.id,
            session_token=session_token,
            ip_address=ip_address,
            expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            device_type=device_type,
            device_model=device_model,
            os_type=os_type,
            os_version=os_version,
            app_version=app_version,
            user_agent=user_agent
        )

        # 9. Generate JWT with session ID
        access_token = create_access_token(
            subject=str(user.id),
            session_id=str(session.id)
        )

        # 10. Prepare user public data
        user_public = UserPublic(
            id=user.id,
            phone=user.phone,
            nickname=user.nickname,
            avatar_url=user.avatar_url,
            preferred_foot=user.preferred_foot,
            level=user.level,
            level_description=user.level_description,
            total_skiing_days=user.total_skiing_days,
            total_skiing_hours=user.total_skiing_hours,
            total_skiing_sessions=user.total_skiing_sessions,
            average_speed=user.average_speed,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login_at=user.last_login_at
        )

        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_public
        )

    async def logout(self, session_token: str) -> bool:
        """
        Logout user by invalidating session

        Args:
            session_token: Session token to invalidate

        Returns:
            True if logout successful
        """
        return await self.session_repo.invalidate_session(session_token)

    async def logout_all_sessions(self, user_id: uuid.UUID) -> int:
        """
        Logout user from all sessions

        Args:
            user_id: User ID

        Returns:
            Number of sessions invalidated
        """
        return await self.session_repo.invalidate_all_sessions(user_id)

    async def get_active_sessions(self, user_id: uuid.UUID) -> List[UserSession]:
        """
        Get all active sessions for a user

        Args:
            user_id: User ID

        Returns:
            List of active UserSession objects
        """
        return await self.session_repo.get_active_sessions(user_id)

    async def validate_session(self, session_token: str) -> Optional[User]:
        """
        Validate session token and return associated user

        Args:
            session_token: Session token to validate

        Returns:
            User object if session valid, None otherwise
        """
        session = await self.session_repo.get_session_by_token(session_token)

        if not session:
            return None

        # Check if expired
        if session.expires_at < datetime.utcnow():
            await self.session_repo.invalidate_session(session_token)
            return None

        # Update activity
        await self.session_repo.update_activity(session_token)

        # Return user
        return await self.user_repo.get_by_id(session.user_id)

    async def get_verification_code_info(self, phone: str) -> Optional[Dict[str, Any]]:
        """
        Get verification code info for debugging (development only)

        Args:
            phone: Phone number

        Returns:
            Dict with code info or None
        """
        if settings.ENVIRONMENT != "local":
            return None

        return self.vcode_repo.get_code(phone)
