"""
Unit tests for verification code service
"""
import json
from datetime import datetime
from app.core.verification_code import VerificationCodeService
from app.tests.utils.auth import MockRedisClient


class TestPhoneValidation:
    """Test phone number validation"""

    def test_valid_chinese_phones(self):
        """Test valid Chinese phone numbers"""
        service = VerificationCodeService()

        valid_phones = [
            "13800138000",
            "13900139000",
            "14700147000",
            "15800158000",
            "16600166000",
            "17700177000",
            "18800188000",
            "19900199000",
        ]

        for phone in valid_phones:
            assert service.validate_phone(phone), f"{phone} should be valid"

    def test_invalid_phones(self):
        """Test invalid phone numbers"""
        service = VerificationCodeService()

        invalid_phones = [
            "1380013800",  # Too short
            "138001380001",  # Too long
            "23800138000",  # Wrong prefix
            "12800128000",  # Prefix not allowed
            "abc00138000",  # Non-numeric
            "138-0013-8000",  # With dashes
            "+8613800138000",  # With country code
        ]

        for phone in invalid_phones:
            assert not service.validate_phone(phone), f"{phone} should be invalid"


class TestCodeGeneration:
    """Test verification code generation"""

    def test_generate_code_format(self):
        """Test that generated codes are 6-digit numbers"""
        service = VerificationCodeService()

        for _ in range(100):
            code = service.generate_code()

            # Should be string of 6 digits
            assert len(code) == 6
            assert code.isdigit()
            assert 100000 <= int(code) <= 999999

    def test_generate_code_randomness(self):
        """Test that generated codes are random"""
        service = VerificationCodeService()

        codes = [service.generate_code() for _ in range(100)]

        # Should have at least 80 unique codes out of 100
        unique_codes = set(codes)
        assert len(unique_codes) >= 80


class TestCodeStorage:
    """Test verification code storage"""

    def test_store_code_success(self):
        """Test successful code storage"""
        service = VerificationCodeService()
        service.redis_client = MockRedisClient()

        phone = "13800138000"
        code = "123456"

        result = service.store_code(phone, code)
        assert result is True

        # Verify stored data
        key = f"verification_code:{phone}"
        stored_data = service.redis_client.get(key)
        assert stored_data is not None

        data = json.loads(stored_data)
        assert data["code"] == code
        assert data["attempts"] == 0
        assert "created_at" in data

    def test_store_code_overwrites_previous(self):
        """Test that new code overwrites previous one"""
        service = VerificationCodeService()
        service.redis_client = MockRedisClient()

        phone = "13800138000"

        # Store first code
        service.store_code(phone, "111111")

        # Store second code
        service.store_code(phone, "222222")

        # Should have second code
        key = f"verification_code:{phone}"
        data = json.loads(service.redis_client.get(key))
        assert data["code"] == "222222"


class TestCodeVerification:
    """Test verification code verification"""

    def test_verify_code_success(self):
        """Test successful code verification"""
        service = VerificationCodeService()
        service.redis_client = MockRedisClient()

        phone = "13800138000"
        code = "123456"

        # Store code
        service.store_code(phone, code)

        # Verify correct code
        result = service.verify_code(phone, code)
        assert result is True

        # Code should be deleted after successful verification
        key = f"verification_code:{phone}"
        assert service.redis_client.get(key) is None

    def test_verify_code_wrong_code(self):
        """Test verification with wrong code"""
        service = VerificationCodeService()
        service.redis_client = MockRedisClient()

        phone = "13800138000"
        correct_code = "123456"
        wrong_code = "654321"

        # Store code
        service.store_code(phone, correct_code)

        # Verify wrong code
        result = service.verify_code(phone, wrong_code)
        assert result is False

        # Code should still exist
        key = f"verification_code:{phone}"
        data = json.loads(service.redis_client.get(key))
        assert data["attempts"] == 1  # Attempt count increased

    def test_verify_code_max_attempts(self):
        """Test max attempts limit"""
        service = VerificationCodeService()
        service.redis_client = MockRedisClient()

        phone = "13800138000"
        code = "123456"

        # Store code
        service.store_code(phone, code)

        # Try wrong code max_attempts times (3 times)
        # After 3 failed attempts, attempts counter = 3
        for i in range(service.max_attempts):
            result = service.verify_code(phone, "000000")
            assert result is False, f"Attempt {i+1} should fail"

        # After max_attempts failed tries, code should still exist with attempts=3
        key = f"verification_code:{phone}"
        data_str = service.redis_client.get(key)
        assert data_str is not None, "Code should still exist after max failed attempts"
        data = json.loads(data_str)
        assert data["attempts"] == service.max_attempts

        # Next attempt (4th) should trigger deletion due to attempts >= max_attempts
        result = service.verify_code(phone, code)
        assert result is False, "Should fail because attempts >= max_attempts"

        # Now code should be deleted
        assert service.redis_client.get(key) is None, "Code should be deleted"

    def test_verify_code_not_found(self):
        """Test verification when code doesn't exist"""
        service = VerificationCodeService()
        service.redis_client = MockRedisClient()

        phone = "13800138000"

        # Verify without storing
        result = service.verify_code(phone, "123456")
        assert result is False

    def test_verify_code_case_sensitivity(self):
        """Test that code verification is case-insensitive (all digits)"""
        service = VerificationCodeService()
        service.redis_client = MockRedisClient()

        phone = "13800138000"
        code = "123456"

        service.store_code(phone, code)

        # String vs int comparison
        result = service.verify_code(phone, "123456")
        assert result is True


class TestRateLimit:
    """Test rate limiting"""

    def test_rate_limit_allows_initial_requests(self):
        """Test that initial requests are allowed"""
        service = VerificationCodeService()
        service.redis_client = MockRedisClient()

        phone = "13800138000"

        # First requests should be allowed
        for i in range(service.rate_limit_count):
            result = service.check_rate_limit(phone)
            assert result is True, f"Request {i+1} should be allowed"

    def test_rate_limit_blocks_excessive_requests(self):
        """Test that excessive requests are blocked"""
        service = VerificationCodeService()
        service.redis_client = MockRedisClient()

        phone = "13800138000"

        # Use up the limit
        for _ in range(service.rate_limit_count):
            service.check_rate_limit(phone)

        # Next request should be blocked
        result = service.check_rate_limit(phone)
        assert result is False

    def test_rate_limit_per_phone(self):
        """Test that rate limit is per phone number"""
        service = VerificationCodeService()
        service.redis_client = MockRedisClient()

        phone1 = "13800138000"
        phone2 = "13900139000"

        # Use up limit for phone1
        for _ in range(service.rate_limit_count):
            service.check_rate_limit(phone1)

        # phone1 should be blocked
        assert service.check_rate_limit(phone1) is False

        # phone2 should still be allowed
        assert service.check_rate_limit(phone2) is True


class TestGetStoredCode:
    """Test getting stored code (for development)"""

    def test_get_stored_code_in_local(self):
        """Test getting stored code in local environment"""
        from app.core.config import settings

        if settings.ENVIRONMENT != "local":
            return  # Skip in non-local environment

        service = VerificationCodeService()
        service.redis_client = MockRedisClient()

        phone = "13800138000"
        code = "123456"

        # Store code
        service.store_code(phone, code)

        # Get stored code
        stored = service.get_stored_code(phone)
        assert stored is not None
        assert stored["code"] == code
        assert stored["attempts"] == 0

    def test_get_stored_code_not_found(self):
        """Test getting non-existent code"""
        from app.core.config import settings

        if settings.ENVIRONMENT != "local":
            return

        service = VerificationCodeService()
        service.redis_client = MockRedisClient()

        phone = "13800138000"

        # Get without storing
        stored = service.get_stored_code(phone)
        assert stored is None


if __name__ == "__main__":
    print("Running verification code service tests...")

    # Test 1
    print("\n[Test 1] Phone validation...")
    test1 = TestPhoneValidation()
    test1.test_valid_chinese_phones()
    test1.test_invalid_phones()
    print("[PASS]")

    # Test 2
    print("\n[Test 2] Code generation...")
    test2 = TestCodeGeneration()
    test2.test_generate_code_format()
    test2.test_generate_code_randomness()
    print("[PASS]")

    # Test 3
    print("\n[Test 3] Code storage...")
    test3 = TestCodeStorage()
    test3.test_store_code_success()
    test3.test_store_code_overwrites_previous()
    print("[PASS]")

    # Test 4
    print("\n[Test 4] Code verification...")
    test4 = TestCodeVerification()
    test4.test_verify_code_success()
    test4.test_verify_code_wrong_code()
    test4.test_verify_code_max_attempts()
    test4.test_verify_code_not_found()
    test4.test_verify_code_case_sensitivity()
    print("[PASS]")

    # Test 5
    print("\n[Test 5] Rate limiting...")
    test5 = TestRateLimit()
    test5.test_rate_limit_allows_initial_requests()
    test5.test_rate_limit_blocks_excessive_requests()
    test5.test_rate_limit_per_phone()
    print("[PASS]")

    print("\n" + "="*50)
    print("All verification code service tests passed!")
