"""Metrics 计算服务模块

该模块负责从 IMU、GPS、气压计原始数据计算滑雪指标（metrics）数据。
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Union
from decimal import Decimal
import uuid
from sqlmodel import Session, select, and_

from app.models import IMUData, GPSData, BarometerData, SkiingMetric


def compute_metrics_from_raw_data(
    db: Session,
    session_id: Union[str, uuid.UUID],
    user_id: Union[str, uuid.UUID],
    device_id: Union[str, uuid.UUID],
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> List[SkiingMetric]:
    """
    从原始数据计算 metrics 数据
    
    Args:
        db: 数据库会话
        session_id: 会话ID（字符串或UUID）
        user_id: 用户ID（字符串或UUID）
        device_id: 设备ID（字符串或UUID）
        start_time: 开始时间（可选）
        end_time: 结束时间（可选）
    
    Returns:
        计算得到的 metrics 数据列表
    """
    # 转换ID为UUID类型（如果需要）
    if isinstance(session_id, str):
        session_id = uuid.UUID(session_id)
    if isinstance(user_id, str):
        user_id = uuid.UUID(user_id)
    if isinstance(device_id, str):
        device_id = uuid.UUID(device_id)
    
    # 1. 获取 IMU 数据
    imu_conditions = [IMUData.session_id == session_id]
    if start_time:
        imu_conditions.append(IMUData.timestamp >= start_time)
    if end_time:
        imu_conditions.append(IMUData.timestamp <= end_time)
    
    imu_statement = (
        select(IMUData)
        .where(and_(*imu_conditions))
        .order_by(IMUData.timestamp)
    )
    imu_data_list = db.exec(imu_statement).all()
    
    # 2. 获取 GPS 数据
    gps_conditions = [GPSData.session_id == session_id]
    if start_time:
        gps_conditions.append(GPSData.timestamp >= start_time)
    if end_time:
        gps_conditions.append(GPSData.timestamp <= end_time)
    
    gps_statement = (
        select(GPSData)
        .where(and_(*gps_conditions))
        .order_by(GPSData.timestamp)
    )
    gps_data_list = db.exec(gps_statement).all()
    
    # 3. 获取气压计数据
    barometer_conditions = [BarometerData.session_id == session_id]
    if start_time:
        barometer_conditions.append(BarometerData.timestamp >= start_time)
    if end_time:
        barometer_conditions.append(BarometerData.timestamp <= end_time)
    
    barometer_statement = (
        select(BarometerData)
        .where(and_(*barometer_conditions))
        .order_by(BarometerData.timestamp)
    )
    barometer_data_list = db.exec(barometer_statement).all()
    
    # 检查数据是否足够
    if not imu_data_list:
        raise ValueError("IMU数据不足，无法计算metrics")
    
    # 4. 调用算法计算 metrics
    # TODO: 这里需要实现具体的算法逻辑
    # 根据文档，算法需要计算：
    # - 立刃角度（基于横滚角Roll分析）
    # - 转弯检测（基于低通滤波的极值检测）
    # - 转弯半径（结合GPS和IMU数据）
    # - 速度指标（GPS速度融合IMU加速度）
    # - 坡面角度（滑板IMU解算）
    # - 其他指标...
    
    metrics_list = _compute_metrics_algorithm(
        imu_data_list=imu_data_list,
        gps_data_list=gps_data_list,
        barometer_data_list=barometer_data_list,
        user_id=user_id,
        device_id=device_id,
        session_id=session_id,
    )
    
    return metrics_list


def _compute_metrics_algorithm(
    imu_data_list: List[IMUData],
    gps_data_list: List[GPSData],
    barometer_data_list: List[BarometerData],
    user_id: str,
    device_id: str,
    session_id: str,
) -> List[SkiingMetric]:
    """
    核心算法：从原始数据计算 metrics
    
    这是一个占位实现，实际算法需要根据文档中的算法描述来实现。
    
    参考文档：
    - docs/算法/算法周会.txt
    - docs/prd.txt (2.5.3 指标解算)
    
    算法要点：
    1. 立刃角度计算：基于横滚角（Roll）分析
    2. 转弯检测：基于低通滤波的极值检测
    3. 转弯半径计算：结合GPS和IMU数据
    4. 速度指标：GPS速度融合IMU加速度
    5. 坡面角度：滑板IMU解算（2度误差）
    """
    metrics_list: List[SkiingMetric] = []
    
    # 创建时间对齐的数据字典，便于查找
    gps_dict = {gps.timestamp: gps for gps in gps_data_list}
    barometer_dict = {baro.timestamp: baro for baro in barometer_data_list}
    
    # 遍历 IMU 数据，为每个时间点计算 metrics
    for imu in imu_data_list:
        # 查找对应时间点的 GPS 和气压计数据（允许一定时间误差）
        gps = _find_nearest_data(imu.timestamp, gps_dict, max_diff_seconds=1.0)
        barometer = _find_nearest_data(imu.timestamp, barometer_dict, max_diff_seconds=1.0)
        
        # TODO: 实现具体的算法计算
        # 这里是一个示例框架，实际需要根据算法文档实现
        
        # 计算立刃角度（示例：使用欧拉角）
        edge_angle = None
        if imu.euler_x is not None:
            # 这里需要根据实际算法计算立刃角度
            # 根据文档，立刃角度基于横滚角（Roll）分析
            edge_angle = float(imu.euler_x)  # 占位实现
        
        # 计算速度（优先使用GPS，否则使用IMU估算）
        speed_kmh = None
        if gps and gps.speed is not None:
            speed_kmh = float(gps.speed) * 3.6  # m/s 转 km/h
        # TODO: 如果没有GPS，可以从IMU加速度积分估算速度
        
        # 计算坡面角度（示例）
        slope_angle = None
        if imu.euler_y is not None:
            # 根据文档，坡面角度由滑板IMU解算，误差约2度
            slope_angle = float(imu.euler_y)  # 占位实现
        
        # 转弯检测（示例：需要实现低通滤波和极值检测）
        turn_detected = False
        turn_direction = None
        turn_radius = None
        # TODO: 实现转弯检测算法
        # 根据文档：用低通滤波（0.5HZ）处理Z轴的角速度，通过极值判断转弯行为
        
        # 创建 metrics 数据点
        metric = SkiingMetric(
            user_id=user_id,
            device_id=device_id,
            session_id=session_id,
            timestamp=imu.timestamp,
            edge_angle=Decimal(str(edge_angle)) if edge_angle is not None else None,
            edge_angle_front=None,  # TODO: 需要区分前后刃
            edge_angle_back=None,  # TODO: 需要区分前后刃
            edge_angle_speed=None,  # TODO: 计算立刃速度
            edge_angle_speed_front=None,
            edge_angle_speed_back=None,
            edge_displacement=None,  # TODO: 计算走刃位移
            edge_displacement_front=None,
            edge_displacement_back=None,
            edge_time_ratio=None,  # TODO: 计算立刃时间占比
            edge_duration_seconds=None,
            turn_detected=turn_detected,
            turn_direction=turn_direction,
            turn_radius=Decimal(str(turn_radius)) if turn_radius is not None else None,
            turn_duration_seconds=None,
            speed_kmh=Decimal(str(speed_kmh)) if speed_kmh is not None else None,
            slope_angle=Decimal(str(slope_angle)) if slope_angle is not None else None,
        )
        
        metrics_list.append(metric)
    
    return metrics_list


def _find_nearest_data(
    target_timestamp: datetime,
    data_dict: dict,
    max_diff_seconds: float = 1.0,
) -> Optional[object]:
    """
    查找最接近目标时间戳的数据点
    
    Args:
        target_timestamp: 目标时间戳
        data_dict: 数据字典，key为时间戳
        max_diff_seconds: 最大时间差（秒）
    
    Returns:
        最接近的数据点，如果时间差超过阈值则返回None
    """
    if not data_dict:
        return None
    
    min_diff = float('inf')
    nearest = None
    
    for timestamp, data in data_dict.items():
        diff = abs((target_timestamp - timestamp).total_seconds())
        if diff < min_diff and diff <= max_diff_seconds:
            min_diff = diff
            nearest = data
    
    return nearest

