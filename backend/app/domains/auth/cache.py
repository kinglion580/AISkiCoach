"""
Session caching layer for performance optimization
Reduces database queries by caching active sessions in Redis
"""
import json
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from redis import Redis


class SessionCache:
    """
    Redis-based session cache for performance optimization

    Caches active UserSession data to reduce database queries
    during authentication middleware execution
    """

    def __init__(self, redis_client: Optional[Redis] = None):
        """Initialize session cache with Redis client.

        Args:
            redis_client: Redis client instance (optional)
        """
        self.redis_client = redis_client
        self.use_redis = redis_client is not None

        # Configuration
        self.key_prefix = "session:"
        self.default_ttl = 3600  # 1 hour default TTL

    def _make_key(self, session_id: uuid.UUID) -> str:
        """Generate Redis key for session.

        Args:
            session_id: Session UUID

        Returns:
            Redis key string
        """
        return f"{self.key_prefix}{str(session_id)}"

    def get_session(self, session_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Retrieve session data from cache.

        Args:
            session_id: Session UUID

        Returns:
            Session data dict or None if not found/expired
        """
        if not self.use_redis or not self.redis_client:
            return None

        try:
            key = self._make_key(session_id)
            data = self.redis_client.get(key)

            if not data:
                return None

            # Parse JSON data
            session_data = json.loads(data.decode('utf-8'))
            return session_data

        except Exception as e:
            print(f"Session cache retrieval failed: {e}")
            return None

    def set_session(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        is_active: bool,
        expires_at: datetime,
        ttl: Optional[int] = None
    ) -> bool:
        """Store session data in cache.

        Args:
            session_id: Session UUID
            user_id: User UUID
            is_active: Whether session is active
            expires_at: Session expiration timestamp
            ttl: Time to live in seconds (optional)

        Returns:
            True if storage successful
        """
        if not self.use_redis or not self.redis_client:
            return False

        try:
            key = self._make_key(session_id)

            # Prepare session data
            session_data = {
                "session_id": str(session_id),
                "user_id": str(user_id),
                "is_active": is_active,
                "expires_at": expires_at.isoformat()
            }

            # Calculate TTL (use remaining time until expiration)
            if ttl is None:
                remaining = (expires_at - datetime.utcnow()).total_seconds()
                ttl = max(int(remaining), 60)  # At least 60 seconds

            # Store in Redis with TTL
            self.redis_client.setex(
                key,
                ttl,
                json.dumps(session_data)
            )
            return True

        except Exception as e:
            print(f"Session cache storage failed: {e}")
            return False

    def delete_session(self, session_id: uuid.UUID) -> bool:
        """Delete session from cache.

        Args:
            session_id: Session UUID

        Returns:
            True if deletion successful
        """
        if not self.use_redis or not self.redis_client:
            return False

        try:
            key = self._make_key(session_id)
            self.redis_client.delete(key)
            return True

        except Exception:
            return False

    def invalidate_user_sessions(self, user_id: uuid.UUID) -> int:
        """Invalidate all sessions for a user.

        Args:
            user_id: User UUID

        Returns:
            Number of sessions invalidated
        """
        if not self.use_redis or not self.redis_client:
            return 0

        try:
            # Scan for all session keys and check user_id
            pattern = f"{self.key_prefix}*"
            count = 0

            for key in self.redis_client.scan_iter(match=pattern, count=100):
                try:
                    data = self.redis_client.get(key)
                    if data:
                        session_data = json.loads(data.decode('utf-8'))
                        if session_data.get("user_id") == str(user_id):
                            self.redis_client.delete(key)
                            count += 1
                except Exception:
                    continue

            return count

        except Exception as e:
            print(f"Session cache invalidation failed: {e}")
            return 0
