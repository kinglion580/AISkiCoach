"""
Tests for exception handling and error codes
"""
from fastapi import status
from app.core.exceptions import (
    ErrorCode,
    AppException,
    AuthenticationError,
    ValidationError,
    VerificationCodeError,
    RateLimitError,
    DatabaseError,
    RedisError,
    SMSServiceError
)


class TestErrorCodes:
    """Test error code definitions"""

    def test_error_codes_are_unique(self):
        """Test that all error codes are unique"""
        codes = [code.value for code in ErrorCode]
        assert len(codes) == len(set(codes)), "Error codes must be unique"

    def test_error_codes_format(self):
        """Test that error codes follow naming convention"""
        for code in ErrorCode:
            # Should be in format: PREFIX_NNNN
            parts = code.value.split("_")
            assert len(parts) == 2, f"Error code {code.value} should have format PREFIX_NNNN"
            prefix, number = parts
            assert len(prefix) >= 2, f"Prefix too short: {prefix}"
            assert number.isdigit(), f"Number part should be digits: {number}"
            assert len(number) == 4, f"Number should be 4 digits: {number}"


class TestAppException:
    """Test base AppException class"""

    def test_app_exception_basic(self):
        """Test basic AppException creation"""
        exc = AppException(
            user_message="User friendly message",
            error_code=ErrorCode.INVALID_INPUT,
            status_code=status.HTTP_400_BAD_REQUEST
        )

        assert exc.user_message == "User friendly message"
        assert exc.error_code == ErrorCode.INVALID_INPUT
        assert exc.status_code == status.HTTP_400_BAD_REQUEST
        assert exc.internal_message == "User friendly message"  # Defaults to user_message

    def test_app_exception_with_internal_message(self):
        """Test AppException with separate internal message"""
        exc = AppException(
            user_message="Something went wrong",
            error_code=ErrorCode.DATABASE_ERROR,
            internal_message="PostgreSQL connection failed: timeout",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

        assert exc.user_message == "Something went wrong"
        assert exc.internal_message == "PostgreSQL connection failed: timeout"
        # Internal message should not be exposed to user
        assert "PostgreSQL" not in exc.user_message
        assert "timeout" not in exc.user_message

    def test_app_exception_to_dict(self):
        """Test conversion to dictionary for JSON response"""
        exc = AppException(
            user_message="Test error",
            error_code=ErrorCode.INVALID_INPUT,
            details={"field": "phone"}
        )

        result = exc.to_dict()

        assert "error" in result
        assert result["error"]["code"] == ErrorCode.INVALID_INPUT.value
        assert result["error"]["message"] == "Test error"
        assert result["error"]["details"]["field"] == "phone"


class TestSpecificExceptions:
    """Test specific exception classes"""

    def test_authentication_error(self):
        """Test AuthenticationError"""
        exc = AuthenticationError()

        assert exc.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc.error_code == ErrorCode.INVALID_CREDENTIALS
        assert "认证失败" in exc.user_message

    def test_validation_error(self):
        """Test ValidationError"""
        exc = ValidationError(
            user_message="手机号格式不正确",
            field="phone"
        )

        assert exc.status_code == status.HTTP_400_BAD_REQUEST
        assert exc.error_code == ErrorCode.INVALID_INPUT
        assert exc.details["field"] == "phone"

    def test_verification_code_error(self):
        """Test VerificationCodeError"""
        exc = VerificationCodeError(
            user_message="验证码已过期",
            error_code=ErrorCode.VERIFICATION_CODE_EXPIRED
        )

        assert exc.status_code == status.HTTP_400_BAD_REQUEST
        assert exc.error_code == ErrorCode.VERIFICATION_CODE_EXPIRED

    def test_rate_limit_error(self):
        """Test RateLimitError"""
        exc = RateLimitError(retry_after=60)

        assert exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert exc.error_code == ErrorCode.RATE_LIMIT_EXCEEDED
        assert exc.details["retry_after"] == 60

    def test_database_error(self):
        """Test DatabaseError"""
        exc = DatabaseError(
            internal_message="Connection pool exhausted"
        )

        assert exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert exc.error_code == ErrorCode.DATABASE_ERROR
        # Internal message should not be in user message
        assert "pool" not in exc.user_message.lower()

    def test_redis_error(self):
        """Test RedisError"""
        exc = RedisError(
            internal_message="Redis connection timeout: redis://localhost:6379"
        )

        assert exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert exc.error_code == ErrorCode.REDIS_CONNECTION_FAILED
        # Should not expose Redis URL to user
        assert "redis://" not in exc.user_message
        assert "localhost" not in exc.user_message
        # But internal message should have full details
        assert "redis://localhost:6379" in exc.internal_message

    def test_sms_service_error(self):
        """Test SMSServiceError"""
        exc = SMSServiceError(
            internal_message="Aliyun SMS API key invalid: AK_12345"
        )

        assert exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert exc.error_code == ErrorCode.SMS_SERVICE_FAILED
        # Should not expose API key to user
        assert "AK_" not in exc.user_message
        # But should be in internal message
        assert "AK_12345" in exc.internal_message


class TestErrorMessageSeparation:
    """Test that sensitive info is not exposed to users"""

    def test_redis_error_no_connection_string(self):
        """Test Redis errors don't expose connection strings"""
        exc = RedisError(
            internal_message="Failed to connect to redis://user:password@host:6379/0"
        )

        # User message should be generic
        assert "redis://" not in exc.user_message
        assert "password" not in exc.user_message
        assert "暂时不可用" in exc.user_message or "不可用" in exc.user_message

        # Internal message should have full details
        assert "redis://user:password@host:6379/0" in exc.internal_message

    def test_database_error_no_credentials(self):
        """Test database errors don't expose credentials"""
        exc = DatabaseError(
            internal_message="PostgreSQL auth failed for user 'admin' password 'secret123'"
        )

        # User message should be generic
        assert "admin" not in exc.user_message
        assert "secret123" not in exc.user_message
        assert "数据库" in exc.user_message

        # Internal message should have details
        assert "admin" in exc.internal_message
        assert "secret123" in exc.internal_message


if __name__ == "__main__":
    print("Running exception tests...")

    # Test 1
    print("\n[Test 1] Error codes are unique...")
    test = TestErrorCodes()
    test.test_error_codes_are_unique()
    print("[PASS]")

    # Test 2
    print("\n[Test 2] Error code format...")
    test.test_error_codes_format()
    print("[PASS]")

    # Test 3
    print("\n[Test 3] AppException basic...")
    test2 = TestAppException()
    test2.test_app_exception_basic()
    print("[PASS]")

    # Test 4
    print("\n[Test 4] AppException with internal message...")
    test2.test_app_exception_with_internal_message()
    print("[PASS]")

    # Test 5
    print("\n[Test 5] AppException to_dict...")
    test2.test_app_exception_to_dict()
    print("[PASS]")

    # Test 6
    print("\n[Test 6] Specific exceptions...")
    test3 = TestSpecificExceptions()
    test3.test_authentication_error()
    test3.test_validation_error()
    test3.test_verification_code_error()
    test3.test_rate_limit_error()
    test3.test_database_error()
    test3.test_redis_error()
    test3.test_sms_service_error()
    print("[PASS]")

    # Test 7
    print("\n[Test 7] Error message separation...")
    test4 = TestErrorMessageSeparation()
    test4.test_redis_error_no_connection_string()
    test4.test_database_error_no_credentials()
    print("[PASS]")

    print("\n" + "="*50)
    print("All exception tests passed!")
