from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, List
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Path, status, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select, func, and_

from app.api.deps import CurrentUser, SessionDep
from app.models import Device, IMUData, SkiingSession, UserDevice


router = APIRouter(prefix="", tags=["ingest"])


class IMUSample(BaseModel):
    timestamp: datetime
    source_id: int
    acc_x: float
    acc_y: float
    acc_z: float
    gyro_x: float
    gyro_y: float
    gyro_z: float
    mag_x: Optional[float] = None
    mag_y: Optional[float] = None
    mag_z: Optional[float] = None
    quaternion_w: Optional[float] = None
    quaternion_x: Optional[float] = None
    quaternion_y: Optional[float] = None
    quaternion_z: Optional[float] = None
    euler_x: Optional[float] = None
    euler_y: Optional[float] = None
    euler_z: Optional[float] = None
    temperature: Optional[float] = None
    battery_level: Optional[int] = Field(default=None, ge=0, le=100)


class IMUBatchRequest(BaseModel):
    request_id: Optional[str] = None
    device_id: str
    samples: list[IMUSample]


# ======================
# IMU数据查询相关模型
# ======================

class IMUDataPoint(BaseModel):
    """IMU数据点"""
    id: str
    timestamp: datetime
    acc_x: Decimal
    acc_y: Decimal
    acc_z: Decimal
    gyro_x: Decimal
    gyro_y: Decimal
    gyro_z: Decimal
    mag_x: Optional[Decimal] = None
    mag_y: Optional[Decimal] = None
    mag_z: Optional[Decimal] = None
    quaternion_w: Optional[Decimal] = None
    quaternion_x: Optional[Decimal] = None
    quaternion_y: Optional[Decimal] = None
    quaternion_z: Optional[Decimal] = None
    euler_x: Optional[Decimal] = None
    euler_y: Optional[Decimal] = None
    euler_z: Optional[Decimal] = None
    temperature: Optional[Decimal] = None
    battery_level: Optional[int] = None


class DataPointsResponse(BaseModel):
    """数据点列表响应"""
    data: List[IMUDataPoint]
    total: int
    page: int
    page_size: int
    has_next: bool


@router.post("/sessions/{session_id}/imu:batch")
def ingest_imu_batch(
    session_id: str = Path(..., description="Skiing session ID"),
    payload: IMUBatchRequest | Any = None,
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

    # 基础字段校验并构建实体
    rows: list[IMUData] = []
    for idx, s in enumerate(samples):
        if not isinstance(s, dict):
            raise HTTPException(status_code=400, detail=f"invalid_sample at index {idx}")
        ts = s.get("timestamp")
        source_id = s.get("source_id")
        acc_x = s.get("acc_x")
        acc_y = s.get("acc_y")
        acc_z = s.get("acc_z")
        gyro_x = s.get("gyro_x")
        gyro_y = s.get("gyro_y")
        gyro_z = s.get("gyro_z")
        if ts is None or source_id is None or any(v is None for v in [acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z]):
            raise HTTPException(status_code=400, detail=f"invalid_sample at index {idx}: missing required fields")
        try:
            ts_dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"invalid_sample at index {idx}: bad timestamp")

        row = IMUData(
            user_id=current_user.id,
            device_id=device.id,
            session_id=ski_sess.id,
            timestamp=ts_dt,
            source_id=int(source_id),
            acc_x=acc_x,
            acc_y=acc_y,
            acc_z=acc_z,
            gyro_x=gyro_x,
            gyro_y=gyro_y,
            gyro_z=gyro_z,
            mag_x=s.get("mag_x"),
            mag_y=s.get("mag_y"),
            mag_z=s.get("mag_z"),
            quaternion_w=s.get("quaternion_w"),
            quaternion_x=s.get("quaternion_x"),
            quaternion_y=s.get("quaternion_y"),
            quaternion_z=s.get("quaternion_z"),
            euler_x=s.get("euler_x"),
            euler_y=s.get("euler_y"),
            euler_z=s.get("euler_z"),
            temperature=s.get("temperature"),
            battery_level=s.get("battery_level"),
        )
        rows.append(row)

    db.add_all(rows)
    db.commit()

    return {
        "request_id": payload.get("request_id"),
        "code": "ok",
        "message": "imu batch accepted",
        "data": {"accepted": len(rows), "failed": 0},
    }


# ======================
# IMU数据查询API
# ======================

@router.get("/sessions/{session_id}/imu-data", response_model=DataPointsResponse)
def get_session_imu_data(
    session_id: str = Path(..., description="Skiing session ID"),
    db: SessionDep = None,
    current_user: CurrentUser = None,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(100, ge=1, le=1000, description="每页数量"),
    start_time: Optional[datetime] = Query(None, description="开始时间筛选"),
    end_time: Optional[datetime] = Query(None, description="结束时间筛选")
) -> Any:
    """
    获取会话的IMU数据
    
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
    conditions = [IMUData.session_id == session_id]
    
    if start_time:
        conditions.append(IMUData.timestamp >= start_time)
    
    if end_time:
        conditions.append(IMUData.timestamp <= end_time)
    
    # 计算总数
    count_statement = select(func.count()).select_from(IMUData).where(and_(*conditions))
    total = db.exec(count_statement).one()
    
    # 分页查询
    offset = (page - 1) * page_size
    statement = (
        select(IMUData)
        .where(and_(*conditions))
        .order_by(IMUData.timestamp)
        .offset(offset)
        .limit(page_size)
    )
    
    imu_data = db.exec(statement).all()
    
    # 构建响应数据
    data_points = []
    for data in imu_data:
        data_point = IMUDataPoint(
            id=str(data.id),
            timestamp=data.timestamp,
            acc_x=data.acc_x,
            acc_y=data.acc_y,
            acc_z=data.acc_z,
            gyro_x=data.gyro_x,
            gyro_y=data.gyro_y,
            gyro_z=data.gyro_z,
            mag_x=data.mag_x,
            mag_y=data.mag_y,
            mag_z=data.mag_z,
            quaternion_w=data.quaternion_w,
            quaternion_x=data.quaternion_x,
            quaternion_y=data.quaternion_y,
            quaternion_z=data.quaternion_z,
            euler_x=data.euler_x,
            euler_y=data.euler_y,
            euler_z=data.euler_z,
            temperature=data.temperature,
            battery_level=data.battery_level
        )
        data_points.append(data_point)
    
    return DataPointsResponse(
        data=data_points,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total
    )


