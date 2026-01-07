"""
Integration tests for authentication API endpoints
Tests verification code login flow
"""
import time
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.tests.utils.auth import MockSMSService, MockRedisClient


class TestSendVerificationCode:
    """Test /auth/send-code endpoint"""

    def test_send_code_success(
        self,
        client: TestClient,
        mock_redis: MockRedisClient,
        mock_sms_service: MockSMSService
    ):
        """Test successful verification code sending"""
        phone = "13800138001"

        response = client.post(
            f"{settings.API_V1_STR}/auth/send-code",
            json={"phone": phone}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "验证码发送成功" in data["message"]
        assert data["expires_in"] == settings.VERIFICATION_CODE_EXPIRE_MINUTES * 60

        # Verify SMS was sent
        assert len(mock_sms_service.sent_messages) == 1
        assert mock_sms_service.sent_messages[0]["phone"] == phone

        # Verify code was stored in Redis
        code_key = f"verification_code:{phone}"
        stored_data = mock_redis.get(code_key)
        assert stored_data is not None

    def test_send_code_invalid_phone(self, client: TestClient):
        """Test sending code with invalid phone number"""
        invalid_phones = [
            "1234567890",  # Wrong length
            "23800138000",  # Wrong prefix
            "abc12345678",  # Non-numeric
            "138001380001",  # Too long
        ]

        for phone in invalid_phones:
            response = client.post(
                f"{settings.API_V1_STR}/auth/send-code",
                json={"phone": phone}
            )

            assert response.status_code == 400
            data = response.json()
            assert "手机号" in data["error"]["message"]

    def test_send_code_rate_limit(
        self,
        client: TestClient,
        mock_redis: MockRedisClient,
        mock_sms_service: MockSMSService
    ):
        """Test rate limiting on verification code sending"""
        phone = "13800138002"

        # Send up to the limit (default 5)
        for i in range(settings.VERIFICATION_CODE_RATE_LIMIT_COUNT):
            response = client.post(
                f"{settings.API_V1_STR}/auth/send-code",
                json={"phone": phone}
            )
            assert response.status_code == 200, f"Request {i+1} should succeed"

        # Next request should be rate limited
        response = client.post(
            f"{settings.API_V1_STR}/auth/send-code",
            json={"phone": phone}
        )

        assert response.status_code == 429
        data = response.json()
        assert "频繁" in data["error"]["message"] or data["error"]["code"] == "RATE_3001"


class TestVerifyCodeLogin:
    """Test /auth/verify-code endpoint"""

    def test_verify_code_success(
        self,
        client: TestClient,
        db: Session,
        mock_redis: MockRedisClient,
        mock_sms_service: MockSMSService
    ):
        """Test successful login with verification code"""
        phone = "13800138003"

        # Step 1: Send verification code
        send_response = client.post(
            f"{settings.API_V1_STR}/auth/send-code",
            json={"phone": phone}
        )
        assert send_response.status_code == 200

        # Get the code that was sent
        code = mock_sms_service.get_last_code(phone)
        assert code is not None

        # Step 2: Login with verification code
        login_response = client.post(
            f"{settings.API_V1_STR}/auth/verify-code",
            json={"phone": phone, "code": code}
        )

        assert login_response.status_code == 200
        data = login_response.json()

        # Verify response structure
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["phone"] == phone

        # Verify token is valid
        token = data["access_token"]
        assert len(token) > 0

    def test_verify_code_invalid_code(
        self,
        client: TestClient,
        mock_redis: MockRedisClient,
        mock_sms_service: MockSMSService
    ):
        """Test login with wrong verification code"""
        phone = "13800138004"

        # Send code
        client.post(
            f"{settings.API_V1_STR}/auth/send-code",
            json={"phone": phone}
        )

        # Try to login with wrong code
        response = client.post(
            f"{settings.API_V1_STR}/auth/verify-code",
            json={"phone": phone, "code": "000000"}  # Wrong code
        )

        assert response.status_code == 400
        data = response.json()
        assert "验证码" in data["error"]["message"]

    def test_verify_code_expired(
        self,
        client: TestClient,
        mock_redis: MockRedisClient,
        mock_sms_service: MockSMSService
    ):
        """Test login with expired verification code"""
        phone = "13800138005"

        # Send code
        client.post(
            f"{settings.API_V1_STR}/auth/send-code",
            json={"phone": phone}
        )

        # Simulate expiration by clearing Redis
        code_key = f"verification_code:{phone}"
        mock_redis.delete(code_key)

        # Try to login
        response = client.post(
            f"{settings.API_V1_STR}/auth/verify-code",
            json={"phone": phone, "code": "123456"}
        )

        assert response.status_code == 400
        data = response.json()
        assert "验证码" in data["error"]["message"]

    def test_verify_code_max_attempts(
        self,
        client: TestClient,
        mock_redis: MockRedisClient,
        mock_sms_service: MockSMSService
    ):
        """Test verification code max attempts limit"""
        phone = "13800138006"

        # Send code
        client.post(
            f"{settings.API_V1_STR}/auth/send-code",
            json={"phone": phone}
        )

        # Try wrong code multiple times (max_attempts = 3)
        for i in range(settings.VERIFICATION_CODE_MAX_ATTEMPTS):
            response = client.post(
                f"{settings.API_V1_STR}/auth/verify-code",
                json={"phone": phone, "code": "000000"}
            )
            assert response.status_code == 400

        # After max attempts, even correct code should fail
        correct_code = mock_sms_service.get_last_code(phone)
        response = client.post(
            f"{settings.API_V1_STR}/auth/verify-code",
            json={"phone": phone, "code": correct_code}
        )

        assert response.status_code == 400

    def test_verify_code_no_code_sent(self, client: TestClient):
        """Test login without sending code first"""
        phone = "13800138007"

        response = client.post(
            f"{settings.API_V1_STR}/auth/verify-code",
            json={"phone": phone, "code": "123456"}
        )

        assert response.status_code == 400
        data = response.json()
        assert "验证码" in data["error"]["message"]


class TestAuthenticationFlow:
    """Test complete authentication flow"""

    def test_complete_auth_flow(
        self,
        client: TestClient,
        db: Session,
        mock_redis: MockRedisClient,
        mock_sms_service: MockSMSService
    ):
        """Test complete flow: send code -> verify -> use token"""
        phone = "13800138008"

        # Step 1: Send verification code
        send_response = client.post(
            f"{settings.API_V1_STR}/auth/send-code",
            json={"phone": phone}
        )
        assert send_response.status_code == 200

        # Step 2: Get code and login
        code = mock_sms_service.get_last_code(phone)
        login_response = client.post(
            f"{settings.API_V1_STR}/auth/verify-code",
            json={"phone": phone, "code": code}
        )
        assert login_response.status_code == 200

        # Step 3: Use token to access protected endpoint
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Try to access user profile
        profile_response = client.get(
            f"{settings.API_V1_STR}/users/me",
            headers=headers
        )

        # Should be authorized
        assert profile_response.status_code == 200
        user_data = profile_response.json()
        assert user_data["phone"] == phone

    def test_token_reuse(
        self,
        client: TestClient,
        mock_redis: MockRedisClient,
        mock_sms_service: MockSMSService
    ):
        """Test that token can be reused for multiple requests"""
        phone = "13800138009"

        # Login
        client.post(f"{settings.API_V1_STR}/auth/send-code", json={"phone": phone})
        code = mock_sms_service.get_last_code(phone)
        login_response = client.post(
            f"{settings.API_V1_STR}/auth/verify-code",
            json={"phone": phone, "code": code}
        )

        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Make multiple requests with same token
        for _ in range(3):
            response = client.get(
                f"{settings.API_V1_STR}/users/me",
                headers=headers
            )
            assert response.status_code == 200


class TestAuthenticationSecurity:
    """Test authentication security"""

    def test_invalid_token_rejected(self, client: TestClient):
        """Test that invalid tokens are rejected"""
        headers = {"Authorization": "Bearer invalid_token_here"}

        response = client.get(
            f"{settings.API_V1_STR}/users/me",
            headers=headers
        )

        assert response.status_code == 401

    def test_no_token_rejected(self, client: TestClient):
        """Test that requests without token are rejected"""
        response = client.get(f"{settings.API_V1_STR}/users/me")

        assert response.status_code == 401

    def test_different_users_isolated(
        self,
        client: TestClient,
        db: Session,
        mock_redis: MockRedisClient,
        mock_sms_service: MockSMSService
    ):
        """Test that different users cannot access each other's data"""
        phone1 = "13800138010"
        phone2 = "13800138011"

        # Login as user 1
        client.post(f"{settings.API_V1_STR}/auth/send-code", json={"phone": phone1})
        code1 = mock_sms_service.get_last_code(phone1)
        login1 = client.post(
            f"{settings.API_V1_STR}/auth/verify-code",
            json={"phone": phone1, "code": code1}
        )
        token1 = login1.json()["access_token"]

        # Login as user 2
        client.post(f"{settings.API_V1_STR}/auth/send-code", json={"phone": phone2})
        code2 = mock_sms_service.get_last_code(phone2)
        login2 = client.post(
            f"{settings.API_V1_STR}/auth/verify-code",
            json={"phone": phone2, "code": code2}
        )
        token2 = login2.json()["access_token"]

        # Verify each user sees their own phone
        headers1 = {"Authorization": f"Bearer {token1}"}
        headers2 = {"Authorization": f"Bearer {token2}"}

        response1 = client.get(f"{settings.API_V1_STR}/users/me", headers=headers1)
        response2 = client.get(f"{settings.API_V1_STR}/users/me", headers=headers2)

        assert response1.json()["phone"] == phone1
        assert response2.json()["phone"] == phone2
        assert response1.json()["phone"] != response2.json()["phone"]
