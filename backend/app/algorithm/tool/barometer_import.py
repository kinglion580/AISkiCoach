import os
import sys
import logging
import pandas as pd
import numpy as np
import traceback
from datetime import datetime
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv
import uuid
from decimal import Decimal

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

# 数据库连接
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:changethis@localhost:5432/app")
engine = create_engine(DATABASE_URL)

# 固定的外键数据（用于测试）
TEST_USER_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
TEST_DEVICE_ID = uuid.UUID("10000000-0000-0000-0000-000000000002")
TEST_SESSION_ID = uuid.UUID("10000000-0000-0000-0000-000000000003")

def check_table_structure():
    """检查barometer_data表结构并返回列信息"""
    try:
        inspector = inspect(engine)
        if 'barometer_data' not in inspector.get_table_names():
            logger.error("barometer_data表不存在")
            return None
        
        columns = [col['name'] for col in inspector.get_columns('barometer_data')]
        logger.info(f"barometer_data表包含列: {', '.join(columns)}")
        return columns
    except Exception as e:
        logger.error(f"检查表结构失败: {e}")
        return None

def read_barometer_csv(file_path, sample_rate=10):
    """
    读取气压计CSV数据
    
    Args:
        file_path: CSV文件路径
        sample_rate: 采样率，用于生成时间戳
        
    Returns:
        pandas.DataFrame: 处理后的气压计数据
    """
    try:
        # 读取CSV文件
        df = pd.read_csv(file_path)
        logger.info(f"成功读取CSV文件，共{len(df)}条记录")
        
        # 检查必要的列是否存在
        required_columns = ['pressure', 'temperature']
        for col in required_columns:
            if col not in df.columns:
                logger.error(f"CSV文件缺少必要的列: {col}")
                # 如果列不存在，尝试使用示例数据创建
                if col == 'pressure':
                    df[col] = 1013.25 + np.random.normal(0, 1, len(df))  # 模拟气压数据
                elif col == 'temperature':
                    df[col] = 20 + np.random.normal(0, 5, len(df))  # 模拟温度数据
        
        # 如果没有timestamp列，生成时间戳
        if 'timestamp' not in df.columns:
            # 从当前时间开始，根据采样率生成时间戳
            start_time = datetime.now()
            timestamps = []
            for i in range(len(df)):
                delta = pd.Timedelta(seconds=i/sample_rate)
                timestamps.append(start_time + delta)
            df['timestamp'] = timestamps
            logger.info("生成了时间戳数据")
        else:
            # 将timestamp列转换为datetime格式
            try:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            except Exception:
                logger.warning("无法将timestamp列转换为datetime格式，重新生成时间戳")
                start_time = datetime.now()
                timestamps = []
                for i in range(len(df)):
                    delta = pd.Timedelta(seconds=i/sample_rate)
                    timestamps.append(start_time + delta)
                df['timestamp'] = timestamps
        
        # 添加source_id列（默认1）
        if 'source_id' not in df.columns:
            df['source_id'] = 1
        
        return df
    except Exception as e:
        logger.error(f"读取CSV文件失败: {e}")
        return None

def create_temp_table(conn):
    """创建临时表用于批量导入"""
    try:
        # 先删除可能存在的临时表
        conn.execute(text("DROP TABLE IF EXISTS barometer_data_temp"))
        
        # 创建临时表
        conn.execute(text("""
            CREATE TABLE barometer_data_temp (
                id VARCHAR(36),
                timestamp TIMESTAMP NOT NULL,
                source_id INTEGER NOT NULL,
                pressure DOUBLE PRECISION NOT NULL,
                temperature DOUBLE PRECISION NOT NULL,
                user_id VARCHAR(36),
                device_id VARCHAR(36),
                session_id VARCHAR(36)
            )
        """))
        logger.info("成功创建临时表")
    except Exception as e:
        logger.error(f"创建临时表失败: {e}")
        raise

def import_barometer_data():
    """导入气压计数据到数据库"""
    logger.info("===== 气压计数据导入开始 =====")
    
    # 检查环境变量和数据库连接
    logger.info(f"数据库连接: {DATABASE_URL}")
    logger.info(f"使用固定测试数据 - user_id: {TEST_USER_ID}, device_id: {TEST_DEVICE_ID}, session_id: {TEST_SESSION_ID}")
    
    # 检查barometer_data表结构
    columns = check_table_structure()
    if not columns:
        logger.error("表结构检查失败，无法继续导入")
        return
    
    # 从指定CSV文件读取数据
    csv_file_path = r"C:\Users\CJ\Documents\trae_projects\AISkiCoach\backend\app\algorithm\dataset\20250703-广融-baro\phone-barometer\_-2025-07-03_17-43-18\Barometer.csv"
    logger.info(f"正在从CSV文件读取数据: {csv_file_path}")
    
    barometer_df = read_barometer_csv(csv_file_path)
    if barometer_df is None or barometer_df.empty:
        logger.error("无法读取或处理CSV文件数据，导入失败")
        return
    
    # 清空表（可选）
    try:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM barometer_data"))
            conn.commit()
            logger.info("成功清空barometer_data表")
    except Exception as e:
        logger.warning(f"清空表失败: {e}")
    
    # 批量导入数据
    try:
        with engine.begin() as conn:
            # 创建临时表
            create_temp_table(conn)
            
            # 准备导入数据
            import_data = []
            for _, row in barometer_df.iterrows():
                import_data.append({
                    'id': str(uuid.uuid4()),
                    'timestamp': row['timestamp'],
                    'source_id': int(row['source_id']),
                    'pressure': float(row['pressure']),
                    'temperature': float(row['temperature']),
                    'user_id': str(TEST_USER_ID),
                    'device_id': str(TEST_DEVICE_ID),
                    'session_id': str(TEST_SESSION_ID)
                })
            
            # 使用copy_from批量导入到临时表
            if import_data:
                # 将数据转换为CSV格式
                import_df = pd.DataFrame(import_data)
                
                # 使用to_sql批量导入（对于大量数据更高效）
                import_df.to_sql(
                    'barometer_data_temp',
                    conn,
                    if_exists='append',
                    index=False,
                    chunksize=1000
                )
                
                logger.info(f"成功将{len(import_df)}条数据导入临时表")
                
                # 从临时表迁移到正式表
                # 首先检查是否有id列冲突的处理
                conn.execute(text("""
                    INSERT INTO barometer_data (id, timestamp, source_id, pressure, temperature, user_id, device_id, session_id)
                    SELECT id, timestamp, source_id, pressure, temperature, user_id, device_id, session_id
                    FROM barometer_data_temp
                """))
                
                logger.info("成功将数据从临时表迁移到正式表")
            
            # 验证导入
            result = conn.execute(text("SELECT COUNT(*) FROM barometer_data"))
            count = result.scalar()
            logger.info(f"barometer_data表中现在有{count}条记录")
            
            # 显示最近的几条记录
            result = conn.execute(text("SELECT id, timestamp, source_id, pressure, temperature FROM barometer_data ORDER BY timestamp DESC LIMIT 3"))
            recent_records = result.fetchall()
            print("\n最近导入的3条记录:")
            for record in recent_records:
                id_str = str(record[0])[:8]
                print(f"ID: {id_str}..., 时间: {record[1]}, 源ID: {record[2]}, 气压: {record[3]:.2f}, 温度: {record[4]:.2f}")
            
            # 清理临时表
            conn.execute(text("DROP TABLE IF EXISTS barometer_data_temp"))
            logger.info("临时表已清理")
            print("临时表已清理")
            
            print(f"\n✅ 导入完成！")
            
    except Exception as e:
        logger.error(f"导入过程出错: {e}")
        print(f"导入过程出错: {e}")
        traceback.print_exc()

def main():
    """主函数"""
    import_barometer_data()