"""
Rate Limiter with sliding window algorithm
Supports multiple dimensions (phone, IP) and fallback to local memory when Redis fails
"""
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from collections import defaultdict, deque
import redis
from fastapi import HTTPException, status

from app.core.config import settings


class InMemoryRateLimiter:
    """In-memory rate limiter fallback when Redis is unavailable"""

    def __init__(self):
        # key -> deque of timestamps
        self.data: Dict[str, deque] = defaultdict(deque)
        self.locks: Dict[str, float] = {}  # key -> lock_until_timestamp

    def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> tuple[bool, int, int]:
        """
        Check if rate limit is exceeded using sliding window

        Returns:
            (is_allowed, current_count, remaining)
        """
        now = time.time()
        cutoff_time = now - window_seconds

        # Check if locked
        if key in self.locks and self.locks[key] > now:
            return False, limit + 1, 0

        # Get timestamps for this key
        if key not in self.data:
            self.data[key] = deque()

        timestamps = self.data[key]

        # Remove old timestamps (outside sliding window)
        while timestamps and timestamps[0] < cutoff_time:
            timestamps.popleft()

        current_count = len(timestamps)

        if current_count >= limit:
            # Rate limit exceeded
            return False, current_count, 0

        # Add current timestamp
        timestamps.append(now)
        remaining = limit - (current_count + 1)

        return True, current_count + 1, remaining

    def reset(self, key: str):
        """Reset rate limit for a key"""
        if key in self.data:
            del self.data[key]
        if key in self.locks:
            del self.locks[key]

    def cleanup(self, max_age_seconds: int = 3600):
        """Clean up old entries"""
        now = time.time()
        cutoff = now - max_age_seconds

        # Clean up data
        keys_to_delete = []
        for key, timestamps in self.data.items():
            while timestamps and timestamps[0] < cutoff:
                timestamps.popleft()
            if not timestamps:
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self.data[key]

        # Clean up expired locks
        self.locks = {k: v for k, v in self.locks.items() if v > now}


class RateLimiter:
    """
    Rate limiter with Redis backend and in-memory fallback
    Implements sliding window algorithm for accurate rate limiting
    """

    def __init__(self):
        self.redis_client = self._init_redis()
        self.memory_limiter = InMemoryRateLimiter()
        self.use_redis = self.redis_client is not None

    def _init_redis(self) -> Optional[redis.Redis]:
        """Initialize Redis connection with fallback"""
        try:
            redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2
            )
            # Test connection
            redis_client.ping()
            print("[RateLimiter] Connected to Redis successfully")
            return redis_client
        except Exception as e:
            print(f"[RateLimiter] Redis connection failed, using in-memory fallback: {e}")
            return None

    def _check_redis_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> tuple[bool, int, int]:
        """
        Check rate limit using Redis with sliding window

        Returns:
            (is_allowed, current_count, remaining)
        """
        try:
            now = time.time()
            window_start = now - window_seconds

            # Use sorted set for sliding window
            pipe = self.redis_client.pipeline()

            # Remove old entries
            pipe.zremrangebyscore(key, 0, window_start)

            # Count current entries
            pipe.zcard(key)

            # Add current request
            pipe.zadd(key, {f"{now}:{id(key)}": now})

            # Set expiration
            pipe.expire(key, window_seconds + 10)

            results = pipe.execute()
            current_count = results[1]  # Count before adding

            if current_count >= limit:
                # Remove the request we just added
                self.redis_client.zremrangebyscore(key, now, now)
                return False, current_count, 0

            remaining = limit - (current_count + 1)
            return True, current_count + 1, remaining

        except redis.RedisError as e:
            print(f"[RateLimiter] Redis error, falling back to memory: {e}")
            # Fall back to in-memory limiter
            self.use_redis = False
            return self.memory_limiter.check_rate_limit(key, limit, window_seconds)

    def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> tuple[bool, int, int]:
        """
        Check rate limit for a key

        Args:
            key: Rate limit key (e.g., "phone:13800138000")
            limit: Maximum number of requests
            window_seconds: Time window in seconds

        Returns:
            (is_allowed, current_count, remaining)
        """
        if self.use_redis and self.redis_client:
            return self._check_redis_rate_limit(key, limit, window_seconds)
        else:
            return self.memory_limiter.check_rate_limit(key, limit, window_seconds)

    def check_multiple(
        self,
        keys: List[str],
        limit: int,
        window_seconds: int
    ) -> tuple[bool, Dict[str, tuple[int, int]]]:
        """
        Check rate limit for multiple keys (e.g., phone + IP)
        All keys must pass the rate limit check

        Args:
            keys: List of keys to check
            limit: Maximum number of requests per key
            window_seconds: Time window in seconds

        Returns:
            (all_allowed, {key: (current_count, remaining)})
        """
        results = {}
        all_allowed = True

        for key in keys:
            is_allowed, current, remaining = self.check_rate_limit(key, limit, window_seconds)
            results[key] = (current, remaining)
            if not is_allowed:
                all_allowed = False

        return all_allowed, results

    def reset(self, key: str):
        """Reset rate limit for a key"""
        if self.use_redis and self.redis_client:
            try:
                self.redis_client.delete(key)
            except redis.RedisError:
                pass
        self.memory_limiter.reset(key)


# Global rate limiter instance
rate_limiter = RateLimiter()


# Rate limit decorator
def rate_limit(
    key_prefix: str,
    limit: int = 5,
    window_seconds: int = 60,
    key_extractor: Optional[callable] = None
):
    """
    Rate limit decorator for FastAPI routes

    Args:
        key_prefix: Prefix for rate limit key
        limit: Maximum requests
        window_seconds: Time window
        key_extractor: Function to extract key from request (phone, IP, etc.)
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract key from request
            if key_extractor:
                key = f"{key_prefix}:{key_extractor(*args, **kwargs)}"
            else:
                # Default: use all args as key
                key = f"{key_prefix}:{':'.join(str(a) for a in args)}"

            is_allowed, current, remaining = rate_limiter.check_rate_limit(
                key, limit, window_seconds
            )

            if not is_allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Try again in {window_seconds} seconds.",
                    headers={"Retry-After": str(window_seconds)}
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator
