#!/usr/bin/env python3
"""
TimescaleDB 初始化脚本
在干净环境中自动配置TimescaleDB扩展、超表和策略
"""
import logging
from sqlalchemy import text
from sqlmodel import Session

from app.core.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_timescale() -> None:
    """初始化TimescaleDB配置"""
    with Session(engine) as session:
        try:
            logger.info("🔄 开始初始化TimescaleDB...")
            
            # 1. 检查并创建TimescaleDB扩展
            logger.info("📦 检查TimescaleDB扩展...")
            result = session.exec(text("SELECT * FROM pg_extension WHERE extname = 'timescaledb';"))
            if not result.fetchone():
                logger.info("📦 创建TimescaleDB扩展...")
                session.exec(text("CREATE EXTENSION IF NOT EXISTS timescaledb;"))
                session.commit()
                logger.info("✅ TimescaleDB扩展已创建")
            else:
                logger.info("✅ TimescaleDB扩展已存在")
            
            # 2. 检查表是否存在，如果存在则创建超表
            tables_to_hypertable = ['imu_data', 'gps_data', 'skiing_metrics']
            
            for table_name in tables_to_hypertable:
                # 检查表是否存在
                result = session.exec(text(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = '{table_name}'
                    );
                """))
                table_exists = result.fetchone()[0]
                
                if table_exists:
                    # 检查是否已经是超表
                    result = session.exec(text(f"""
                        SELECT EXISTS (
                            SELECT FROM timescaledb_information.hypertables 
                            WHERE hypertable_name = '{table_name}'
                        );
                    """))
                    is_hypertable = result.fetchone()[0]
                    
                    if not is_hypertable:
                        logger.info(f"🔄 将 {table_name} 转换为超表...")
                        session.exec(text(f"SELECT create_hypertable('{table_name}', 'timestamp');"))
                        session.commit()
                        logger.info(f"✅ {table_name} 已转换为超表")
                    else:
                        logger.info(f"✅ {table_name} 已经是超表")
                else:
                    logger.warning(f"⚠️ 表 {table_name} 不存在，跳过超表创建")
            
            # 3. 配置压缩策略
            logger.info("🗜️ 配置压缩策略...")
            for table_name in tables_to_hypertable:
                # 检查是否已有压缩策略
                result = session.exec(text(f"""
                    SELECT EXISTS (
                        SELECT FROM timescaledb_information.jobs 
                        WHERE hypertable_name = '{table_name}' 
                        AND proc_name = 'policy_compression'
                    );
                """))
                has_compression_policy = result.fetchone()[0]
                
                if not has_compression_policy:
                    # 启用列存储
                    session.exec(text(f"""
                        ALTER TABLE {table_name} SET (
                            timescaledb.compress, 
                            timescaledb.compress_segmentby = 'id, user_id, device_id, session_id'
                        );
                    """))
                    # 添加压缩策略
                    session.exec(text(f"SELECT add_compression_policy('{table_name}', INTERVAL '7 days');"))
                    session.commit()
                    logger.info(f"✅ {table_name} 压缩策略已配置")
                else:
                    logger.info(f"✅ {table_name} 压缩策略已存在")
            
            # 4. 配置数据保留策略
            logger.info("🗑️ 配置数据保留策略...")
            for table_name in tables_to_hypertable:
                # 检查是否已有保留策略
                result = session.exec(text(f"""
                    SELECT EXISTS (
                        SELECT FROM timescaledb_information.jobs 
                        WHERE hypertable_name = '{table_name}' 
                        AND proc_name = 'policy_retention'
                    );
                """))
                has_retention_policy = result.fetchone()[0]
                
                if not has_retention_policy:
                    session.exec(text(f"SELECT add_retention_policy('{table_name}', INTERVAL '1 year');"))
                    session.commit()
                    logger.info(f"✅ {table_name} 保留策略已配置")
                else:
                    logger.info(f"✅ {table_name} 保留策略已存在")
            
            logger.info("🎉 TimescaleDB初始化完成！")
            
        except Exception as e:
            logger.error(f"❌ TimescaleDB初始化失败: {e}")
            raise e


def main() -> None:
    """主函数"""
    logger.info("开始TimescaleDB初始化")
    init_timescale()
    logger.info("TimescaleDB初始化完成")


if __name__ == "__main__":
    main()
