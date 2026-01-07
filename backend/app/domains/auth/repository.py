"""
Authentication domain repositories
Data access layer for verification codes and user authentication
"""
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from redis import Redis
from sqlmodel import Session, desc, select, update

from .cache import SessionCache
from .models import User, UserAuth, UserSession


class VerificationCodeRepository:
    """
    Repository for verification code storage and retrieval
    Implements Redis primary storage with PostgreSQL fallback
    """

    def __init__(self, redis_client: Optional[Redis] = None):
        """
        Initialize repository with Redis client

        Args:
            redis_client: Redis client instance (optional, will try to connect if not provided)
        """
        self.redis_client = redis_client
        self.use_redis = redis_client is not None

        # Configuration
        self.key_prefix = "verification_code:"
        self.default_ttl = 300  # 5 minutes

    def _make_key(self, phone: str) -> str:
        """Generate Redis key for phone number"""
        return f"{self.key_prefix}{phone}"

    def store_code(
        self,
        phone: str,
        code: str,
        ttl: Optional[int] = None,
        attempts: int = 0
    ) -> bool:
        """
        Store verification code in Redis and PostgreSQL

        Args:
            phone: Phone number
            code: Verification code (6 digits)
            ttl: Time to live in seconds (default: 300)
            attempts: Number of failed attempts

        Returns:
            True if storage successful
        """
        if ttl is None:
            ttl = self.default_ttl

        expires_at = datetime.utcnow() + timedelta(seconds=ttl)

        # Data to store
        data = {
            "code": code,
            "phone": phone,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat(),
            "attempts": str(attempts)
        }

        # Try Redis first
        if self.use_redis and self.redis_client:
            try:
                key = self._make_key(phone)
                # Store as hash in Redis
                self.redis_client.hset(key, mapping=data)
                self.redis_client.expire(key, ttl)
                return True
            except Exception as e:
                # Fall through to PostgreSQL if Redis fails
                print(f"Redis storage failed: {e}, falling back to PostgreSQL")

        # Redis-only storage: No PostgreSQL fallback for verification codes
        # Verification codes are ephemeral (5 min TTL), Redis failure means retry needed
        return False

    def get_code(self, phone: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve verification code data

        Args:
            phone: Phone number

        Returns:
            Dictionary with code data or None if not found/expired
        """
        # Try Redis first
        if self.use_redis and self.redis_client:
            try:
                key = self._make_key(phone)
                data = self.redis_client.hgetall(key)

                if not data:
                    return None

                # Convert bytes to strings
                result = {
                    k.decode('utf-8'): v.decode('utf-8')
                    for k, v in data.items()
                }

                # Check if expired
                expires_at = datetime.fromisoformat(result["expires_at"])
                if datetime.utcnow() > expires_at:
                    # Delete expired code
                    self.redis_client.delete(key)
                    return None

                return result
            except Exception as e:
                print(f"Redis retrieval failed: {e}, falling back to PostgreSQL")

        # Redis-only retrieval: No PostgreSQL fallback
        return None

    def verify_code(self, phone: str, code: str) -> bool:
        """
        Verify if the provided code matches the stored code

        Args:
            phone: Phone number
            code: Code to verify

        Returns:
            True if code is valid and not expired
        """
        data = self.get_code(phone)

        if not data:
            return False

        return data.get("code") == code

    def increment_attempts(self, phone: str) -> int:
        """
        Increment failed verification attempts

        Args:
            phone: Phone number

        Returns:
            Current number of attempts
        """
        if self.use_redis and self.redis_client:
            try:
                key = self._make_key(phone)
                attempts = self.redis_client.hincrby(key, "attempts", 1)
                return attempts
            except Exception:
                pass

        return 0

    def delete_code(self, phone: str) -> bool:
        """
        Delete verification code

        Args:
            phone: Phone number

        Returns:
            True if deletion successful
        """
        if self.use_redis and self.redis_client:
            try:
                key = self._make_key(phone)
                self.redis_client.delete(key)
                return True
            except Exception:
                pass

        return False


class UserRepository:
    """Repository for User CRUD operations"""

    def __init__(self, session: Session):
        """Initialize user repository.

        Args:
            session: SQLModel database session
        """
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """Get user by ID"""
        return self.session.get(User, user_id)

    async def get_by_phone(self, phone: str) -> Optional[User]:
        """Get user by phone number"""
        statement = select(User).where(User.phone == phone)
        result = self.session.exec(statement)
        return result.first()

    async def create(
        self,
        phone: str,
        nickname: Optional[str] = None,
        preferred_foot: Optional[str] = None
    ) -> User:
        """
        Create a new user

        Args:
            phone: Phone number (required)
            nickname: User nickname (optional)
            preferred_foot: Preferred foot setting (optional)

        Returns:
            Created User instance
        """
        user = User(
            phone=phone,
            nickname=nickname,
            preferred_foot=preferred_foot,
            created_at=datetime.utcnow()
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    async def update_last_login(self, user: User) -> None:
        """Update user's last login timestamp.

        Args:
            user: User object to update (avoids redundant query)
        """
        user.last_login_at = datetime.utcnow()
        self.session.add(user)
        self.session.commit()


class UserAuthRepository:
    """Repository for UserAuth records"""

    def __init__(self, session: Session):
        """Initialize user authentication repository.

        Args:
            session: SQLModel database session
        """
        self.session = session

    async def create_auth_record(
        self,
        user_id: uuid.UUID,
        phone: str,
        verification_code: str
    ) -> UserAuth:
        """
        Create authentication record

        Args:
            user_id: User ID
            phone: Phone number
            verification_code: The verification code used

        Returns:
            Created UserAuth instance
        """
        auth_record = UserAuth(
            user_id=user_id,
            phone=phone,
            verification_code=verification_code,
            is_verified=True,
            created_at=datetime.utcnow()
        )
        self.session.add(auth_record)
        self.session.commit()
        self.session.refresh(auth_record)
        return auth_record

    async def get_recent_auth(self, user_id: uuid.UUID, limit: int = 10) -> List[UserAuth]:
        """
        Get recent authentication records for a user

        Args:
            user_id: User ID
            limit: Maximum number of records to return

        Returns:
            List of UserAuth records
        """
        statement = (
            select(UserAuth)
            .where(UserAuth.user_id == user_id)
            .order_by(desc(UserAuth.created_at))
            .limit(limit)
        )
        result = self.session.exec(statement)
        return list(result.all())


class SessionRepository:
    """Repository for UserSession management with Redis caching"""

    def __init__(self, session: Session, redis_client: Optional[Redis] = None):
        """Initialize session repository.

        Args:
            session: SQLModel database session
            redis_client: Redis client for session caching (optional)
        """
        self.session = session
        self.cache = SessionCache(redis_client)

    async def create_session(
        self,
        user_id: uuid.UUID,
        session_token: str,
        ip_address: Optional[str] = None,
        expires_in_seconds: int = 3600 * 24 * 7,  # 7 days default
        device_type: Optional[str] = None,
        device_model: Optional[str] = None,
        os_type: Optional[str] = None,
        os_version: Optional[str] = None,
        app_version: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_info: Optional[Dict[str, Any]] = None
    ) -> UserSession:
        """
        Create a new session

        Args:
            user_id: User ID
            session_token: JWT token or session identifier
            ip_address: Client IP address
            expires_in_seconds: Session expiration time
            device_type: Device type (iOS, Android, etc.)
            device_model: Device model
            os_type: OS type
            os_version: OS version
            app_version: App version
            user_agent: User agent string
            device_info: Additional device info as JSON

        Returns:
            Created UserSession instance
        """
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=expires_in_seconds)

        session = UserSession(
            user_id=user_id,
            session_token=session_token,
            ip_address=ip_address,
            expires_at=expires_at,
            created_at=now,
            last_activity_at=now,
            is_active=True,
            device_type=device_type,
            device_model=device_model,
            os_type=os_type,
            os_version=os_version,
            app_version=app_version,
            user_agent=user_agent,
            device_info=device_info
        )

        self.session.add(session)
        self.session.commit()
        self.session.refresh(session)

        # Cache the session for faster lookups
        self.cache.set_session(
            session_id=session.id,
            user_id=user_id,
            is_active=True,
            expires_at=expires_at,
            ttl=expires_in_seconds
        )

        return session

    async def get_session_by_token(self, session_token: str) -> Optional[UserSession]:
        """Get session by token"""
        statement = select(UserSession).where(
            UserSession.session_token == session_token,
            UserSession.is_active
        )
        result = self.session.exec(statement)
        return result.first()

    async def get_active_sessions(self, user_id: uuid.UUID) -> List[UserSession]:
        """Get all active sessions for a user"""
        statement = select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.is_active,
            UserSession.expires_at > datetime.utcnow()
        )
        result = self.session.exec(statement)
        return list(result.all())

    async def invalidate_session(self, session_token: str) -> bool:
        """Invalidate a session and remove from cache.

        Args:
            session_token: Session token to invalidate

        Returns:
            True if invalidation successful
        """
        session = await self.get_session_by_token(session_token)
        if session:
            session.is_active = False
            self.session.add(session)
            self.session.commit()

            # Remove from cache
            self.cache.delete_session(session.id)

            return True
        return False

    async def invalidate_all_sessions(self, user_id: uuid.UUID) -> int:
        """Invalidate all sessions for a user using bulk update.

        Args:
            user_id: User ID

        Returns:
            Number of sessions invalidated
        """
        # Use bulk update for better performance
        statement = (
            update(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.is_active
            )
            .values(is_active=False)
        )
        result = self.session.exec(statement)
        self.session.commit()

        # Invalidate all cached sessions for this user
        self.cache.invalidate_user_sessions(user_id)

        return result.rowcount

    async def update_activity(self, session_token: str) -> None:
        """Update last activity timestamp"""
        session = await self.get_session_by_token(session_token)
        if session:
            session.last_activity_at = datetime.utcnow()
            self.session.add(session)
            self.session.commit()
