from collections.abc import Generator
from typing import Annotated, Optional
import uuid
from datetime import datetime

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
    OAuth2PasswordBearer,
)
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session, select

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.models import TokenPayload, User, UserSession

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token",
    auto_error=False,
)
http_bearer = HTTPBearer(
    auto_error=False,
    description="Paste your JWT (without the 'Bearer ' prefix)",
)


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
# 两种鉴权同时兼容：HTTP Bearer 与 OAuth2 Password（Swagger 原生登录）
BearerDep = Annotated[Optional[HTTPAuthorizationCredentials], Depends(http_bearer)]
OAuthTokenDep = Annotated[Optional[str], Depends(reusable_oauth2)]


def _extract_token_string(
    bearer: Optional[HTTPAuthorizationCredentials], oauth_token: Optional[str]
) -> str:
    if bearer and bearer.credentials:
        return bearer.credentials
    if oauth_token:
        return oauth_token
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    session: SessionDep, bearer: BearerDep, oauth_token: OAuthTokenDep
) -> User:
    """
    Get current user from JWT token with session validation

    Validates:
    1. JWT token signature and expiration
    2. User exists and is active
    3. Session exists and is active (if session_id in token)

    Returns:
        User object

    Raises:
        HTTPException: If authentication fails
    """
    token_str = _extract_token_string(bearer, oauth_token)
    try:
        payload = jwt.decode(
            token_str, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    # Get user
    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Validate session if session_id is present in token
    session_id = getattr(token_data, 'sid', None)
    if session_id:
        try:
            session_uuid = uuid.UUID(session_id)
        except (ValueError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session",
            )

        # Query session
        statement = select(UserSession).where(
            UserSession.id == session_uuid,
            UserSession.user_id == user.id
        )
        user_session = session.exec(statement).first()

        if not user_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session not found",
            )

        # Check if session is active
        if not user_session.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been terminated",
            )

        # Check if session is expired
        if user_session.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has expired",
            )

        # Update last activity time
        user_session.last_activity_at = datetime.utcnow()
        session.add(user_session)
        session.commit()

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user
