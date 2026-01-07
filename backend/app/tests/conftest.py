from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from app.models import Item, User
from app.tests.utils.user import authentication_token_from_email
from app.tests.utils.utils import get_superuser_token_headers
from app.tests.utils.auth import (
    MockRedisClient,
    MockSMSService,
    create_test_user_with_phone,
    get_verification_code_token
)


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        init_db(session)
        yield session
        statement = delete(Item)
        session.execute(statement)
        statement = delete(User)
        session.execute(statement)
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )


# Authentication test fixtures

@pytest.fixture(scope="function")
def mock_redis() -> Generator[MockRedisClient, None, None]:
    """Mock Redis client for testing verification codes"""
    mock_client = MockRedisClient()

    # Patch the Redis client in verification_code service
    with patch("app.core.verification_code.verification_code_service.redis_client", mock_client):
        yield mock_client

    # Cleanup
    mock_client.clear()


@pytest.fixture(scope="function")
def mock_sms_service() -> Generator[MockSMSService, None, None]:
    """Mock SMS service for testing"""
    mock_sms = MockSMSService()

    # Patch the SMS service
    with patch("app.core.verification_code.sms_service", mock_sms):
        yield mock_sms

    # Cleanup
    mock_sms.clear()


@pytest.fixture(scope="function")
def auth_phone_user(client: TestClient, db: Session) -> Generator[tuple[User, str], None, None]:
    """
    Create a test user with phone-based authentication

    Returns:
        Tuple of (User, access_token)
    """
    phone = "13900139000"

    # Create user
    user = create_test_user_with_phone(db, phone=phone)

    # Get token using verification code login
    # In test environment, code is fixed to "123456"
    try:
        token = get_verification_code_token(client, phone=phone, code="123456")
        yield user, token
    finally:
        # Cleanup: delete test user
        if user.id:
            db.delete(user)
            db.commit()
