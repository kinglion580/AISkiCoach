from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from sqlmodel import Session, select
from app.models import SkiingMetric, IMUData, BarometerData
import pandas as pd
import numpy as np
import sys
import os
import importlib.util

# 添加ski_compute扩展模块所在的路径
bin_path = os.path.join(os.path.dirname(__file__), 'bin')
sys.path.append(bin_path)

# 直接导入ski_compute模块
import ski_compute

SkiAnalysisSystem = ski_compute.SkiAnalysisSystem
SkiDataProcessor = ski_compute.SkiDataProcessor
SkiDataLoader = ski_compute.SkiDataLoader
   

def compute_metrics_from_raw_data(
    db: Session,
    session_id: str,
    user_id: str,
    device_id: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> List[SkiingMetric]:
    """
    从原始数据（IMU、GPS、气压计）计算metrics数据
    使用SkiAnalysisSystem类进行处理，返回转弯指标并写入数据库
    
    Args:
        db: 数据库会话
        session_id: 滑雪会话ID
        user_id: 用户ID
        device_id: 设备ID
        start_time: 开始时间（可选）
        end_time: 结束时间（可选）
    
    Returns:
        计算得到的metrics数据列表
    """
    print(f"\n{'='*60}")
    print(f"开始计算滑雪指标 - 会话ID: {session_id}")
    print(f"{'='*60}")

    # 构建查询条件
    imu_conditions = [IMUData.session_id == session_id]
    baro_conditions = [BarometerData.session_id == session_id]

    if start_time:
        imu_conditions.append(IMUData.timestamp >= start_time)
        baro_conditions.append(BarometerData.timestamp >= start_time)
    if end_time:
        imu_conditions.append(IMUData.timestamp <= end_time)
        baro_conditions.append(BarometerData.timestamp <= end_time)


    # 获取IMU原始数据
    imu_data = db.exec(
        select(IMUData).where(*imu_conditions).order_by(IMUData.timestamp)
    ).all()

    # 获取气压计原始数据
    baro_data = db.exec(
        select(BarometerData).where(*baro_conditions).order_by(BarometerData.timestamp)
    ).all()

    if not imu_data and not baro_data:
        raise ValueError("No raw IMU or barometer data found for the specified session and time range")

    print(f"✓ 从数据库读取到 {len(imu_data)} 条IMU数据，{len(baro_data)} 条气压计数据")

    # 转换为DataFrame格式
    imu_df = pd.DataFrame([imu.dict() for imu in imu_data]) if imu_data else pd.DataFrame()
    baro_df = pd.DataFrame([baro.dict() for baro in baro_data]) if baro_data else pd.DataFrame()

    # 只读取时间戳、加速度、角速度
    imu_df = imu_df[['timestamp', 'source_id', 'acc_x', 'acc_y', 'acc_z', 'gyro_x', 'gyro_y', 'gyro_z']]
    baro_df = baro_df[['timestamp', 'pressure']]

    # 只要source_id为default的IMU数据
    imu_df = imu_df[imu_df['source_id'] == 0]

    # 确保所有数值列都转换为float类型
    numeric_columns = ['acc_x', 'acc_y', 'acc_z', 'gyro_x', 'gyro_y', 'gyro_z']
    for col in numeric_columns:
        if col in imu_df.columns:
            imu_df[col] = imu_df[col].astype(float)

    # 加速度单位：m/s^2
    GRAVITY = 9.80665
    acc_columns = ['acc_x', 'acc_y', 'acc_z']
    if all(col in imu_df.columns for col in acc_columns):
        for col in acc_columns:
            imu_df[col] = imu_df[col] * GRAVITY

    # 确保气压计数值列也为float类型
    baro_numeric_columns = ['pressure', 'temperature']
    for col in baro_numeric_columns:
        if col in baro_df.columns:
            baro_df[col] = baro_df[col].astype(float)

    # 时间改为时间戳格式
    imu_df['datetime'] = pd.to_datetime(imu_df['timestamp'])
    datetime_utc8 = imu_df['datetime'].dt.tz_localize('Asia/Shanghai')
    imu_df['timestamp'] = datetime_utc8.astype('int64') // 10**6  # 毫秒级时间戳
    baro_df['datetime'] = pd.to_datetime(baro_df['timestamp'])
    datetime_utc8 = baro_df['datetime'].dt.tz_localize('Asia/Shanghai')
    baro_df['timestamp'] = datetime_utc8.astype('int64') // 10**6  # 毫秒级时间戳

    print(imu_df.shape)
    print(imu_df.head())
    print(baro_df.head())

    if not imu_df.empty:
        print(f"✓ IMU数据时间范围: {imu_df['timestamp'].min()} 到 {imu_df['timestamp'].max()}")
    if not baro_df.empty:
        print(f"✓ 气压计数据时间范围: {baro_df['timestamp'].min()} 到 {baro_df['timestamp'].max()}")

    # 使用SkiAnalysisSystem处理数据
    print(f"\n--- 使用SkiAnalysisSystem处理数据 ---")

    try:
        # 初始化数据处理器和滑雪分析系统
        processor = SkiDataProcessor()

        # 估算采样频率（如果数据中包含频率信息）
        imu_fs = 100  # 默认IMU采样频率
        baro_fs = 1  # 默认气压计采样频率

        print(f"✓ 估算采样频率: IMU {imu_fs:.1f}Hz, 气压计 {baro_fs:.1f}Hz")

        # 初始化滑雪分析系统
        analysis_system = SkiAnalysisSystem(
            baro_df=baro_df,
            imu_df=imu_df,
            gps_df=None,  # 如果有GPS数据可以传入
            imu_fs=imu_fs,
            baro_fs=baro_fs,
            gps_fs=1,
            processor=processor
        )

        print(f"✓ SkiAnalysisSystem初始化完成")

        # 调用完整的数据处理流水线
        results = analysis_system.process_ski_session()

        print(f"✓ 数据处理完成")

        # 提取转弯数据并创建metrics
        metrics_list = []
        total_turns = 0

        if isinstance(results, list):
            # results是一个包含所有滑雪段分析的列表
            for segment_result in results:
                if isinstance(segment_result, dict) and 'turns' in segment_result:
                    turns = segment_result['turns']
                    total_turns += len(turns)

                    for turn in turns:
                        # 提取转弯的关键指标并映射到数据库字段
                        # 判断这个弯是前刃还是后刃主导
                        edge_angle_front = Decimal(str(turn.get('front_edge_angle', 0)))
                        edge_angle_back = Decimal(str(turn.get('back_edge_angle', 0)))
                        edge_angle_speed_front=Decimal('0')
                        edge_angle_speed_back=Decimal('0')
                        edge_displacement_front=Decimal('0')
                        edge_displacement_back=Decimal('0')

                        if abs(float(edge_angle_front)) > abs(float(edge_angle_back)):
                            edge_angle_front = Decimal(str(turn.get('front_edge_angle', 0)))
                            edge_angle_speed_front = Decimal(str(turn.get('avg_skiing_speed', 0)))
                            edge_displacement_front = Decimal(str(turn.get('carving_distance', 0)))  
                        else:
                            edge_angle_back = Decimal(str(turn.get('back_edge_angle', 0)))
                            edge_angle_speed_back = Decimal(str(turn.get('avg_skiing_speed', 0)))
                            edge_displacement_back = Decimal(str(turn.get('carving_distance', 0))) 

                        # 处理edge_time_ratio防止除零
                        carving_time = turn.get('carving_time', 0)
                        turn_duration = turn.get('turn_duration', 1)
                        edge_time_ratio = None
                        if turn_duration and carving_time != 0:
                            try:
                                edge_time_ratio = Decimal(str(carving_time)) / Decimal(str(turn_duration))
                            except (ZeroDivisionError, TypeError):
                                edge_time_ratio = None

                        metric = SkiingMetric(
                            user_id=user_id,
                            device_id=device_id,
                            session_id=session_id,
                            timestamp=datetime.now(),  # 使用当前时间作为时间戳

                            # 立刃相关指标 - 转换为Decimal
                            edge_angle=Decimal(str(turn.get('roll_angle', 0))) if turn.get('roll_angle') is not None else None,
                            edge_angle_speed=Decimal(str(turn.get('avg_vv_kmh', 0))) if turn.get('avg_vv_kmh') is not None else None,
                            edge_angle_front=edge_angle_front if edge_angle_front != 0 else None,
                            edge_angle_back=edge_angle_back if edge_angle_back != 0 else None,
                            edge_angle_speed_front=edge_angle_speed_front if edge_angle_speed_front != 0 else None,
                            edge_angle_speed_back=edge_angle_speed_back if edge_angle_speed_back != 0 else None,
                            edge_displacement=Decimal(str(turn.get('total_distance', 0))) if turn.get('total_distance') is not None else None,
                            edge_displacement_front=edge_displacement_front if edge_displacement_front != 0 else None,
                            edge_displacement_back=edge_displacement_back if edge_displacement_back != 0 else None,
                            edge_time_ratio=edge_time_ratio,
                            edge_duration_seconds=turn.get('carving_time', None),

                            # 转弯相关指标
                            turn_detected=True,
                            turn_direction=turn.get('direction', None),
                            turn_radius=Decimal(str(turn.get('turn_radius', 0))) if turn.get('turn_radius') is not None else None,
                            turn_duration_seconds=turn.get('turn_duration', None),

                            # 运动相关指标
                            speed_kmh=Decimal(str(turn.get('avg_skiing_speed', 0))) if turn.get('avg_skiing_speed') is not None else None,
                            slope_angle=Decimal(str(segment_result.get('slope_angle', 0))) if segment_result.get('slope_angle') is not None else None,
                        )
                        metrics_list.append(metric)

        print(f"✓ 提取到 {len(metrics_list)} 个转弯指标（总共 {total_turns} 个转弯）")

        # 如果有额外的整体数据，也可以添加其他指标
        if not metrics_list:
            # 如果没有转弯数据，创建一个基础指标记录
            metric = SkiingMetric(
                user_id=user_id,
                device_id=device_id,
                session_id=session_id,
                timestamp=datetime.now(),
                edge_angle=None,
                edge_angle_front=None,
                edge_angle_back=None,
                edge_angle_speed=None,
                edge_angle_speed_front=None,
                edge_angle_speed_back=None,
                edge_displacement=None,
                edge_displacement_front=None,
                edge_displacement_back=None,
                edge_time_ratio=None,
                edge_duration_seconds=None,
                turn_detected=False,
                turn_direction=None,
                turn_radius=None,
                turn_duration_seconds=None,
                speed_kmh=None,
                slope_angle=None,
            )
            metrics_list.append(metric)

        print(f"✓ 指标计算完成，共 {len(metrics_list)} 条记录")

        # 写入数据库
        if metrics_list:
            print("✓ 正在写入数据库...")
            db.add_all(metrics_list)
            db.commit()
            print("✓ 数据库写入完成")

        return metrics_list

    except Exception as e:
        print(f"❌ 处理数据时出错: {e}")
        import traceback
        traceback.print_exc()

        # 返回错误记录
        metric = SkiingMetric(
            user_id=user_id,
            device_id=device_id,
            session_id=session_id,
            timestamp=datetime.now(),
            edge_angle=None,
            edge_angle_front=None,
            edge_angle_back=None,
            edge_angle_speed=None,
            edge_angle_speed_front=None,
            edge_angle_speed_back=None,
            edge_displacement=None,
            edge_displacement_front=None,
            edge_displacement_back=None,
            edge_time_ratio=None,
            edge_duration_seconds=None,
            turn_detected=False,
            turn_direction=None,
            turn_radius=None,
            turn_duration_seconds=None,
            speed_kmh=None,
            slope_angle=None,
        )
        return [metric]



# def test_specific_session():
#     """
#     测试指定会话ID "10000000-0000-0000-0000-000000000003" 的数据读取
#     """
#     from sqlmodel import create_engine, Session, select
#     from app.core.config import settings
#     from app.models import IMUData, BarometerData, SkiingSession
#     from datetime import datetime

#     print("=" * 80)
#     print("测试指定会话ID的数据读取")
#     print("=" * 80)

#     start_time = '2025-10-30 18:34:07.850000'
#     end_time = '2025-10-30 18:46:23.23'


#     try:
#         # 连接数据库
#         engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))

#         with Session(engine) as db:
#             session_id = '10000000-0000-0000-0000-000000000003'
#             print(f"检查会话ID: {session_id}")

#             # 检查会话是否存在
#             session = db.get(SkiingSession, session_id)
#             if not session:
#                 print(f"❌ 未找到会话: {session_id}")
#                 # 显示现有会话
#                 existing_sessions = db.exec(select(SkiingSession).limit(3)).all()
#                 print("现有会话:")
#                 for s in existing_sessions:
#                     print(f"  - ID: {s.id}")
#                     print(f"    用户ID: {s.user_id}")
#                     print(f"    设备ID: {s.device_id}")
#                     print(f"    开始时间: {s.start_time}")
#                     print(f"    状态: {s.session_status}")
#                     print()
#                 return

#             print(f"✅ 找到会话: {session_id}")
#             print(f"用户ID: {session.user_id}")
#             print(f"设备ID: {session.device_id}")
#             print(f"开始时间: {session.start_time}")
#             print(f"状态: {session.session_status}")
#             print()

#             # 转换时间格式
#             from datetime import datetime
#             start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S.%f')
#             end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S.%f')

#             # 查询IMU数据 - 使用时间范围条件
#             imu_data = db.exec(
#                 select(IMUData).where(
#                     IMUData.session_id == session_id,
#                     IMUData.timestamp >= start_dt,
#                     IMUData.timestamp <= end_dt
#                 ).order_by(IMUData.timestamp)
#             ).all()

#             # 查询气压计数据 - 使用时间范围条件
#             baro_data = db.exec(
#                 select(BarometerData).where(
#                     BarometerData.session_id == session_id,
#                     BarometerData.timestamp >= start_dt,
#                     BarometerData.timestamp <= end_dt
#                 ).order_by(BarometerData.timestamp)
#             ).all()

#             print(f"📊 IMU数据记录数: {len(imu_data)}")
#             print(f"📊 气压计数据记录数: {len(baro_data)}")
#             print()

#             if imu_data:
#                 print("📈 IMU数据详情 (前5条):")
#                 print("-" * 50)
#                 for i, imu in enumerate(imu_data[:5]):
#                     print(f"  记录 {i+1}:")
#                     print(f"    时间戳: {imu.timestamp}")
#                     print(f"    加速度: X={imu.acc_x}, Y={imu.acc_y}, Z={imu.acc_z}")
#                     print(f"    陀螺仪: X={imu.gyro_x}, Y={imu.gyro_y}, Z={imu.gyro_z}")
#                     print()

#             if baro_data:
#                 print("🌡️ 气压计数据详情 (前5条):")
#                 print("-" * 50)
#                 for i, baro in enumerate(baro_data[:5]):
#                     print(f"  记录 {i+1}:")
#                     print(f"    时间戳: {baro.timestamp}")
#                     print(f"    气压: {baro.pressure}")
#                     print(f"    温度: {baro.temperature}")
#                     print()

#             # 如果有数据，尝试运行compute_metrics_from_raw_data
#             if imu_data or baro_data:
#                 print("🔄 尝试计算metrics数据...")
#                 try:
#                     metrics = compute_metrics_from_raw_data(
#                         db=db,
#                         session_id=session_id,
#                         user_id=str(session.user_id),
#                         device_id=str(session.device_id),
#                         start_time=start_dt,
#                         end_time=end_dt,
#                     )
#                     print(f"✅ 成功计算得到 {len(metrics)} 条metrics数据")

#                     # 显示前3条metrics数据
#                     if metrics:
#                         print("\n📋 Metrics数据样例 (前3条):")
#                         print("-" * 50)
#                         for i, metric in enumerate(metrics[:3]):
#                             print(f"  Metrics {i+1}:")
#                             print(f"    时间戳: {metric.timestamp}")
#                             print(f"    立刃角度: {metric.edge_angle}")
#                             print(f"    速度(km/h): {metric.speed_kmh}")
#                             print(f"    坡度角度: {metric.slope_angle}")
#                             print(f"    转弯检测: {metric.turn_detected}")
#                             print()
#                 except Exception as e:
#                     print(f"❌ 计算metrics时出错: {e}")
#                     import traceback
#                     traceback.print_exc()
#             else:
#                 print("❌ 没有找到原始数据，无法计算metrics")

#     except Exception as e:
#         print(f"❌ 发生错误: {e}")
#         import traceback
#         traceback.print_exc()



# if __name__ == "__main__":
#     print("🚀 滑雪指标计算系统")
#     print("=" * 50)

#     test_specific_session()