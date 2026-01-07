"""
User session management API endpoints (authentication sessions)
Handles user login session operations: list, logout, etc.
"""
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.domains.auth.schemas import (
    SessionsPublic,
    UserSessionPublic,
    LogoutRequest,
    LogoutResponse
)
from app.domains.auth.models import UserSession
from app.domains.auth.repository import SessionRepository

router = APIRouter()


@router.get("/me", response_model=SessionsPublic)
def get_my_sessions(
    current_user: CurrentUser,
    session: SessionDep
) -> Any:
    """
    Get all active sessions for the current user

    Returns:
        List of active sessions with device info
    """
    # Query active sessions
    statement = select(UserSession).where(
        UserSession.user_id == current_user.id,
        UserSession.is_active == True
    ).order_by(UserSession.last_activity_at.desc())

    sessions = session.exec(statement).all()

    # Convert to public format
    session_list = [
        UserSessionPublic(
            id=s.id,
            user_id=s.user_id,
            session_token=s.session_token[:10] + "...",  # Truncate token for security
            ip_address=s.ip_address,
            expires_at=s.expires_at,
            created_at=s.created_at,
            last_activity_at=s.last_activity_at,
            is_active=s.is_active,
            device_type=s.device_type,
            device_model=s.device_model,
            os_type=s.os_type,
            os_version=s.os_version,
            app_version=s.app_version,
            device_info=s.device_info
        )
        for s in sessions
    ]

    return SessionsPublic(data=session_list, count=len(session_list))


@router.post("/logout", response_model=LogoutResponse)
async def logout_session(
    logout_request: LogoutRequest,
    current_user: CurrentUser,
    session: SessionDep
) -> Any:
    """
    Logout from a specific session or current session

    Args:
        logout_request: Contains optional session_id to logout

    Returns:
        Logout response with success status
    """
    session_repo = SessionRepository(session)

    if logout_request.session_id:
        # Logout specific session
        try:
            session_uuid = uuid.UUID(logout_request.session_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid session ID format"
            )

        # Verify session belongs to current user
        statement = select(UserSession).where(
            UserSession.id == session_uuid,
            UserSession.user_id == current_user.id
        )
        user_session = session.exec(statement).first()

        if not user_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )

        # Invalidate session
        success = await session_repo.invalidate_session(user_session.session_token)

        if success:
            return LogoutResponse(
                success=True,
                message="Session logged out successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to logout session"
            )
    else:
        # Logout current session (would need current session token)
        # For now, just return success
        return LogoutResponse(
            success=True,
            message="Please provide session_id to logout specific session"
        )


@router.post("/logout-all", response_model=LogoutResponse)
async def logout_all_sessions(
    current_user: CurrentUser,
    session: SessionDep
) -> Any:
    """
    Logout from all sessions

    Returns:
        Logout response with number of sessions logged out
    """
    session_repo = SessionRepository(session)

    count = await session_repo.invalidate_all_sessions(current_user.id)

    return LogoutResponse(
        success=True,
        message=f"Logged out from {count} session(s)"
    )


@router.delete("/{session_id}", response_model=LogoutResponse)
async def delete_session(
    session_id: str,
    current_user: CurrentUser,
    session: SessionDep
) -> Any:
    """
    Delete a specific session (same as logout but using DELETE method)

    Args:
        session_id: Session ID to delete

    Returns:
        Logout response
    """
    session_repo = SessionRepository(session)

    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID format"
        )

    # Verify session belongs to current user
    statement = select(UserSession).where(
        UserSession.id == session_uuid,
        UserSession.user_id == current_user.id
    )
    user_session = session.exec(statement).first()

    if not user_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    # Invalidate session
    success = await session_repo.invalidate_session(user_session.session_token)

    if success:
        return LogoutResponse(
            success=True,
            message="Session deleted successfully"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete session"
        )
