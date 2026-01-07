"""
TimescaleDB 生产环境优化脚本
- 启用压缩以节省存储空间
- 设置数据保留策略
- 创建连续聚合视图以加速查询

运行时机：在初始化 TimescaleDB 表之后运行

配置说明：
- 所有配置参数从 app.core.config.Settings 读取
- 可通过 .env 文件自定义配置
"""
import logging

from sqlmodel import Session, text

from app.core.config import settings
from app.core.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def optimize_timescale() -> None:
    """优化 TimescaleDB 配置"""

    with Session(engine) as session:
        logger.info("开始优化 TimescaleDB 配置...")

        # ========================================
        # 1. 为时序表启用压缩
        # ========================================
        # 从配置读取压缩参数
        compress_after_days = settings.TIMESCALE_COMPRESS_AFTER_DAYS
        segment_by = settings.TIMESCALE_COMPRESS_SEGMENT_BY
        order_by = settings.TIMESCALE_COMPRESS_ORDER_BY

        timescale_tables = [
            {
                "name": "imu_data",
                "segment_by": segment_by,
                "order_by": order_by,
                "compress_after": f"{compress_after_days} days",
            },
            {
                "name": "gps_data",
                "segment_by": segment_by,
                "order_by": order_by,
                "compress_after": f"{compress_after_days} days",
            },
            {
                "name": "barometer_data",
                "segment_by": segment_by,
                "order_by": order_by,
                "compress_after": f"{compress_after_days} days",
            },
            {
                "name": "skiing_metrics",
                "segment_by": segment_by,
                "order_by": order_by,
                "compress_after": f"{compress_after_days} days",
            },
        ]

        for table in timescale_tables:
            try:
                # 检查表是否已经是 hypertable
                check_hypertable = text(f"""
                    SELECT EXISTS (
                        SELECT 1 FROM timescaledb_information.hypertables
                        WHERE hypertable_name = '{table["name"]}'
                    );
                """)
                is_hypertable = session.exec(check_hypertable).first()

                if not is_hypertable:
                    logger.warning(f"表 {table['name']} 不是 hypertable，跳过压缩配置")
                    continue

                # 启用压缩
                logger.info(f"为表 {table['name']} 启用压缩...")
                alter_compression = text(f"""
                    ALTER TABLE {table["name"]} SET (
                        timescaledb.compress,
                        timescaledb.compress_segmentby = '{table["segment_by"]}',
                        timescaledb.compress_orderby = '{table["order_by"]}'
                    );
                """)
                session.exec(alter_compression)

                # 添加压缩策略
                logger.info(f"为表 {table['name']} 添加压缩策略（{table['compress_after']} 后压缩）...")
                add_compression_policy = text(f"""
                    SELECT add_compression_policy('{table["name"]}', INTERVAL '{table["compress_after"]}');
                """)
                session.exec(add_compression_policy)

                logger.info(f"✓ 表 {table['name']} 压缩配置完成")

            except Exception as e:
                # 如果策略已存在，会抛出异常，这是正常的
                if "already exists" in str(e) or "already compressed" in str(e):
                    logger.info(f"表 {table['name']} 压缩策略已存在，跳过")
                else:
                    logger.error(f"配置表 {table['name']} 压缩时出错: {e}")

        # ========================================
        # 2. 设置数据保留策略
        # ========================================
        # 从配置读取保留策略参数
        sensor_data_retention_days = settings.TIMESCALE_RETENTION_SENSOR_DATA_DAYS
        metrics_data_retention_days = settings.TIMESCALE_RETENTION_METRICS_DATA_DAYS

        retention_policies = [
            {
                "name": "imu_data",
                "retention": f"{sensor_data_retention_days} days",
            },
            {
                "name": "gps_data",
                "retention": f"{sensor_data_retention_days} days",
            },
            {
                "name": "barometer_data",
                "retention": f"{sensor_data_retention_days} days",
            },
            {
                "name": "skiing_metrics",
                "retention": f"{metrics_data_retention_days} days",
            },
        ]

        for policy in retention_policies:
            try:
                logger.info(f"为表 {policy['name']} 添加数据保留策略（{policy['retention']}）...")
                add_retention_policy = text(f"""
                    SELECT add_retention_policy('{policy["name"]}', INTERVAL '{policy["retention"]}');
                """)
                session.exec(add_retention_policy)
                logger.info(f"✓ 表 {policy['name']} 保留策略配置完成")

            except Exception as e:
                if "already exists" in str(e):
                    logger.info(f"表 {policy['name']} 保留策略已存在，跳过")
                else:
                    logger.error(f"配置表 {policy['name']} 保留策略时出错: {e}")

        # ========================================
        # 3. 创建连续聚合视图以加速查询
        # ========================================

        # 从配置读取刷新策略参数
        refresh_interval = settings.TIMESCALE_REFRESH_INTERVAL_HOURS
        start_offset = settings.TIMESCALE_REFRESH_START_OFFSET_HOURS
        end_offset = settings.TIMESCALE_REFRESH_END_OFFSET_HOURS

        # 3.1 每小时 IMU 数据聚合（用于趋势分析）
        try:
            logger.info("创建 IMU 数据每小时连续聚合视图...")
            create_imu_hourly = text("""
                CREATE MATERIALIZED VIEW IF NOT EXISTS imu_data_hourly
                WITH (timescaledb.continuous) AS
                SELECT
                    time_bucket('1 hour', timestamp) AS hour,
                    session_id,
                    user_id,
                    device_id,
                    AVG(acc_x) AS avg_acc_x,
                    AVG(acc_y) AS avg_acc_y,
                    AVG(acc_z) AS avg_acc_z,
                    AVG(gyro_x) AS avg_gyro_x,
                    AVG(gyro_y) AS avg_gyro_y,
                    AVG(gyro_z) AS avg_gyro_z,
                    COUNT(*) AS sample_count
                FROM imu_data
                GROUP BY hour, session_id, user_id, device_id;
            """)
            session.exec(create_imu_hourly)

            # 添加刷新策略

            add_refresh_policy = text(f"""
                SELECT add_continuous_aggregate_policy('imu_data_hourly',
                    start_offset => INTERVAL '{start_offset} hours',
                    end_offset => INTERVAL '{end_offset} hour',
                    schedule_interval => INTERVAL '{refresh_interval} hour');
            """)
            session.exec(add_refresh_policy)
            logger.info("✓ IMU 数据每小时聚合视图创建完成")

        except Exception as e:
            if "already exists" in str(e):
                logger.info("IMU 每小时聚合视图已存在，跳过")
            else:
                logger.error(f"创建 IMU 聚合视图时出错: {e}")

        # 3.2 每次滑雪会话的指标聚合（用于会话摘要）
        try:
            logger.info("创建滑雪指标会话聚合视图...")
            create_metrics_summary = text("""
                CREATE MATERIALIZED VIEW IF NOT EXISTS skiing_metrics_session_summary
                WITH (timescaledb.continuous) AS
                SELECT
                    time_bucket('1 day', timestamp) AS day,
                    session_id,
                    user_id,
                    AVG(edge_angle) AS avg_edge_angle,
                    MAX(edge_angle) AS max_edge_angle,
                    AVG(speed_kmh) AS avg_speed_kmh,
                    MAX(speed_kmh) AS max_speed_kmh,
                    COUNT(*) FILTER (WHERE turn_detected = true) AS turn_count,
                    AVG(turn_radius) FILTER (WHERE turn_detected = true) AS avg_turn_radius,
                    COUNT(*) AS total_samples
                FROM skiing_metrics
                GROUP BY day, session_id, user_id;
            """)
            session.exec(create_metrics_summary)

            # 添加刷新策略（从配置读取）
            add_refresh_policy2 = text(f"""
                SELECT add_continuous_aggregate_policy('skiing_metrics_session_summary',
                    start_offset => INTERVAL '1 week',
                    end_offset => INTERVAL '{end_offset} hour',
                    schedule_interval => INTERVAL '{refresh_interval} hour');
            """)
            session.exec(add_refresh_policy2)
            logger.info("✓ 滑雪指标会话聚合视图创建完成")

        except Exception as e:
            if "already exists" in str(e):
                logger.info("滑雪指标聚合视图已存在，跳过")
            else:
                logger.error(f"创建滑雪指标聚合视图时出错: {e}")

        # 3.3 用户每日统计聚合（用于用户仪表板）
        try:
            logger.info("创建用户每日统计聚合视图...")
            create_user_daily = text("""
                CREATE MATERIALIZED VIEW IF NOT EXISTS user_daily_stats
                WITH (timescaledb.continuous) AS
                SELECT
                    time_bucket('1 day', timestamp) AS day,
                    user_id,
                    COUNT(DISTINCT session_id) AS sessions_count,
                    AVG(speed_kmh) AS avg_speed,
                    MAX(speed_kmh) AS max_speed,
                    SUM(CASE WHEN turn_detected THEN 1 ELSE 0 END) AS total_turns
                FROM skiing_metrics
                GROUP BY day, user_id;
            """)
            session.exec(create_user_daily)

            # 添加刷新策略（从配置读取）
            add_refresh_policy3 = text(f"""
                SELECT add_continuous_aggregate_policy('user_daily_stats',
                    start_offset => INTERVAL '1 week',
                    end_offset => INTERVAL '{end_offset} hour',
                    schedule_interval => INTERVAL '{refresh_interval} hour');
            """)
            session.exec(add_refresh_policy3)
            logger.info("✓ 用户每日统计聚合视图创建完成")

        except Exception as e:
            if "already exists" in str(e):
                logger.info("用户每日统计聚合视图已存在，跳过")
            else:
                logger.error(f"创建用户每日统计聚合视图时出错: {e}")

        # 提交所有更改
        session.commit()

        logger.info("=" * 60)
        logger.info("TimescaleDB 优化配置完成！")
        logger.info("=" * 60)
        logger.info("已启用功能：")
        logger.info(f"1. ✓ 时序表数据压缩（{compress_after_days}天后自动压缩）")
        logger.info(f"2. ✓ 数据保留策略（传感器数据{sensor_data_retention_days}天，指标数据{metrics_data_retention_days}天）")
        logger.info(f"3. ✓ 连续聚合视图（每{refresh_interval}小时刷新）")
        logger.info("=" * 60)
        logger.info("配置来源：app.core.config.Settings (.env 文件)")
        logger.info("=" * 60)


if __name__ == "__main__":
    logger.info("运行 TimescaleDB 优化脚本...")
    optimize_timescale()
    logger.info("优化完成！")
