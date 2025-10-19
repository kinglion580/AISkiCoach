from datetime import datetime, timezone, timedelta
import uuid
from typing import Optional, Any, List
from decimal import Decimal

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, status, Form, Query
from sqlmodel import Session, select, func, and_, desc, asc

from app.api.deps import CurrentUser, SessionDep
from app.models import Device, SkiingSession, UserDevice


router = APIRouter(prefix="", tags=["sessions"])


# ======================
# Request/Response 模型
# ======================

class StartSessionRequest(BaseModel):
    request_id: Optional[str] = Field(default=None, description="请求ID")
    device_id: str = Field(description="设备ID")
    start_time: datetime = Field(description="开始时间(ISO8601)")
    location_name: Optional[str] = Field(default=None, description="地点名称")
    metadata: Optional[dict] = Field(default=None, description="会话元数据")


class StartSessionData(BaseModel):
    session_id: str
    start_time: datetime


class ApiEnvelope(BaseModel):
    request_id: Optional[str] = None
    code: str
    message: str
    data: dict | StartSessionData | None = None


class FinishSessionRequest(BaseModel):
    request_id: Optional[str] = None
    session_id: str
    end_time: datetime


class FinishSessionData(BaseModel):
    session_id: str
    duration_seconds: int
    max_edge_angle: Optional[float] = None
    edge_time_ratio: Optional[float] = None
    average_speed: Optional[float] = None


class StartSessionRequestModel:
    request_id: Optional[str]
    device_id: str
    start_time: datetime
    location_name: Optional[str] = None
    metadata: Optional[dict] = None


class StartSessionResponseDataModel:
    session_id: str
    start_time: datetime


# ======================
# 会话查询相关模型
# ======================

class SessionSummary(BaseModel):
    """会话摘要信息"""
    id: uuid.UUID
    session_name: str
    location_name: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    max_edge_angle: Optional[Decimal] = None
    max_speed: Optional[Decimal] = None
    average_speed: Optional[Decimal] = None
    total_distance: Optional[Decimal] = None
    session_status: str
    device_name: Optional[str] = None
    created_at: datetime


class SessionsListResponse(BaseModel):
    """会话列表响应"""
    data: List[SessionSummary]
    total: int
    page: int
    page_size: int
    has_next: bool


class SessionDetailResponse(BaseModel):
    """会话详情响应"""
    session: SessionSummary
    device_info: Optional[dict] = None
    session_metadata: Optional[dict] = None
    data_counts: dict = Field(default_factory=dict)  # 各类数据点数量


@router.post("/sessions:start", response_model=ApiEnvelope)
def start_session(
    payload: StartSessionRequest,
    session: SessionDep,
    current_user: CurrentUser,
):
    # 解析与基础校验（P0最小实现，使用字典并做必要字段检查）
    device_id_str = payload.device_id
    start_time = payload.start_time
    location_name = payload.location_name
    metadata = payload.metadata

    # 设备存在性
    device = session.exec(select(Device).where(Device.device_id == device_id_str)).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device_not_found")

    # 设备归属校验
    binding = session.exec(
        select(UserDevice).where(
            (UserDevice.user_id == current_user.id) & (UserDevice.device_id == device.id)
        )
    ).first()
    if not binding:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="device_not_belong_to_user")

    # 创建会话
    new_session = SkiingSession(
        user_id=current_user.id,
        device_id=device.id,
        session_name=location_name or "Ski Session",
        start_time=start_time,
        location_name=location_name,
        session_status="active",
        session_metadata=metadata,
    )
    session.add(new_session)
    session.commit()
    session.refresh(new_session)

    return ApiEnvelope(
        request_id=payload.request_id,
        code="ok",
        message="session started",
        data=StartSessionData(session_id=str(new_session.id), start_time=new_session.start_time),
    )


@router.post("/sessions:start-form", response_model=ApiEnvelope)
def start_session_form(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    device_id: str = Form(description="设备ID，如 382EL22G"),
    start_time: datetime = Form(description="开始时间(ISO8601)，例如 2025-06-10T08:15:30Z"),
    location_name: Optional[str] = Form(default=None, description="地点名称"),
    request_id: Optional[str] = Form(default=None, description="请求ID(可选)"),
    metadata_json: Optional[str] = Form(default=None, description="会话元数据(JSON，可选)"),
):
    """以表单提交开始会话，便于在 Swagger 中逐字段填写。"""
    # 设备存在性
    device = session.exec(select(Device).where(Device.device_id == device_id)).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device_not_found")

    # 设备归属校验
    binding = session.exec(
        select(UserDevice).where((UserDevice.user_id == current_user.id) & (UserDevice.device_id == device.id))
    ).first()
    if not binding:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="device_not_belong_to_user")

    # 解析可选 metadata
    metadata: Optional[dict] = None
    if metadata_json:
        try:
            import json as _json

            metadata = _json.loads(metadata_json)
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="invalid metadata_json (must be valid JSON)")

    new_session = SkiingSession(
        user_id=current_user.id,
        device_id=device.id,
        session_name=location_name or "Ski Session",
        start_time=start_time,
        location_name=location_name,
        session_status="active",
        session_metadata=metadata,
    )
    session.add(new_session)
    session.commit()
    session.refresh(new_session)

    return ApiEnvelope(
        request_id=request_id,
        code="ok",
        message="session started",
        data=StartSessionData(session_id=str(new_session.id), start_time=new_session.start_time),
    )


@router.post("/sessions:finish", response_model=ApiEnvelope)
def finish_session(
    payload: FinishSessionRequest,
    session: SessionDep,
    current_user: CurrentUser,
):
    session_id = payload.session_id
    end_time = payload.end_time

    # 解析并校验 session_id 为 UUID
    try:
        sess_uuid = uuid.UUID(str(session_id))
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid session_id format (UUID expected)")

    ski_sess = session.get(SkiingSession, sess_uuid)
    if not ski_sess:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session_not_found")
    if ski_sess.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    if ski_sess.session_status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="session_not_active")

    # 统一为有时区的 UTC 时间再比较与计算
    start_dt = ski_sess.start_time
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)
    end_dt = end_time
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)

    if end_dt < start_dt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_time")

    # 计算持续时间（秒）
    duration_seconds = int((end_dt - start_dt).total_seconds())
    if duration_seconds < 0:
        duration_seconds = 0

    ski_sess.end_time = end_time
    ski_sess.duration_seconds = duration_seconds
    ski_sess.session_status = "completed"
    session.add(ski_sess)
    session.commit()
    session.refresh(ski_sess)

    return ApiEnvelope(
        request_id=payload.request_id,
        code="ok",
        message="session finished",
        data=FinishSessionData(
            session_id=str(ski_sess.id),
            duration_seconds=ski_sess.duration_seconds or 0,
            max_edge_angle=float(ski_sess.max_edge_angle) if ski_sess.max_edge_angle is not None else None,
            edge_time_ratio=float(ski_sess.edge_time_ratio) if ski_sess.edge_time_ratio is not None else None,
            average_speed=float(ski_sess.average_speed) if ski_sess.average_speed is not None else None,
        ),
    )


# ======================
# 会话查询API
# ======================

@router.get("/sessions", response_model=SessionsListResponse)
def get_user_sessions(
    session: SessionDep,
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="会话状态筛选"),
    start_date: Optional[datetime] = Query(None, description="开始日期筛选"),
    end_date: Optional[datetime] = Query(None, description="结束日期筛选"),
    location: Optional[str] = Query(None, description="地点筛选"),
    sort_by: str = Query("start_time", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向")
) -> Any:
    """
    获取用户的滑雪会话列表
    
    - **page**: 页码，从1开始
    - **page_size**: 每页数量，最大100
    - **status**: 会话状态筛选 (active, completed, cancelled)
    - **start_date**: 开始日期筛选
    - **end_date**: 结束日期筛选
    - **location**: 地点筛选
    - **sort_by**: 排序字段 (start_time, duration_seconds, max_speed等)
    - **sort_order**: 排序方向 (asc, desc)
    """
    
    # 构建查询条件
    conditions = [SkiingSession.user_id == current_user.id]
    
    if status:
        conditions.append(SkiingSession.session_status == status)
    
    if start_date:
        conditions.append(SkiingSession.start_time >= start_date)
    
    if end_date:
        conditions.append(SkiingSession.start_time <= end_date)
    
    if location:
        conditions.append(SkiingSession.location_name.ilike(f"%{location}%"))
    
    # 构建排序
    sort_column = getattr(SkiingSession, sort_by, SkiingSession.start_time)
    if sort_order.lower() == "desc":
        order_clause = desc(sort_column)
    else:
        order_clause = asc(sort_column)
    
    # 计算总数
    count_statement = select(func.count()).select_from(SkiingSession).where(and_(*conditions))
    total = session.exec(count_statement).one()
    
    # 分页查询
    offset = (page - 1) * page_size
    statement = (
        select(SkiingSession, Device.device_name)
        .outerjoin(Device, SkiingSession.device_id == Device.id)
        .where(and_(*conditions))
        .order_by(order_clause)
        .offset(offset)
        .limit(page_size)
    )
    
    results = session.exec(statement).all()
    
    # 构建响应数据
    sessions = []
    for skiing_session, device_name in results:
        session_summary = SessionSummary(
            id=skiing_session.id,
            session_name=skiing_session.session_name,
            location_name=skiing_session.location_name,
            start_time=skiing_session.start_time,
            end_time=skiing_session.end_time,
            duration_seconds=skiing_session.duration_seconds,
            max_edge_angle=skiing_session.max_edge_angle,
            max_speed=skiing_session.max_speed,
            average_speed=skiing_session.average_speed,
            total_distance=skiing_session.total_distance,
            session_status=skiing_session.session_status,
            device_name=device_name,
            created_at=skiing_session.created_at
        )
        sessions.append(session_summary)
    
    return SessionsListResponse(
        data=sessions,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total
    )


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
def get_session_detail(
    session: SessionDep,
    current_user: CurrentUser,
    session_id: uuid.UUID
) -> Any:
    """
    获取特定会话的详细信息
    
    - **session_id**: 会话ID
    """
    
    # 查询会话信息
    statement = (
        select(SkiingSession, Device)
        .outerjoin(Device, SkiingSession.device_id == Device.id)
        .where(
            and_(
                SkiingSession.id == session_id,
                SkiingSession.user_id == current_user.id
            )
        )
    )
    
    result = session.exec(statement).first()
    if not result:
        raise HTTPException(status_code=404, detail="会话不存在或无权限访问")
    
    skiing_session, device = result
    
    # 构建会话摘要
    session_summary = SessionSummary(
        id=skiing_session.id,
        session_name=skiing_session.session_name,
        location_name=skiing_session.location_name,
        start_time=skiing_session.start_time,
        end_time=skiing_session.end_time,
        duration_seconds=skiing_session.duration_seconds,
        max_edge_angle=skiing_session.max_edge_angle,
        max_speed=skiing_session.max_speed,
        average_speed=skiing_session.average_speed,
        total_distance=skiing_session.total_distance,
        session_status=skiing_session.session_status,
        device_name=device.device_name if device else None,
        created_at=skiing_session.created_at
    )
    
    # 构建设备信息
    device_info = None
    if device:
        device_info = {
            "id": device.id,
            "device_id": device.device_id,
            "device_type": device.device_type,
            "device_name": device.device_name,
            "connection_status": device.connection_status,
            "last_seen_at": device.last_seen_at
        }
    
    # 统计各类数据点数量
    from app.models import IMUData, GPSData, SkiingMetric, AIAnalysis
    
    data_counts = {}
    
    # IMU数据数量
    imu_count = session.exec(
        select(func.count()).select_from(IMUData).where(IMUData.session_id == session_id)
    ).one()
    data_counts["imu_data_count"] = imu_count
    
    # GPS数据数量
    gps_count = session.exec(
        select(func.count()).select_from(GPSData).where(GPSData.session_id == session_id)
    ).one()
    data_counts["gps_data_count"] = gps_count
    
    # 滑雪指标数量
    metrics_count = session.exec(
        select(func.count()).select_from(SkiingMetric).where(SkiingMetric.session_id == session_id)
    ).one()
    data_counts["metrics_count"] = metrics_count
    
    # AI分析数量
    analysis_count = session.exec(
        select(func.count()).select_from(AIAnalysis).where(AIAnalysis.session_id == session_id)
    ).one()
    data_counts["analysis_count"] = analysis_count
    
    return SessionDetailResponse(
        session=session_summary,
        device_info=device_info,
        session_metadata=skiing_session.session_metadata,
        data_counts=data_counts
    )


