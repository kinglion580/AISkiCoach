"""
Authentication test utilities
Mock verification codes, create test users, get auth tokens
"""
from typing import Optional, Dict
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import User, UserCreate


class MockSMSService:
    """Mock SMS service for testing"""

    def __init__(self):
        self.sent_messages: list[Dict] = []
        self.should_fail = False

    def send_verification_code(self, phone: str, code: str) -> bool:
        """Mock sending verification code"""
        if self.should_fail:
            return False

        self.sent_messages.append({
            "phone": phone,
            "code": code,
            "type": "verification_code"
        })
        return True

    def get_last_code(self, phone: str) -> Optional[str]:
        """Get the last verification code sent to a phone number"""
        for msg in reversed(self.sent_messages):
            if msg["phone"] == phone:
                return msg["code"]
        return None

    def clear(self):
        """Clear sent messages"""
        self.sent_messages.clear()

    def set_fail(self, should_fail: bool = True):
        """Set whether sending should fail"""
        self.should_fail = should_fail


def mock_verification_code(phone: str, code: str = "123456") -> Dict:
    """
    Create a mock verification code entry for testing

    Args:
        phone: Phone number
        code: Verification code (default: "123456")

    Returns:
        Dict with verification code data
    """
    from datetime import datetime
    return {
        "phone": phone,
        "code": code,
        "created_at": datetime.utcnow().isoformat(),
        "attempts": 0
    }


def create_test_user_with_phone(
    session: Session,
    phone: str = "13800138000",
    full_name: Optional[str] = None,
    **kwargs
) -> User:
    """
    Create a test user with phone number

    Args:
        session: Database session
        phone: Phone number (default: "13800138000")
        full_name: User's full name
        **kwargs: Additional user fields

    Returns:
        Created User object
    """
    from sqlmodel import select

    # Check if user already exists
    existing_user = session.exec(
        select(User).where(User.phone == phone)
    ).first()

    if existing_user:
        return existing_user

    # Create new user
    user_data = {
        "phone": phone,
        "full_name": full_name or f"Test User {phone[-4:]}",
        "is_active": True,
        **kwargs
    }

    user = User(**user_data)
    session.add(user)
    session.commit()
    session.refresh(user)

    return user


def get_verification_code_token(
    client: TestClient,
    phone: str = "13800138000",
    code: str = "123456"
) -> str:
    """
    Get authentication token using verification code login

    Args:
        client: FastAPI test client
        phone: Phone number
        code: Verification code

    Returns:
        JWT access token
    """
    # Send verification code (in test environment, code is fixed)
    send_response = client.post(
        "/api/v1/auth/send-code",
        json={"phone": phone}
    )

    if send_response.status_code != 200:
        raise Exception(f"Failed to send code: {send_response.json()}")

    # Login with verification code
    login_response = client.post(
        "/api/v1/auth/verify-code",
        json={"phone": phone, "code": code}
    )

    if login_response.status_code != 200:
        raise Exception(f"Failed to login: {login_response.json()}")

    data = login_response.json()
    return data["access_token"]


def get_auth_headers(token: str) -> Dict[str, str]:
    """
    Get authorization headers with Bearer token

    Args:
        token: JWT access token

    Returns:
        Headers dict with Authorization
    """
    return {"Authorization": f"Bearer {token}"}


def get_test_user_token(
    client: TestClient,
    session: Session,
    phone: str = "13800138000"
) -> tuple[User, str]:
    """
    Get or create test user and return user object + token

    Args:
        client: FastAPI test client
        session: Database session
        phone: Phone number

    Returns:
        Tuple of (User, token)
    """
    # Create user if not exists
    user = create_test_user_with_phone(session, phone)

    # Get token
    token = get_verification_code_token(client, phone)

    return user, token


def cleanup_test_user(session: Session, phone: str):
    """
    Delete test user by phone number

    Args:
        session: Database session
        phone: Phone number to delete
    """
    from sqlmodel import select, delete

    # Delete user
    user = session.exec(select(User).where(User.phone == phone)).first()
    if user:
        session.delete(user)
        session.commit()


# Mock Redis for testing
class MockRedisClient:
    """Mock Redis client for testing verification codes"""

    def __init__(self):
        self.data: Dict[str, Dict] = {}

    def setex(self, key: str, time: int, value: str) -> bool:
        """Set key with expiration"""
        import json
        from datetime import datetime, timedelta

        self.data[key] = {
            "value": value,
            "expire_at": datetime.utcnow() + timedelta(seconds=time)
        }
        return True

    def get(self, key: str) -> Optional[str]:
        """Get value by key"""
        from datetime import datetime

        if key not in self.data:
            return None

        entry = self.data[key]
        if datetime.utcnow() > entry["expire_at"]:
            del self.data[key]
            return None

        return entry["value"]

    def delete(self, key: str) -> int:
        """Delete key"""
        if key in self.data:
            del self.data[key]
            return 1
        return 0

    def incr(self, key: str) -> int:
        """Increment counter"""
        from datetime import datetime, timedelta
        import json

        if key not in self.data:
            self.data[key] = {
                "value": "0",
                "expire_at": datetime.utcnow() + timedelta(hours=1)
            }

        current = int(self.data[key]["value"])
        current += 1
        self.data[key]["value"] = str(current)
        return current

    def expire(self, key: str, time: int) -> bool:
        """Set expiration time"""
        from datetime import datetime, timedelta

        if key in self.data:
            self.data[key]["expire_at"] = datetime.utcnow() + timedelta(seconds=time)
            return True
        return False

    def ping(self) -> bool:
        """Ping Redis"""
        return True

    def clear(self):
        """Clear all data"""
        self.data.clear()
