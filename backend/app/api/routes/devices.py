from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, List, Optional, Union
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status, Query, Path
from pydantic import BaseModel, Field
from sqlmodel import Session, select, func, and_, desc, asc

from app.api.deps import CurrentUser, SessionDep
from app.models import Device, UserDevice, DeviceCalibration, DeviceCreate, DeviceUpdate, DevicePublic, DeviceCalibrationCreate, DeviceCalibrationPublic
# from app.algorithm.static_clabration import auto_calibrate_imu
import sys
import os
import pandas as pd
# 添加算法模块目录到系统路径
current_file_dir = os.path.dirname(os.path.abspath(__file__))
algorithm_bin_path = os.path.join(current_file_dir, '..', '..', 'algorithm', 'bin')
sys.path.append(algorithm_bin_path)

import imu_clabration


router = APIRouter(prefix="", tags=["devices"])


# ======================
# 设备管理相关模型
# ======================

class DeviceListItem(BaseModel):
    """设备列表项"""
    id: str
    device_id: str
    device_type: str
    device_name: str
    firmware_version: Optional[str] = None
    battery_level: Optional[int] = None
    connection_status: str
    last_seen_at: Optional[datetime] = None
    is_primary: bool = False
    connected_at: Optional[datetime] = None
    created_at: datetime


class DeviceListResponse(BaseModel):
    """设备列表响应"""
    data: List[DeviceListItem]
    total: int
    page: int
    page_size: int
    has_next: bool


class DeviceDetailResponse(BaseModel):
    """设备详情响应"""
    device: DevicePublic
    is_primary: bool
    connected_at: Optional[datetime] = None
    disconnected_at: Optional[datetime] = None
    recent_sessions_count: int
    last_calibration: Optional[DeviceCalibrationPublic] = None


class DeviceBindingRequest(BaseModel):
    """设备绑定请求"""
    device_id: str = Field(description="设备ID，如382EL22G")
    is_primary: bool = Field(default=False, description="是否设为主设备")


class DeviceBindingResponse(BaseModel):
    """设备绑定响应"""
    device: DevicePublic
    binding_status: str
    is_primary: bool


class DeviceUnbindRequest(BaseModel):
    """设备解绑请求"""
    device_id: str = Field(description="设备ID")


class DeviceStatusUpdateRequest(BaseModel):
    """设备状态更新请求"""
    battery_level: Optional[int] = Field(default=None, ge=0, le=100, description="电量百分比")
    connection_status: Optional[str] = Field(default=None, description="连接状态")
    firmware_version: Optional[str] = Field(default=None, description="固件版本")


class DeviceCalibrationRequest(BaseModel):
    """设备校准请求"""
    calibration_step: int = Field(ge=1, le=4, description="校准步骤(1-4)")
    calibration_data: Optional[Union[dict, List[dict]]] = Field(
        default=None, 
        description="校准数据"
    )


class DeviceCalibrationListResponse(BaseModel):
    """设备校准历史响应"""
    data: List[DeviceCalibrationPublic]
    total: int
    page: int
    page_size: int
    has_next: bool


# ======================
# 设备管理API
# ======================

@router.get("/devices", response_model=DeviceListResponse)
def get_user_devices(
    session: SessionDep,
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    device_type: Optional[str] = Query(None, description="设备类型筛选"),
    connection_status: Optional[str] = Query(None, description="连接状态筛选"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向")
) -> Any:
    """
    获取用户的设备列表
    
    - **page**: 页码，从1开始
    - **page_size**: 每页数量，最大100
    - **device_type**: 设备类型筛选 (HeyGo A1, HeyGo R1, HeyGo R2)
    - **connection_status**: 连接状态筛选 (connected, disconnected, connecting, error)
    - **sort_by**: 排序字段 (created_at, device_name, last_seen_at等)
    - **sort_order**: 排序方向 (asc, desc)
    """
    
    # 构建查询条件
    conditions = [UserDevice.user_id == current_user.id]
    
    if device_type:
        conditions.append(Device.device_type == device_type)
    
    if connection_status:
        conditions.append(Device.connection_status == connection_status)
    
    # 构建排序
    sort_column = getattr(Device, sort_by, Device.created_at)
    if sort_order.lower() == "desc":
        order_clause = desc(sort_column)
    else:
        order_clause = asc(sort_column)
    
    # 计算总数
    count_statement = (
        select(func.count())
        .select_from(UserDevice)
        .join(Device, UserDevice.device_id == Device.id)
        .where(and_(*conditions))
    )
    total = session.exec(count_statement).one()
    
    # 分页查询
    offset = (page - 1) * page_size
    statement = (
        select(Device, UserDevice.is_primary, UserDevice.connected_at)
        .join(UserDevice, Device.id == UserDevice.device_id)
        .where(and_(*conditions))
        .order_by(order_clause)
        .offset(offset)
        .limit(page_size)
    )
    
    results = session.exec(statement).all()
    
    # 构建响应数据
    devices = []
    for device, is_primary, connected_at in results:
        device_item = DeviceListItem(
            id=str(device.id),
            device_id=device.device_id,
            device_type=device.device_type,
            device_name=device.device_name,
            firmware_version=device.firmware_version,
            battery_level=device.battery_level,
            connection_status=device.connection_status,
            last_seen_at=device.last_seen_at,
            is_primary=is_primary,
            connected_at=connected_at,
            created_at=device.created_at
        )
        devices.append(device_item)
    
    return DeviceListResponse(
        data=devices,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total
    )


@router.get("/devices/{device_id}", response_model=DeviceDetailResponse)
def get_device_detail(
    device_id: str = Path(..., description="设备ID"),
    session: SessionDep = None,
    current_user: CurrentUser = None
) -> Any:
    """
    获取设备详细信息
    
    - **device_id**: 设备ID，如382EL22G
    """
    
    # 查询设备信息
    device = session.exec(
        select(Device).where(Device.device_id == device_id)
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 查询用户设备绑定关系
    user_device = session.exec(
        select(UserDevice).where(
            and_(
                UserDevice.user_id == current_user.id,
                UserDevice.device_id == device.id
            )
        )
    ).first()
    
    if not user_device:
        raise HTTPException(status_code=403, detail="无权限访问此设备")
    
    # 统计最近会话数（最近30天）
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    from app.models import SkiingSession
    recent_sessions_count = session.exec(
        select(func.count())
        .select_from(SkiingSession)
        .where(
            and_(
                SkiingSession.user_id == current_user.id,
                SkiingSession.device_id == device.id,
                SkiingSession.start_time >= thirty_days_ago
            )
        )
    ).one()
    
    # 查询最近的校准记录
    last_calibration = session.exec(
        select(DeviceCalibration)
        .where(
            and_(
                DeviceCalibration.user_id == current_user.id,
                DeviceCalibration.device_id == device.id
            )
        )
        .order_by(desc(DeviceCalibration.created_at))
        .limit(1)
    ).first()
    
    last_calibration_public = None
    if last_calibration:
        last_calibration_public = DeviceCalibrationPublic(
            id=last_calibration.id,
            user_id=last_calibration.user_id,
            device_id=last_calibration.device_id,
            calibration_step=last_calibration.calibration_step,
            calibration_status=last_calibration.calibration_status,
            calibration_data=last_calibration.calibration_data or {},
            completed_at=last_calibration.completed_at,
            created_at=last_calibration.created_at
        )
    
    return DeviceDetailResponse(
        device=DevicePublic(
            id=device.id,
            device_id=device.device_id,
            device_type=device.device_type,
            device_name=device.device_name,
            firmware_version=device.firmware_version,
            battery_level=device.battery_level,
            connection_status=device.connection_status,
            last_seen_at=device.last_seen_at,
            created_at=device.created_at
        ),
        is_primary=user_device.is_primary,
        connected_at=user_device.connected_at,
        disconnected_at=user_device.disconnected_at,
        recent_sessions_count=recent_sessions_count,
        last_calibration=last_calibration_public
    )


@router.post("/devices/bind", response_model=DeviceBindingResponse)
def bind_device(
    request: DeviceBindingRequest,
    session: SessionDep,
    current_user: CurrentUser
) -> Any:
    """
    绑定设备到用户账户
    
    - **device_id**: 设备ID，如382EL22G
    - **is_primary**: 是否设为主设备
    """
    
    # 查找设备
    device = session.exec(
        select(Device).where(Device.device_id == request.device_id)
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 检查是否已经绑定
    existing_binding = session.exec(
        select(UserDevice).where(
            and_(
                UserDevice.user_id == current_user.id,
                UserDevice.device_id == device.id
            )
        )
    ).first()
    
    if existing_binding:
        raise HTTPException(status_code=409, detail="设备已绑定到当前用户")
    
    # 如果设为主设备，需要先将其他设备设为主设备设为False
    if request.is_primary:
        from sqlmodel import update
        session.exec(
            update(UserDevice)
            .where(UserDevice.user_id == current_user.id)
            .values(is_primary=False)
        )
    
    # 创建设备绑定
    user_device = UserDevice(
        user_id=current_user.id,
        device_id=device.id,
        is_primary=request.is_primary,
        connected_at=datetime.utcnow() if device.connection_status == "connected" else None
    )
    session.add(user_device)
    session.commit()
    session.refresh(user_device)
    
    return DeviceBindingResponse(
        device=DevicePublic(
            id=device.id,
            device_id=device.device_id,
            device_type=device.device_type,
            device_name=device.device_name,
            firmware_version=device.firmware_version,
            battery_level=device.battery_level,
            connection_status=device.connection_status,
            last_seen_at=device.last_seen_at,
            created_at=device.created_at
        ),
        binding_status="bound",
        is_primary=request.is_primary
    )


@router.post("/devices/unbind", response_model=dict)
def unbind_device(
    request: DeviceUnbindRequest,
    session: SessionDep,
    current_user: CurrentUser
) -> Any:
    """
    解绑设备
    
    - **device_id**: 设备ID，如382EL22G
    """
    
    # 查找设备
    device = session.exec(
        select(Device).where(Device.device_id == request.device_id)
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 查找绑定关系
    user_device = session.exec(
        select(UserDevice).where(
            and_(
                UserDevice.user_id == current_user.id,
                UserDevice.device_id == device.id
            )
        )
    ).first()
    
    if not user_device:
        raise HTTPException(status_code=404, detail="设备未绑定到当前用户")
    
    # 删除绑定关系
    session.delete(user_device)
    session.commit()
    
    return {"message": "设备解绑成功", "device_id": request.device_id}


@router.patch("/devices/{device_id}/status", response_model=DevicePublic)
def update_device_status(
    device_id: str = Path(..., description="设备ID"),
    request: DeviceStatusUpdateRequest = None,
    session: SessionDep = None,
    current_user: CurrentUser = None
) -> Any:
    """
    更新设备状态
    
    - **device_id**: 设备ID，如382EL22G
    - **battery_level**: 电量百分比
    - **connection_status**: 连接状态
    - **firmware_version**: 固件版本
    """
    
    # 查找设备
    device = session.exec(
        select(Device).where(Device.device_id == device_id)
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 验证用户权限
    user_device = session.exec(
        select(UserDevice).where(
            and_(
                UserDevice.user_id == current_user.id,
                UserDevice.device_id == device.id
            )
        )
    ).first()
    
    if not user_device:
        raise HTTPException(status_code=403, detail="无权限访问此设备")
    
    # 更新设备状态
    update_data = request.model_dump(exclude_unset=True)
    if update_data:
        device.sqlmodel_update(update_data)
        device.updated_at = datetime.utcnow()
        if device.connection_status == "connected":
            device.last_seen_at = datetime.utcnow()
        
        session.add(device)
        session.commit()
        session.refresh(device)
    
    return DevicePublic(
        id=device.id,
        device_id=device.device_id,
        device_type=device.device_type,
        device_name=device.device_name,
        firmware_version=device.firmware_version,
        battery_level=device.battery_level,
        connection_status=device.connection_status,
        last_seen_at=device.last_seen_at,
        created_at=device.created_at
    )


@router.post("/devices/{device_id}/set-primary", response_model=dict)
def set_primary_device(
    device_id: str = Path(..., description="设备ID"),
    session: SessionDep = None,
    current_user: CurrentUser = None
) -> Any:
    """
    设置主设备
    
    - **device_id**: 设备ID，如382EL22G
    """
    
    # 查找设备
    device = session.exec(
        select(Device).where(Device.device_id == device_id)
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 验证用户权限
    user_device = session.exec(
        select(UserDevice).where(
            and_(
                UserDevice.user_id == current_user.id,
                UserDevice.device_id == device.id
            )
        )
    ).first()
    
    if not user_device:
        raise HTTPException(status_code=403, detail="无权限访问此设备")
    
    # 先将所有设备设为主设备设为False
    from sqlmodel import update
    session.exec(
        update(UserDevice)
        .where(UserDevice.user_id == current_user.id)
        .values(is_primary=False)
    )
    
    # 设置当前设备为主设备
    user_device.is_primary = True
    session.add(user_device)
    session.commit()
    
    return {"message": "主设备设置成功", "device_id": device_id}


@router.get("/devices/{device_id}/calibrations", response_model=DeviceCalibrationListResponse)
def get_device_calibrations(
    device_id: str = Path(..., description="设备ID"),
    session: SessionDep = None,
    current_user: CurrentUser = None,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
) -> Any:
    """
    获取设备校准历史
    
    - **device_id**: 设备ID，如382EL22G
    - **page**: 页码
    - **page_size**: 每页数量
    """
    
    # 查找设备
    device = session.exec(
        select(Device).where(Device.device_id == device_id)
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 验证用户权限
    user_device = session.exec(
        select(UserDevice).where(
            and_(
                UserDevice.user_id == current_user.id,
                UserDevice.device_id == device.id
            )
        )
    ).first()
    
    if not user_device:
        raise HTTPException(status_code=403, detail="无权限访问此设备")
    
    # 计算总数
    count_statement = select(func.count()).select_from(DeviceCalibration).where(
        and_(
            DeviceCalibration.user_id == current_user.id,
            DeviceCalibration.device_id == device.id
        )
    )
    total = session.exec(count_statement).one()
    
    # 分页查询
    offset = (page - 1) * page_size
    statement = (
        select(DeviceCalibration)
        .where(
            and_(
                DeviceCalibration.user_id == current_user.id,
                DeviceCalibration.device_id == device.id
            )
        )
        .order_by(desc(DeviceCalibration.created_at))
        .offset(offset)
        .limit(page_size)
    )
    
    calibrations = session.exec(statement).all()
    
    # 构建响应数据
    calibration_list = []
    for cal in calibrations:
        calibration_public = DeviceCalibrationPublic(
            id=cal.id,
            user_id=cal.user_id,
            device_id=cal.device_id,
            calibration_step=cal.calibration_step,
            calibration_status=cal.calibration_status,
            calibration_data=cal.calibration_data or {},
            completed_at=cal.completed_at,
            created_at=cal.created_at
        )
        calibration_list.append(calibration_public)
    
    return DeviceCalibrationListResponse(
        data=calibration_list,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total
    )


@router.post("/devices/{device_id}/calibrate", response_model=DeviceCalibrationPublic)
def start_device_calibration(
    device_id: str = Path(..., description="设备ID"),
    request: DeviceCalibrationRequest = None,
    session: SessionDep = None,
    current_user: CurrentUser = None
) -> Any:
    """
    开始设备校准
    
    - **device_id**: 设备ID，如382EL22G
    - **calibration_step**: 校准步骤(1-4)
    - **calibration_data**: 校准数据
    """
    
    # 查找设备
    device = session.exec(
        select(Device).where(Device.device_id == device_id)
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 验证用户权限
    user_device = session.exec(
        select(UserDevice).where(
            and_(
                UserDevice.user_id == current_user.id,
                UserDevice.device_id == device.id
            )
        )
    ).first()
    
    if not user_device:
        raise HTTPException(status_code=403, detail="无权限访问此设备")
    
    # 初始化校准结果字典
    calibration_result = {}
    calibration_status = "in_progress"
    calibration_meta = {}
    final_calibration_data = {}

    # 处理校准数据并调用auto_calibrate_imu函数
    if request.calibration_data:
        print("收到数据，开始校准")
        try:
            # 检查新数据格式 - 包含meta和data字段
            if isinstance(request.calibration_data, dict) and 'meta' in request.calibration_data and 'data' in request.calibration_data:
                # 新数据格式处理：{meta: {...}, data: [[timestamp, acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z], ...]}
                meta = request.calibration_data.get('meta', {})
                data = request.calibration_data.get('data', [])
                
                # 验证数据格式
                if not isinstance(data, list) or len(data) == 0:
                    raise HTTPException(status_code=400, detail="新格式校准数据必须包含非空的数据数组")
                
                # 检查每条数据的字段数量
                for i, row in enumerate(data):
                    if not isinstance(row, list) or len(row) != 7:
                        raise HTTPException(
                            status_code=400, 
                            detail=f"数据行 {i} 格式不正确，应包含7个字段：[timestamp, acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z]"
                        )
                
                # 提取传感器数据
                timestamps = [row[0] for row in data]
                acc_x = [row[1] for row in data]
                acc_y = [row[2] for row in data]
                acc_z = [row[3] for row in data]
                gyro_x = [row[4] for row in data]
                gyro_y = [row[5] for row in data]
                gyro_z = [row[6] for row in data]
                
                # 保存元数据信息
                calibration_meta = {
                    'device_id': meta.get('device_id', ''),
                    'sensor_type': meta.get('sensor_type', ''),
                    'sample_rate': meta.get('sample_rate', 0),
                    'total_count': meta.get('total_count', len(data))
                }
                
                # 保存校准数据（新格式）
                final_calibration_data = {
                    "meta": calibration_meta,
                    "data_count": len(data)
                }
                
                # 转换为auto_calibrate_imu函数期望的格式
                imu_data = pd.DataFrame({
                    'imu_acc_x': acc_x,
                    'imu_acc_y': acc_y,
                    'imu_acc_z': acc_z,
                    'imu_gyro_x': gyro_x,
                    'imu_gyro_y': gyro_y,
                    'imu_gyro_z': gyro_z
                })
                
            else:
                # 兼容旧数据格式
                # 检查必要的数据字段
                required_fields = [
                    'acc_offset_x', 'acc_offset_y', 'acc_offset_z',
                    'gyro_offset_x', 'gyro_offset_y', 'gyro_offset_z'
                ]
                
                # 支持批量处理 - 检查calibration_data是否为列表
                if isinstance(request.calibration_data, list):
                    # 批量处理模式
                    all_acc_x = []
                    all_acc_y = []
                    all_acc_z = []
                    all_gyro_x = []
                    all_gyro_y = []
                    all_gyro_z = []
                    
                    for data_item in request.calibration_data:
                        # 检查每个数据项的必要字段
                        for field in required_fields:
                            if field not in data_item:
                                raise HTTPException(
                                    status_code=400,
                                    detail=f"校准数据缺少必要字段: {field}"
                                )
                        
                        # 收集所有数据
                        all_acc_x.append(float(data_item['acc_offset_x']))
                        all_acc_y.append(float(data_item['acc_offset_y']))
                        all_acc_z.append(float(data_item['acc_offset_z']))
                        all_gyro_x.append(float(data_item['gyro_offset_x']))
                        all_gyro_y.append(float(data_item['gyro_offset_y']))
                        all_gyro_z.append(float(data_item['gyro_offset_z']))
                    
                    # 构建包含所有样本的DataFrame
                    imu_data = pd.DataFrame({
                        'imu_acc_x': all_acc_x,
                        'imu_acc_y': all_acc_y,
                        'imu_acc_z': all_acc_z,
                        'imu_gyro_x': all_gyro_x,
                        'imu_gyro_y': all_gyro_y,
                        'imu_gyro_z': all_gyro_z
                    })
                    
                    # 保存原始校准数据
                    final_calibration_data = {'raw_calibration_data': request.calibration_data}
                else:
                    # 单条数据模式（保持向后兼容）
                    for field in required_fields:
                        if field not in request.calibration_data:
                            raise HTTPException(
                                status_code=400,
                                detail=f"校准数据缺少必要字段: {field}"
                            )
                    
                    # 构建IMU数据DataFrame，直接使用校准数据
                    imu_data = pd.DataFrame({
                        'imu_acc_x': [float(request.calibration_data['acc_offset_x'])],
                        'imu_acc_y': [float(request.calibration_data['acc_offset_y'])],
                        'imu_acc_z': [float(request.calibration_data['acc_offset_z'])],
                        'imu_gyro_x': [float(request.calibration_data['gyro_offset_x'])],
                        'imu_gyro_y': [float(request.calibration_data['gyro_offset_y'])],
                        'imu_gyro_z': [float(request.calibration_data['gyro_offset_z'])]
                    })
                    
                    # 保存原始校准数据
                    final_calibration_data = request.calibration_data.copy()

            # 加速度处理，把单位从g转换为m/s^2
            GRAVITY = 9.80665
            acc_columns = ['imu_acc_x', 'imu_acc_y', 'imu_acc_z']
            for col in acc_columns:
                imu_data[col] = imu_data[col] * GRAVITY
                
            # 调用校准算法
            print("开始校准")
            success, result = imu_clabration.auto_calibrate_imu(
                imu_data,
                static_window_size=100,
                rotation_window_size=200,
                rotation_purity_threshold=0.8,
                verbose=False
            )
            
            if success:
                # 打印校准结果
                print("校准成功")
                print("旋转矩阵:", result['R_board_to_imu'].tolist())
                print("安装角度:", result['installation_angles'].tolist())
                print("纯度:", result['purity'])
                print("静态窗口:", result['static_slice'])
                print("旋转窗口:", result['rotation_slice'])

                calibration_result = {
                    'calibration_success': True,
                    'rotation_matrix': result['R_board_to_imu'].tolist(),
                    'installation_angles': result['installation_angles'].tolist(),
                    'purity': result['purity'],
                    'static_window': {
                        'start': result['static_slice'].start,
                        'stop': result['static_slice'].stop
                    },
                    'rotation_window': {
                        'start': result['rotation_slice'].start,
                        'stop': result['rotation_slice'].stop
                    }
                }
                calibration_status = "completed"
            else:
                # 打印校准失败信息
                print("校准失败:", result)
                calibration_result = {
                    'calibration_success': False,
                    'error_message': result
                }
                calibration_status = "failed"
                
        except Exception as e:
            # 捕获所有异常，确保API不会崩溃
            print(f"校准过程中发生错误: {str(e)}")
            calibration_result = {
                'calibration_success': False,
                'error_message': f"校准过程中发生错误: {str(e)}"
            }
            calibration_status = "failed"
    
    # 合并原始校准数据和校准结果
    final_calibration_data.update(calibration_result)
    
    # 创建设备校准记录
    calibration = DeviceCalibration(
        user_id=current_user.id,
        device_id=device.id,
        calibration_step=request.calibration_step,
        calibration_status=calibration_status,
        calibration_data=final_calibration_data
    )
    
    # 设置校准数据字段（从calibration_data dict拆分）
    if request.calibration_data:
        if isinstance(request.calibration_data, dict) and 'meta' in request.calibration_data and 'data' in request.calibration_data:
            # 新数据格式 - 使用第一条数据作为偏移量
            data = request.calibration_data.get('data', [])
            if data:
                # 使用第一条数据
                first_item = data[0]
                acc_x_avg = float(first_item[1])
                acc_y_avg = float(first_item[2])
                acc_z_avg = float(first_item[3])
                gyro_x_avg = float(first_item[4])
                gyro_y_avg = float(first_item[5])
                gyro_z_avg = float(first_item[6])
                
                calibration.acc_offset_x = Decimal(str(acc_x_avg))
                calibration.acc_offset_y = Decimal(str(acc_y_avg))
                calibration.acc_offset_z = Decimal(str(acc_z_avg))
                calibration.gyro_offset_x = Decimal(str(gyro_x_avg))
                calibration.gyro_offset_y = Decimal(str(gyro_y_avg))
                calibration.gyro_offset_z = Decimal(str(gyro_z_avg))
        elif isinstance(request.calibration_data, list) and request.calibration_data:
            # 批量处理模式 - 使用第一个数据项的值
            first_item = request.calibration_data[0]
            calibration.acc_offset_x = Decimal(str(first_item.get('acc_offset_x', 0)))
            calibration.acc_offset_y = Decimal(str(first_item.get('acc_offset_y', 0)))
            calibration.acc_offset_z = Decimal(str(first_item.get('acc_offset_z', 0)))
            calibration.gyro_offset_x = Decimal(str(first_item.get('gyro_offset_x', 0)))
            calibration.gyro_offset_y = Decimal(str(first_item.get('gyro_offset_y', 0)))
            calibration.gyro_offset_z = Decimal(str(first_item.get('gyro_offset_z', 0)))
        else:
            # 单条数据模式
            calibration.acc_offset_x = Decimal(str(request.calibration_data.get('acc_offset_x', 0)))
            calibration.acc_offset_y = Decimal(str(request.calibration_data.get('acc_offset_y', 0)))
            calibration.acc_offset_z = Decimal(str(request.calibration_data.get('acc_offset_z', 0)))
            calibration.gyro_offset_x = Decimal(str(request.calibration_data.get('gyro_offset_x', 0)))
            calibration.gyro_offset_y = Decimal(str(request.calibration_data.get('gyro_offset_y', 0)))
            calibration.gyro_offset_z = Decimal(str(request.calibration_data.get('gyro_offset_z', 0)))
    
    # 如果校准成功，设置完成时间
    if calibration_status == "completed":
        calibration.completed_at = datetime.utcnow()
    
    session.add(calibration)
    session.commit()
    session.refresh(calibration)
    
    return DeviceCalibrationPublic(
        id=calibration.id,
        user_id=calibration.user_id,
        device_id=calibration.device_id,
        calibration_step=calibration.calibration_step,
        calibration_status=calibration.calibration_status,
        calibration_data=calibration.calibration_data or {},
        completed_at=calibration.completed_at,
        created_at=calibration.created_at
    )
