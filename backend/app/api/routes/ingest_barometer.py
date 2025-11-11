from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, List
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Path, status, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select, func, and_

from app.api.deps import CurrentUser, SessionDep
from app.models import Device, BarometerData, SkiingSession, UserDevice


router = APIRouter(prefix="", tags=["ingest"])


class BarometerSample(BaseModel):
    timestamp: datetime
    source_id: int
    pressure: float
    temperature: Optional[float] = None


class BarometerBatchRequest(BaseModel):
    request_id: Optional[str] = None
    device_id: str
    samples: list[BarometerSample]


# ======================
# 气压计数据查询相关模型
# ======================

class BarometerDataPoint(BaseModel):
    """气压计数据点"""
    id: str
    timestamp: datetime
    pressure: Decimal
    temperature: Optional[Decimal] = None


class BarometerDataPointsResponse(BaseModel):
    """气压计数据点列表响应"""
    data: List[BarometerDataPoint]
    total: int
    page: int
    page_size: int
    has_next: bool


@router.post("/sessions/{session_id}/barometer:batch")
def ingest_barometer_batch(
    session_id: str = Path(..., description="Skiing session ID"),
    *,
    payload: BarometerBatchRequest,
    db: SessionDep = None,
    current_user: CurrentUser = None,
):
    try:
        device_id_str = payload.device_id
        samples = payload.samples
        request_id = payload.request_id
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

        rows: list[BarometerData] = []
        for idx, s in enumerate(samples):
            # 支持 Pydantic 模型和原始 dict
            if isinstance(s, BarometerSample):
                s_dict = s.model_dump(exclude_none=True)
            elif isinstance(s, dict):
                s_dict = s
            else:
                raise HTTPException(status_code=400, detail=f"invalid_sample at index {idx}")

            ts = s_dict.get("timestamp")
            source_id = s_dict.get("source_id")
            pressure = s_dict.get("pressure")
            if ts is None or source_id is None or pressure is None:
                raise HTTPException(status_code=400, detail=f"invalid_sample at index {idx}: missing required fields")
            try:
                ts_dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            except Exception:  # noqa: BLE001
                raise HTTPException(status_code=400, detail=f"invalid_sample at index {idx}: bad timestamp")

            row = BarometerData(
                user_id=current_user.id,
                device_id=device.id,
                session_id=ski_sess.id,
                timestamp=ts_dt,
                source_id=int(source_id),
                pressure=pressure,
                temperature=s_dict.get("temperature"),
            )
            rows.append(row)

        db.add_all(rows)
        db.commit()

        return {
            "request_id": request_id,
            "code": "ok",
            "message": "barometer batch accepted",
            "data": {"accepted": len(rows), "failed": 0},
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


# ======================
# 气压计数据查询API
# ======================

@router.get("/sessions/{session_id}/barometer-data", response_model=BarometerDataPointsResponse)
def get_session_barometer_data(
    session_id: str = Path(..., description="Skiing session ID"),
    db: SessionDep = None,
    current_user: CurrentUser = None,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(100, ge=1, le=1000, description="每页数量"),
    start_time: Optional[datetime] = Query(None, description="开始时间筛选"),
    end_time: Optional[datetime] = Query(None, description="结束时间筛选")
) -> Any:
    """
    获取会话的气压计数据
    
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
    conditions = [BarometerData.session_id == session_id]
    
    if start_time:
        conditions.append(BarometerData.timestamp >= start_time)
    
    if end_time:
        conditions.append(BarometerData.timestamp <= end_time)
    
    # 计算总数
    count_statement = select(func.count()).select_from(BarometerData).where(and_(*conditions))
    total = db.exec(count_statement).one()
    
    # 分页查询
    offset = (page - 1) * page_size
    statement = (
        select(BarometerData)
        .where(and_(*conditions))
        .order_by(BarometerData.timestamp)
        .offset(offset)
        .limit(page_size)
    )
    
    barometer_data = db.exec(statement).all()
    
    # 构建响应数据
    data_points = []
    for data in barometer_data:
        data_point = BarometerDataPoint(
            id=str(data.id),
            timestamp=data.timestamp,
            pressure=data.pressure,
            temperature=data.temperature,
        )
        data_points.append(data_point)
    
    return BarometerDataPointsResponse(
        data=data_points,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total
    )

