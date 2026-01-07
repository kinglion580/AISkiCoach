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
TEST_USER_ID = uuid.UUID("47db736f-b22f-4998-9045-735c7579aaae")
TEST_DEVICE_ID = uuid.UUID("712ceb39-eb4a-44c0-b877-d0e6ac1c8099")
TEST_SESSION_ID = uuid.UUID("82ed5810-409e-4a90-b7d0-537e18d80e34")

def ensure_required_records(conn, session_id=None, device_id=None, user_id=None):
    """确保必要的外键记录存在"""
    # 使用固定ID
    if user_id is None:
        user_id = TEST_USER_ID
    if device_id is None:
        device_id = TEST_DEVICE_ID
    if session_id is None:
        session_id = TEST_SESSION_ID
    
    # 每个表操作使用独立事务，避免一个失败影响其他操作
    # 1. 创建用户记录（如果表存在）
    try:
        with engine.begin() as user_conn:
            # 检查users表是否存在
            user_table_exists = user_conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE  table_schema = 'public'
                    AND    table_name   = 'users'
                )
            """)).scalar()
            
            if user_table_exists:
                # 检查用户记录是否已存在
                user_exists = user_conn.execute(text("""
                    SELECT EXISTS (SELECT 1 FROM users WHERE id = :id)
                """), {'id': user_id}).scalar()
                
                if not user_exists:
                    # 插入用户记录 - 使用phone字段，没有email和password_hash
                    user_conn.execute(text("""
                        INSERT INTO users (id, created_at, updated_at, phone, nickname, is_active, level)
                        VALUES (:id, NOW(), NOW(), :phone, :nickname, true, 'Dexter')
                    """), {
                        'id': user_id,
                        'phone': f'1380000{datetime.now().strftime("%H%M%S")}',
                        'nickname': '临时导入用户'
                    })
                    print(f"创建用户记录: {user_id}")
                else:
                    print(f"用户记录已存在，直接使用: {user_id}")
    except Exception as e:
        print(f"创建用户记录失败: {e}")
    
    # 2. 创建设备记录（如果表存在）
    try:
        with engine.begin() as device_conn:
            # 检查devices表是否存在
            device_table_exists = device_conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE  table_schema = 'public'
                    AND    table_name   = 'devices'
                )
            """)).scalar()
            
            if device_table_exists:
                # 检查设备记录是否已存在
                device_exists = device_conn.execute(text("""
                    SELECT EXISTS (SELECT 1 FROM devices WHERE id = :id)
                """), {'id': device_id}).scalar()
                
                if not device_exists:
                    # 插入设备记录 - 使用device_name和device_id字段，没有user_id（通过user_devices表关联）
                    device_conn.execute(text("""
                        INSERT INTO devices (id, created_at, updated_at, device_id, device_name, device_type, connection_status)
                        VALUES (:id, NOW(), NOW(), :device_id, :device_name, :device_type, 'connected')
                    """), {
                        'id': device_id,
                        'device_id': f'BARO-{str(device_id)[:8].upper()}',
                        'device_name': '气压计导入设备',
                        'device_type': 'HeyGo A1'
                    })
                    print(f"创建设备记录: {device_id}")
                else:
                    print(f"设备记录已存在，直接使用: {device_id}")
                
                # 创建用户设备关联记录
                try:
                    # 检查是否已存在关联
                    exists = device_conn.execute(text("""
                        SELECT EXISTS (
                            SELECT 1 FROM user_devices 
                            WHERE user_id = :user_id AND device_id = :device_id
                        )
                    """), {
                        'user_id': user_id,
                        'device_id': device_id
                    }).scalar()
                    
                    if not exists:
                        device_conn.execute(text("""
                            INSERT INTO user_devices (id, user_id, device_id, is_primary, created_at)
                            VALUES (gen_random_uuid(), :user_id, :device_id, true, NOW())
                        """), {
                            'user_id': user_id,
                            'device_id': device_id
                        })
                        print(f"创建用户设备关联记录")
                    else:
                        print(f"用户设备关联记录已存在")
                except Exception as e:
                    print(f"创建用户设备关联记录失败: {e}")
    except Exception as e:
        print(f"创建设备记录失败: {e}")
    
    # 3. 创建滑雪会话记录（如果表存在）
    try:
        with engine.begin() as session_conn:
            # 检查skiing_sessions表是否存在
            session_table_exists = session_conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE  table_schema = 'public'
                    AND    table_name   = 'skiing_sessions'
                )
            """)).scalar()
            
            if session_table_exists:
                # 检查会话记录是否已存在
                session_exists = session_conn.execute(text("""
                    SELECT EXISTS (SELECT 1 FROM skiing_sessions WHERE id = :id)
                """), {'id': session_id}).scalar()
                
                if not session_exists:
                    # 插入会话记录 - 需要session_name字段（NOT NULL）
                    session_conn.execute(text("""
                        INSERT INTO skiing_sessions (id, created_at, updated_at, user_id, device_id, session_name, session_status, start_time, end_time)
                        VALUES (:id, NOW(), NOW(), :user_id, :device_id, :session_name, 'active', NOW(), NOW())
                    """), {
                        'id': session_id,
                        'user_id': user_id,
                        'device_id': device_id,
                        'session_name': f'气压计导入会话_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
                    })
                    print(f"创建会话记录: {session_id}")
                else:
                    print(f"会话记录已存在，直接使用: {session_id}")
    except Exception as e:
        print(f"创建会话记录失败: {e}")
    
    return user_id, device_id

def check_table_structure():
    """检查barometer_data表结构并返回列信息"""
    try:
        inspector = inspect(engine)
        if 'barometer_data' not in inspector.get_table_names():
            print("barometer_data表不存在")
            return None
        
        columns = [col['name'] for col in inspector.get_columns('barometer_data')]
        print(f"barometer_data表包含列: {', '.join(columns)}")
        return columns
    except Exception as e:
        print(f"检查表结构失败: {e}")
        return None


def convert_timestamp_to_datetime(time_ns):
    """Convert nanosecond timestamp to datetime object"""
    time_ms = int(time_ns // 1_000_000)
    return datetime.fromtimestamp(time_ms / 1000.0)

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
        print(f"成功读取CSV文件，共{len(df)}条记录")
        
        # Log column names
        print(f"Columns in file: {list(df.columns)}")
        
        # Print the first few rows for verification
        print("\nFirst 5 rows of data:")
        for i in range(min(5, len(df))):
            print(f"Row {i}: {dict(df.iloc[i])}")
        
        # 检查必要的列是否存在 - pressure必须有，temperature允许缺失但会用固定值-6
        required_columns = ['pressure']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"CSV文件缺少必要的列: {', '.join(missing_columns)}")
            return None
        
        # 检查pressure数据是否为空
        if df['pressure'].isna().all():
            print("CSV文件中pressure列的所有数据都为空")
            return None
        
        # temperature列处理：允许缺失但需要用固定值-6
        if 'temperature' not in df.columns:
            logger.warning("CSV文件中没有temperature列，将使用固定值-6")
            df['temperature'] = -6.0
        
        # 检查时间列是否存在，必须有时间数据
        if 'time' not in df.columns:
            print("CSV文件缺少必要的列: time")
            return None
        
        # 所有时间戳都转为毫秒级 - 只处理真实的时间数据
        df['timestamp'] = pd.to_numeric(df['time']).apply(convert_timestamp_to_datetime)
        print("Time conversion completed")
        print(f"Time range: {df['timestamp'].min()} - {df['timestamp'].max()}")
        
        # 验证时间戳有效性
        if df['timestamp'].isna().any():
            print("时间戳转换后存在无效数据")
            return None
        
        # 添加source_id列（默认1）
        if 'source_id' not in df.columns:
            df['source_id'] = 1
        
        return df
    except Exception as e:
        print(f"读取CSV文件失败: {e}")
        return None

def create_temp_table(conn):
    """创建临时表用于批量导入"""
    try:
        # 先删除可能存在的临时表
        conn.execute(text("DROP TABLE IF EXISTS barometer_data_temp"))
        
        # 创建临时表 - 使用UUID类型匹配原始表
        conn.execute(text("""
            CREATE TABLE barometer_data_temp (
                id UUID,
                timestamp TIMESTAMP NOT NULL,
                source_id INTEGER NOT NULL,
                pressure DOUBLE PRECISION NOT NULL,
                temperature DOUBLE PRECISION NOT NULL,
                user_id UUID,
                device_id UUID,
                session_id UUID
            )
        """))
        print("成功创建临时表")
    except Exception as e:
        print(f"创建临时表失败: {e}")
        raise

def import_barometer_data():
    """导入气压计数据到数据库"""
    print("===== 气压计数据导入开始 =====")
    
    # 检查环境变量和数据库连接
    print(f"数据库连接: {DATABASE_URL}")
    print(f"使用固定测试数据 - user_id: {TEST_USER_ID}, device_id: {TEST_DEVICE_ID}, session_id: {TEST_SESSION_ID}")
    
    # 检查barometer_data表结构
    columns = check_table_structure()
    if not columns:
        print("表结构检查失败，无法继续导入")
        return
    
    # 从指定CSV文件读取数据
    csv_file_path = r"../dataset/jason/baro/2025-10-30_10-34-08/Barometer.csv"
    print(f"正在从CSV文件读取数据: {csv_file_path}")
    
    barometer_df = read_barometer_csv(csv_file_path)
    if barometer_df is None or barometer_df.empty:
        print("无法读取或处理CSV文件数据，导入失败")
        return
    
    # 清空表（可选）
    try:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM barometer_data"))
            conn.commit()
            print("成功清空barometer_data表")
    except Exception as e:
        logger.warning(f"清空表失败: {e}")
    
    # 批量导入数据
    try:
        with engine.begin() as conn:
            # 确保必要的外键记录存在
            ensure_required_records(conn, TEST_SESSION_ID, TEST_DEVICE_ID, TEST_USER_ID)
            
            # 创建临时表
            create_temp_table(conn)
            
            # 准备导入数据
            import_data = []
            for _, row in barometer_df.iterrows():
                import_data.append({
                    'id': uuid.uuid4(),
                    'timestamp': row['timestamp'],
                    'source_id': int(row['source_id']),
                    'pressure': float(row['pressure']),
                    'temperature': float(row['temperature']),
                    'user_id': TEST_USER_ID,
                    'device_id': TEST_DEVICE_ID,
                    'session_id': TEST_SESSION_ID
                })
            
            # 使用直接SQL插入避免列名冲突
            if import_data:
                # 批量插入数据，避免pandas to_sql的列名冲突问题
                batch_size = 1000
                inserted_count = 0
                
                for i in range(0, len(import_data), batch_size):
                    batch = import_data[i:i + batch_size]
                    
                    # 构建批量插入的SQL语句
                    placeholders = ','.join([
                        '(:id_{}, :timestamp_{}, :source_id_{}, :pressure_{}, :temperature_{}, :user_id_{}, :device_id_{}, :session_id_{})'.format(
                            j, j, j, j, j, j, j, j) 
                        for j in range(len(batch))
                    ])
                    
                    sql = f"""
                        INSERT INTO barometer_data_temp (id, timestamp, source_id, pressure, temperature, user_id, device_id, session_id)
                        VALUES {placeholders}
                    """
                    
                    # 构建参数字典
                    params = {}
                    for j, row in enumerate(batch):
                        params.update({
                            f'id_{j}': row['id'],
                            f'timestamp_{j}': row['timestamp'],
                            f'source_id_{j}': row['source_id'],
                            f'pressure_{j}': row['pressure'],
                            f'temperature_{j}': row['temperature'],
                            f'user_id_{j}': row['user_id'],
                            f'device_id_{j}': row['device_id'],
                            f'session_id_{j}': row['session_id']
                        })
                    
                    # 执行批量插入
                    conn.execute(text(sql), params)
                    inserted_count += len(batch)
                
                print(f"成功将{inserted_count}条数据导入临时表")
                
                # 从临时表迁移到正式表
                # 首先检查是否有id列冲突的处理
                conn.execute(text("""
                    INSERT INTO barometer_data (id, timestamp, source_id, pressure, temperature, user_id, device_id, session_id)
                    SELECT id, timestamp, source_id, pressure, temperature, user_id, device_id, session_id
                    FROM barometer_data_temp
                """))
                
                print("成功将数据从临时表迁移到正式表")
            
            # 验证导入
            result = conn.execute(text("SELECT COUNT(*) FROM barometer_data"))
            count = result.scalar()
            print(f"barometer_data表中现在有{count}条记录")
            
            # 显示最近的几条记录
            result = conn.execute(text("SELECT id, timestamp, source_id, pressure, temperature FROM barometer_data ORDER BY timestamp DESC LIMIT 3"))
            recent_records = result.fetchall()
            print("\n最近导入的3条记录:")
            for record in recent_records:
                id_str = str(record[0])[:8]
                print(f"ID: {id_str}..., 时间: {record[1]}, 源ID: {record[2]}, 气压: {record[3]:.2f}, 温度: {record[4]:.2f}")
            
            # 清理临时表
            conn.execute(text("DROP TABLE IF EXISTS barometer_data_temp"))
            print("临时表已清理")
            print("临时表已清理")
            
            print(f"\n✅ 导入完成！")
            
    except Exception as e:
        print(f"导入过程出错: {e}")
        print(f"导入过程出错: {e}")
        traceback.print_exc()

def main():
    """主函数"""
    import_barometer_data()

if __name__ == "__main__":
    main()