from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, List
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Path, status, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select, func, and_

from app.api.deps import CurrentUser, SessionDep
from app.models import Device, SkiingMetric, SkiingSession, UserDevice


router = APIRouter(prefix="", tags=["ingest"])


class MetricsSample(BaseModel):
    timestamp: datetime
    edge_angle: Optional[float] = None
    edge_angle_front: Optional[float] = None
    edge_angle_back: Optional[float] = None
    edge_angle_speed: Optional[float] = None
    edge_angle_speed_front: Optional[float] = None
    edge_angle_speed_back: Optional[float] = None
    edge_displacement: Optional[float] = None
    edge_displacement_front: Optional[float] = None
    edge_displacement_back: Optional[float] = None
    edge_time_ratio: Optional[float] = None
    edge_duration_seconds: Optional[int] = None
    turn_detected: Optional[bool] = None
    turn_direction: Optional[str] = None
    turn_radius: Optional[float] = None
    turn_duration_seconds: Optional[int] = None
    speed_kmh: Optional[float] = None
    slope_angle: Optional[float] = None


class MetricsBatchRequest(BaseModel):
    request_id: Optional[str] = None
    device_id: str
    samples: list[MetricsSample]


# ======================
# 滑雪指标查询相关模型
# ======================

class SkiingMetricPoint(BaseModel):
    """滑雪指标数据点"""
    id: str
    timestamp: datetime
    edge_angle: Optional[Decimal] = None
    edge_angle_front: Optional[Decimal] = None
    edge_angle_back: Optional[Decimal] = None
    edge_angle_speed: Optional[Decimal] = None
    edge_angle_speed_front: Optional[Decimal] = None
    edge_angle_speed_back: Optional[Decimal] = None
    edge_displacement: Optional[Decimal] = None
    edge_displacement_front: Optional[Decimal] = None
    edge_displacement_back: Optional[Decimal] = None
    edge_time_ratio: Optional[Decimal] = None
    edge_duration_seconds: Optional[int] = None
    turn_detected: bool = False
    turn_direction: Optional[str] = None
    turn_radius: Optional[Decimal] = None
    turn_duration_seconds: Optional[int] = None
    speed_kmh: Optional[Decimal] = None
    slope_angle: Optional[Decimal] = None


class MetricsDataPointsResponse(BaseModel):
    """滑雪指标数据点列表响应"""
    data: List[SkiingMetricPoint]
    total: int
    page: int
    page_size: int
    has_next: bool


@router.post("/sessions/{session_id}/metrics:batch")
def ingest_metrics_batch(
    session_id: str = Path(..., description="Skiing session ID"),
    payload: MetricsBatchRequest | Any = None,
    db: SessionDep = None,
    current_user: CurrentUser = None,
):
    if payload is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid payload")

    device_id_str = payload.device_id
    samples = payload.samples
    if not device_id_str or samples is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="device_id and samples are required")
    if not isinstance(samples, list) or len(samples) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="samples must be a non-empty array")
    if len(samples) > 5000:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="too many samples")

    # 校验会话归属
    ski_sess = db.get(SkiingSession, session_id)
    if not ski_sess:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session_not_found")
    if ski_sess.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    # 校验设备绑定
    device = db.exec(select(Device).where(Device.device_id == device_id_str)).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device_not_found")
    binding = db.exec(
        select(UserDevice).where((UserDevice.user_id == current_user.id) & (UserDevice.device_id == device.id))
    ).first()
    if not binding:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="device_not_belong_to_user")

    rows: list[SkiingMetric] = []
    for idx, s in enumerate(samples):
        if not isinstance(s, dict):
            raise HTTPException(status_code=400, detail=f"invalid_sample at index {idx}")
        ts = s.get("timestamp")
        if ts is None:
            raise HTTPException(status_code=400, detail=f"invalid_sample at index {idx}: timestamp is required")
        try:
            ts_dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"invalid_sample at index {idx}: bad timestamp")

        row = SkiingMetric(
            user_id=current_user.id,
            device_id=device.id,
            session_id=ski_sess.id,
            timestamp=ts_dt,
            edge_angle=s.get("edge_angle"),
            edge_angle_front=s.get("edge_angle_front"),
            edge_angle_back=s.get("edge_angle_back"),
            edge_angle_speed=s.get("edge_angle_speed"),
            edge_angle_speed_front=s.get("edge_angle_speed_front"),
            edge_angle_speed_back=s.get("edge_angle_speed_back"),
            edge_displacement=s.get("edge_displacement"),
            edge_displacement_front=s.get("edge_displacement_front"),
            edge_displacement_back=s.get("edge_displacement_back"),
            edge_time_ratio=s.get("edge_time_ratio"),
            edge_duration_seconds=s.get("edge_duration_seconds"),
            turn_detected=bool(s.get("turn_detected", False)),
            turn_direction=s.get("turn_direction"),
            turn_radius=s.get("turn_radius"),
            turn_duration_seconds=s.get("turn_duration_seconds"),
            speed_kmh=s.get("speed_kmh"),
            slope_angle=s.get("slope_angle"),
        )
        rows.append(row)

    db.add_all(rows)
    db.commit()

    return {
        "request_id": payload.get("request_id"),
        "code": "ok",
        "message": "metrics batch accepted",
        "data": {"accepted": len(rows), "failed": 0},
    }


# ======================
# 滑雪指标查询API
# ======================

@router.get("/sessions/{session_id}/metrics", response_model=MetricsDataPointsResponse)
def get_session_metrics(
    session_id: str = Path(..., description="Skiing session ID"),
    db: SessionDep = None,
    current_user: CurrentUser = None,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(100, ge=1, le=1000, description="每页数量"),
    start_time: Optional[datetime] = Query(None, description="开始时间筛选"),
    end_time: Optional[datetime] = Query(None, description="结束时间筛选")
) -> Any:
    """
    获取会话的滑雪指标数据
    
    - **session_id**: 会话ID
    - **page**: 页码
    - **page_size**: 每页数量，最大1000
    - **start_time**: 开始时间筛选
    - **end_time**: 结束时间筛选
    """
    
    # 验证会话权限
    ski_sess = db.get(SkiingSession, session_id)
    if not ski_sess:
        raise HTTPException(status_code=404, detail="会话不存在")
    if ski_sess.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问")
    
    # 构建查询条件
    conditions = [SkiingMetric.session_id == session_id]
    
    if start_time:
        conditions.append(SkiingMetric.timestamp >= start_time)
    
    if end_time:
        conditions.append(SkiingMetric.timestamp <= end_time)
    
    # 计算总数
    count_statement = select(func.count()).select_from(SkiingMetric).where(and_(*conditions))
    total = db.exec(count_statement).one()
    
    # 分页查询
    offset = (page - 1) * page_size
    statement = (
        select(SkiingMetric)
        .where(and_(*conditions))
        .order_by(SkiingMetric.timestamp)
        .offset(offset)
        .limit(page_size)
    )
    
    metrics_data = db.exec(statement).all()
    
    # 构建响应数据
    data_points = []
    for data in metrics_data:
        data_point = SkiingMetricPoint(
            id=str(data.id),
            timestamp=data.timestamp,
            edge_angle=data.edge_angle,
            edge_angle_front=data.edge_angle_front,
            edge_angle_back=data.edge_angle_back,
            edge_angle_speed=data.edge_angle_speed,
            edge_angle_speed_front=data.edge_angle_speed_front,
            edge_angle_speed_back=data.edge_angle_speed_back,
            edge_displacement=data.edge_displacement,
            edge_displacement_front=data.edge_displacement_front,
            edge_displacement_back=data.edge_displacement_back,
            edge_time_ratio=data.edge_time_ratio,
            edge_duration_seconds=data.edge_duration_seconds,
            turn_detected=data.turn_detected,
            turn_direction=data.turn_direction,
            turn_radius=data.turn_radius,
            turn_duration_seconds=data.turn_duration_seconds,
            speed_kmh=data.speed_kmh,
            slope_angle=data.slope_angle
        )
        data_points.append(data_point)
    
    return MetricsDataPointsResponse(
        data=data_points,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total
    )


