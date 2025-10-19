import uuid
from typing import Any, List
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, delete, func, select, and_, desc
from pydantic import BaseModel

from app import crud
from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models import (
    Item,
    Message,
    User,
    UserCreate,
    UserPublic,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
    SkiingSession,
)
from app.utils import generate_new_account_email, send_email

router = APIRouter(prefix="/users", tags=["users"])


# ======================
# 用户统计相关模型
# ======================

class UserStatsResponse(BaseModel):
    """用户统计响应"""
    total_skiing_days: int
    total_skiing_hours: Decimal
    total_skiing_sessions: int
    average_speed: Decimal
    max_speed: Decimal
    total_distance: Decimal
    max_edge_angle: Decimal
    average_edge_time_ratio: Decimal
    recent_sessions_count: int  # 最近30天会话数
    favorite_locations: List[str]  # 最常去的滑雪场


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
def read_users(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve users.
    """

    count_statement = select(func.count()).select_from(User)
    count = session.exec(count_statement).one()

    statement = select(User).offset(skip).limit(limit)
    users = session.exec(statement).all()

    return UsersPublic(data=users, count=count)


@router.post(
    "/", dependencies=[Depends(get_current_active_superuser)], response_model=UserPublic
)
def create_user(*, session: SessionDep, user_in: UserCreate) -> Any:
    """
    Create new user.
    """
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    user = crud.create_user(session=session, user_create=user_in)
    if settings.emails_enabled and user_in.email:
        email_data = generate_new_account_email(
            email_to=user_in.email, username=user_in.email, password=user_in.password
        )
        send_email(
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return user


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """

    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    user_data = user_in.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


# @router.patch("/me/password", response_model=Message)
# def update_password_me(
#     *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
# ) -> Any:
#     """
#     Update own password - DISABLED: New user model uses phone verification instead of passwords
#     """
#     pass


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.delete("/me", response_model=Message)
def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Delete own user.
    """
    if current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    session.delete(current_user)
    session.commit()
    return Message(message="User deleted successfully")


# @router.post("/signup", response_model=UserPublic)
# def register_user(session: SessionDep, user_in: UserRegister) -> Any:
#     """
#     Create new user without the need to be logged in - DISABLED: New user model uses phone verification
#     """
#     pass


@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    user = session.get(User, user_id)
    if user == current_user:
        return user
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    return user


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
def update_user(
    *,
    session: SessionDep,
    user_id: uuid.UUID,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """

    db_user = session.get(User, user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )

    db_user = crud.update_user(session=session, db_user=db_user, user_in=user_in)
    return db_user


@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
def delete_user(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> Message:
    """
    Delete a user.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user == current_user:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    statement = delete(Item).where(col(Item.owner_id) == user_id)
    session.exec(statement)  # type: ignore
    session.delete(user)
    session.commit()
    return Message(message="User deleted successfully")


# ======================
# 用户统计API
# ======================

@router.get("/me/stats", response_model=UserStatsResponse)
def get_user_stats(
    session: SessionDep,
    current_user: CurrentUser
) -> Any:
    """
    获取用户个人统计数据
    
    包括总滑雪天数、总时长、平均速度、最大速度等统计信息
    """
    
    # 基础统计（从用户表获取）
    user_stats = {
        "total_skiing_days": current_user.total_skiing_days,
        "total_skiing_hours": current_user.total_skiing_hours,
        "total_skiing_sessions": current_user.total_skiing_sessions,
        "average_speed": current_user.average_speed
    }
    
    # 从会话数据计算额外统计
    # 最大速度
    max_speed_result = session.exec(
        select(func.max(SkiingSession.max_speed))
        .where(SkiingSession.user_id == current_user.id)
    ).first()
    max_speed = max_speed_result if max_speed_result else Decimal('0.0')
    
    # 总距离
    total_distance_result = session.exec(
        select(func.sum(SkiingSession.total_distance))
        .where(SkiingSession.user_id == current_user.id)
    ).first()
    total_distance = total_distance_result if total_distance_result else Decimal('0.0')
    
    # 最大立刃角度
    max_edge_angle_result = session.exec(
        select(func.max(SkiingSession.max_edge_angle))
        .where(SkiingSession.user_id == current_user.id)
    ).first()
    max_edge_angle = max_edge_angle_result if max_edge_angle_result else Decimal('0.0')
    
    # 平均立刃时间占比
    avg_edge_ratio_result = session.exec(
        select(func.avg(SkiingSession.edge_time_ratio))
        .where(SkiingSession.user_id == current_user.id)
    ).first()
    avg_edge_ratio = avg_edge_ratio_result if avg_edge_ratio_result else Decimal('0.0')
    
    # 最近30天会话数
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_sessions_count = session.exec(
        select(func.count())
        .select_from(SkiingSession)
        .where(
            and_(
                SkiingSession.user_id == current_user.id,
                SkiingSession.start_time >= thirty_days_ago
            )
        )
    ).one()
    
    # 最常去的滑雪场（前5个）
    favorite_locations_result = session.exec(
        select(
            SkiingSession.location_name,
            func.count().label('count')
        )
        .where(
            and_(
                SkiingSession.user_id == current_user.id,
                SkiingSession.location_name.is_not(None)
            )
        )
        .group_by(SkiingSession.location_name)
        .order_by(desc('count'))
        .limit(5)
    ).all()
    
    favorite_locations = [location for location, _ in favorite_locations_result]
    
    return UserStatsResponse(
        total_skiing_days=user_stats["total_skiing_days"],
        total_skiing_hours=user_stats["total_skiing_hours"],
        total_skiing_sessions=user_stats["total_skiing_sessions"],
        average_speed=user_stats["average_speed"],
        max_speed=max_speed,
        total_distance=total_distance,
        max_edge_angle=max_edge_angle,
        average_edge_time_ratio=avg_edge_ratio,
        recent_sessions_count=recent_sessions_count,
        favorite_locations=favorite_locations
    )
