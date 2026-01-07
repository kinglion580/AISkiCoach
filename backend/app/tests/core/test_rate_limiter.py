"""
Tests for rate limiter with sliding window algorithm
"""
import time
from app.core.rate_limiter import RateLimiter, InMemoryRateLimiter


class TestInMemoryRateLimiter:
    """Test in-memory rate limiter"""

    def test_basic_rate_limit(self):
        """Test basic rate limiting"""
        limiter = InMemoryRateLimiter()
        key = "test:phone:13800138000"

        # First 5 requests should pass (limit=5)
        for i in range(5):
            is_allowed, current, remaining = limiter.check_rate_limit(key, limit=5, window_seconds=60)
            assert is_allowed, f"Request {i+1} should be allowed"
            assert current == i + 1
            assert remaining == 5 - (i + 1)

        # 6th request should be blocked
        is_allowed, current, remaining = limiter.check_rate_limit(key, limit=5, window_seconds=60)
        assert not is_allowed, "6th request should be blocked"
        assert current == 5
        assert remaining == 0

    def test_sliding_window(self):
        """Test sliding window behavior"""
        limiter = InMemoryRateLimiter()
        key = "test:sliding"

        # Make 3 requests
        for _ in range(3):
            is_allowed, _, _ = limiter.check_rate_limit(key, limit=3, window_seconds=2)
            assert is_allowed

        # 4th should be blocked
        is_allowed, _, _ = limiter.check_rate_limit(key, limit=3, window_seconds=2)
        assert not is_allowed

        # Wait for window to expire
        time.sleep(2.1)

        # Should be allowed again
        is_allowed, current, remaining = limiter.check_rate_limit(key, limit=3, window_seconds=2)
        assert is_allowed
        assert current == 1  # Old entries should be removed
        assert remaining == 2

    def test_multiple_keys(self):
        """Test multiple independent keys"""
        limiter = InMemoryRateLimiter()

        # Different keys should have independent limits
        key1 = "test:phone:13800138000"
        key2 = "test:phone:13900139000"

        # Fill up key1
        for _ in range(3):
            is_allowed, _, _ = limiter.check_rate_limit(key1, limit=3, window_seconds=60)
            assert is_allowed

        # key1 should be blocked
        is_allowed, _, _ = limiter.check_rate_limit(key1, limit=3, window_seconds=60)
        assert not is_allowed

        # key2 should still be allowed
        is_allowed, _, _ = limiter.check_rate_limit(key2, limit=3, window_seconds=60)
        assert is_allowed

    def test_reset(self):
        """Test reset functionality"""
        limiter = InMemoryRateLimiter()
        key = "test:reset"

        # Fill up the limit
        for _ in range(5):
            limiter.check_rate_limit(key, limit=5, window_seconds=60)

        # Should be blocked
        is_allowed, _, _ = limiter.check_rate_limit(key, limit=5, window_seconds=60)
        assert not is_allowed

        # Reset
        limiter.reset(key)

        # Should be allowed again
        is_allowed, current, remaining = limiter.check_rate_limit(key, limit=5, window_seconds=60)
        assert is_allowed
        assert current == 1
        assert remaining == 4


class TestRateLimiter:
    """Test Redis-backed rate limiter with fallback"""

    def test_redis_or_memory_rate_limit(self):
        """Test rate limiting (works with either Redis or memory)"""
        limiter = RateLimiter()
        key = f"test:integration:{time.time()}"

        # First 3 requests should pass
        for i in range(3):
            is_allowed, current, remaining = limiter.check_rate_limit(key, limit=3, window_seconds=60)
            assert is_allowed, f"Request {i+1} should be allowed"
            assert current == i + 1

        # 4th request should be blocked
        is_allowed, current, remaining = limiter.check_rate_limit(key, limit=3, window_seconds=60)
        assert not is_allowed
        assert current == 3

    def test_multiple_dimension_limits(self):
        """Test checking multiple dimensions (phone + IP)"""
        limiter = RateLimiter()
        timestamp = time.time()

        keys = [
            f"test:phone:13800138000:{timestamp}",
            f"test:ip:192.168.1.1:{timestamp}"
        ]

        # Check both dimensions
        all_allowed, results = limiter.check_multiple(keys, limit=5, window_seconds=60)
        assert all_allowed
        assert len(results) == 2

        for key in keys:
            current, remaining = results[key]
            assert current == 1
            assert remaining == 4

    def test_memory_fallback(self):
        """Test that memory fallback works"""
        limiter = RateLimiter()

        # Force memory mode
        limiter.use_redis = False

        key = f"test:memory:{time.time()}"

        # Should work with memory limiter
        is_allowed, current, remaining = limiter.check_rate_limit(key, limit=5, window_seconds=60)
        assert is_allowed
        assert current == 1
        assert remaining == 4


def test_rate_limiter_initialization():
    """Test rate limiter initialization"""
    limiter = RateLimiter()
    assert limiter is not None
    assert limiter.memory_limiter is not None
    # Redis may or may not be available
    print(f"Rate limiter using Redis: {limiter.use_redis}")


if __name__ == "__main__":
    # Run tests manually
    print("Running rate limiter tests...")

    # Test 1
    print("\n[Test 1] Basic rate limit...")
    test = TestInMemoryRateLimiter()
    test.test_basic_rate_limit()
    print("[PASS]")

    # Test 2
    print("\n[Test 2] Sliding window...")
    test.test_sliding_window()
    print("[PASS]")

    # Test 3
    print("\n[Test 3] Multiple keys...")
    test.test_multiple_keys()
    print("[PASS]")

    # Test 4
    print("\n[Test 4] Reset...")
    test.test_reset()
    print("[PASS]")

    # Test 5
    print("\n[Test 5] Rate limiter integration...")
    test2 = TestRateLimiter()
    test2.test_redis_or_memory_rate_limit()
    print("[PASS]")

    # Test 6
    print("\n[Test 6] Multiple dimensions...")
    test2.test_multiple_dimension_limits()
    print("[PASS]")

    # Test 7
    print("\n[Test 7] Memory fallback...")
    test2.test_memory_fallback()
    print("[PASS]")

    # Test 8
    print("\n[Test 8] Initialization...")
    test_rate_limiter_initialization()
    print("[PASS]")

    print("\n" + "="*50)
    print("All rate limiter tests passed!")
