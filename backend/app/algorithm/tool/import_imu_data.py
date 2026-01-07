import csv
import os
import sys
from pathlib import Path
from datetime import datetime
import uuid
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

# 加载环境变量
load_dotenv()

# 数据库连接配置 - 支持DATABASE_URL或单独配置
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    engine = create_engine(DATABASE_URL)
else:
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    if not DB_PASSWORD:
        raise ValueError(
            "DB_PASSWORD environment variable is required. "
            "Set it in your environment or use DATABASE_URL instead."
        )
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'app')
    engine = create_engine(f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}')

# 固定的用户、设备、会话ID
FIXED_USER_ID = "47db736f-b22f-4998-9045-735c7579aaae"
FIXED_DEVICE_ID = "712ceb39-eb4a-44c0-b877-d0e6ac1c8099"  
FIXED_SESSION_ID = "82ed5810-409e-4a90-b7d0-537e18d80e34"

def get_source_id(device_name):
    """根据设备名称映射source_id
    
    Args:
        device_name (str): 设备名称
        
    Returns:
        int: 对应的source_id值
            雪板 -> 0
            left  -> 1  
            right -> 2
            其他   -> 0 (默认值)
    """
    if not device_name:
        return 0
    
    # device_name_lower = device_name.lower().strip()
    
    # 雪板相关映射到0 - 只要包含关键词就匹配
    if device_name in ['WTB1', 'board', 'WTB3']:
        return 0
    
    # left相关映射到1 - 只要包含关键词就匹配
    elif device_name in ['WTL1', 'left', 'WTL3']:
        return 1
    
    # right相关映射到2 - 只要包含关键词就匹配
    elif device_name in ['WTR1', 'right', 'WTR3']:
        return 2
    
    # 默认返回0
    else:
        return 0

def ensure_required_records(conn, session_id=None, device_id=None, user_id=None):
    """确保必要的外键记录存在"""
    # 使用固定ID
    if user_id is None:
        user_id = FIXED_USER_ID
    if device_id is None:
        device_id = FIXED_DEVICE_ID
    if session_id is None:
        session_id = FIXED_SESSION_ID
    
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
                        'device_id': f'IMU-{str(device_id)[:8].upper()}',
                        'device_name': 'IMU导入设备',
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
                        'session_name': f'IMU导入会话_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
                    })
                    print(f"创建会话记录: {session_id}")
                else:
                    print(f"会话记录已存在，直接使用: {session_id}")
    except Exception as e:
        print(f"创建会话记录失败: {e}")
    
    return user_id, device_id


class IMUDataProcessor:
    """IMU数据处理器"""
    
    def __init__(self):
        pass
    
    # --- 2. 私有读取器 (基于你提供的逻辑) --- 
    def _read_wt_imu(self, file_path):
        """读取WT公司IMU数据文件"""
        print(f"读取WT IMU文件: {file_path}")
        
        # 检测文件扩展名，选择合适的分隔符
        file_extension = Path(file_path).suffix.lower()
        if file_extension == '.txt':
            print("检测到TXT文件，使用制表符分隔符...")
            df = pd.read_csv(file_path, sep='\t', encoding='utf-8')
        else:
            print("检测到CSV文件，使用逗号分隔符...")
            df = pd.read_csv(file_path, sep=',', encoding='utf-8')
            
        print(f"原始 IMU 文件已读取: {len(df)} 行")

        # 定义英文字段和对应的中文字段
        en_selected_columns = ['time', 'DeviceName', 'AccX(g)', 'AccY(g)', 'AccZ(g)', 
                             'AsX(°/s)', 'AsY(°/s)', 'AsZ(°/s)', 'HX(uT)', 'HY(uT)', 'HZ(uT)']
        
        zh_selected_columns = ['时间', '设备名称', '加速度X(g)', '加速度Y(g)', '加速度Z(g)', 
                             '角速度X(°/s)', '角速度Y(°/s)', '角速度Z(°/s)', '磁场X(uT)', '磁场Y(uT)', '磁场Z(uT)']

        # 检测数据格式并提取列
        if all(col in df.columns for col in en_selected_columns):
            print("  > 检测到维特英文格式，正在提取列...")
            df = df[en_selected_columns].copy()
            
            # 重命名英文字段为中文
            df = df.rename(columns={
                'time': '时间',
                'DeviceName': '设备名称',
                'AccX(g)': '加速度X(g)',
                'AccY(g)': '加速度Y(g)',
                'AccZ(g)': '加速度Z(g)',
                'AsX(°/s)': '角速度X(°/s)',
                'AsY(°/s)': '角速度Y(°/s)',
                'AsZ(°/s)': '角速度Z(°/s)',
                'HX(uT)': '磁场X(uT)',
                'HY(uT)': '磁场Y(uT)',
                'HZ(uT)': '磁场Z(uT)'
            })
            
        elif all(col in df.columns for col in zh_selected_columns):
            print("  > 检测到维特中文格式，正在提取列...")
            df = df[zh_selected_columns].copy()
        else:
            print("  > 未检测到WT格式，尝试使用现有列名...")
            # 尝试映射常见的列名
            column_mapping = {}
            for col in df.columns:
                col_lower = col.lower()
                if 'time' in col_lower or '时间' in col:
                    column_mapping[col] = '时间'
                elif 'device' in col_lower or '设备' in col:
                    column_mapping[col] = '设备名称'
                elif 'acc' in col_lower and 'x' in col_lower:
                    column_mapping[col] = '加速度X(g)'
                elif 'acc' in col_lower and 'y' in col_lower:
                    column_mapping[col] = '加速度Y(g)'
                elif 'acc' in col_lower and 'z' in col_lower:
                    column_mapping[col] = '加速度Z(g)'
                elif ('gyro' in col_lower or '角速度' in col) and 'x' in col_lower:
                    column_mapping[col] = '角速度X(°/s)'
                elif ('gyro' in col_lower or '角速度' in col) and 'y' in col_lower:
                    column_mapping[col] = '角速度Y(°/s)'
                elif ('gyro' in col_lower or '角速度' in col) and 'z' in col_lower:
                    column_mapping[col] = '角速度Z(°/s)'
                elif ('mag' in col_lower or '磁场' in col) and 'x' in col_lower:
                    column_mapping[col] = '磁场X(uT)'
                elif ('mag' in col_lower or '磁场' in col) and 'y' in col_lower:
                    column_mapping[col] = '磁场Y(uT)'
                elif ('mag' in col_lower or '磁场' in col) and 'z' in col_lower:
                    column_mapping[col] = '磁场Z(uT)'
            
            if column_mapping:
                df = df.rename(columns=column_mapping)
                print(f"  > 成功映射 {len(column_mapping)} 个列名")
            else:
                print("  > 无法识别列名，保持原样")

        # --- 标准化 ---
        if '设备名称' in df.columns:
            df['设备名称'] = df['设备名称'].str.split('(', n=1).str[0]


        # --- 目标格式 ---
        column_mapping = {
            '时间': 'timestamp',
            '设备名称': 'device_name',
            '加速度X(g)': 'acc_x',
            '加速度Y(g)': 'acc_y',
            '加速度Z(g)': 'acc_z',
            '角速度X(°/s)': 'gyro_x',
            '角速度Y(°/s)': 'gyro_y',
            '角速度Z(°/s)': 'gyro_z',
            '磁场X(uT)': 'mag_x',
            '磁场Y(uT)': 'mag_y',
            '磁场Z(uT)': 'mag_z'
        }

        df = df.rename(columns=column_mapping)
      
        # --- 定义列的顺序 ---
        column_order = ['timestamp', 'datetime', 'device_name', 'gyro_x', 'gyro_y', 'gyro_z',
                       'mag_x', 'mag_y', 'mag_z', 'acc_x', 'acc_y', 'acc_z']
        
        # 确保所有列都存在，如果不存在则填充NaN
        for col in column_order:
            if col not in df.columns:
                df[col] = None
                
        df = df[column_order]

        print(f"WT IMU数据处理完成: {len(df)} 行")
        return df

def import_imu_data(csv_file_path, session_id=None, device_id=None, user_id=None):
    """从CSV/TXT文件导入IMU数据到数据库，使用新的数据处理器和临时表方法"""
    # 验证文件
    csv_path = Path(csv_file_path)
    if not csv_path.exists():
        print(f"错误：文件不存在: {csv_file_path}")
        return False
    
    print(f"开始导入IMU数据: {csv_file_path}")
    
    # 初始化数据处理器
    processor = IMUDataProcessor()
    
    try:
        # 使用新的数据处理器读取文件
        print("使用新的数据处理器读取文件...")
        
        # 检测文件类型并选择适当的读取方法
        file_extension = Path(csv_file_path).suffix.lower()
        
        if file_extension == '.txt' or file_extension == '.csv':
            # 使用WT IMU数据处理器
            df = processor._read_wt_imu(csv_file_path)
        else:
            print(f"不支持的文件格式: {file_extension}")
            return False
        
        if df is None or len(df) == 0:
            print("读取的数据为空")
            return False
            
        print(f"成功读取 {len(df)} 行数据")
        
        # 使用事务性连接 - 确保自动管理事务
        with engine.begin() as conn:
            
            # 使用固定的会话ID，如果没有指定则使用默认值
            if session_id is None:
                session_id = FIXED_SESSION_ID
                print(f"使用固定滑雪会话: {session_id}")
            
            # 确保必需的用户和设备记录存在
            user_id, device_id = ensure_required_records(conn, session_id, device_id, user_id)
            
            # 1. 创建临时表
            print("创建临时表...")
            try:
                # 先删除临时表（如果存在）
                conn.execute(text("DROP TABLE IF EXISTS imu_data_temp"))
                
                # 创建临时表
                conn.execute(text("""
                    CREATE TEMP TABLE imu_data_temp (
                        id UUID PRIMARY KEY,
                        timestamp TIMESTAMP NOT NULL,
                        source_id INTEGER,
                        device_name VARCHAR(100),
                        acc_x DOUBLE PRECISION,
                        acc_y DOUBLE PRECISION,
                        acc_z DOUBLE PRECISION,
                        gyro_x DOUBLE PRECISION,
                        gyro_y DOUBLE PRECISION,
                        gyro_z DOUBLE PRECISION,
                        mag_x DOUBLE PRECISION,
                        mag_y DOUBLE PRECISION,
                        mag_z DOUBLE PRECISION
                    )
                """))
                print("成功创建临时表")
            except Exception as e:
                print(f"创建临时表失败: {e}")
                raise
            
            # 2. 准备数据导入到临时表
            print("准备批量插入数据...")
            total_rows = len(df)
            success_count = 0
            
            try:
                # 批量处理数据
                temp_records = []
                
                for idx, row in df.iterrows():
                    try:
                        # 准备临时表记录
                        temp_record = {
                            'id': uuid.uuid4(),  # 为每行数据生成唯一ID
                            'timestamp': row.get('timestamp'),
                            'source_id': get_source_id(row.get('device_name', 'unknown')),  # 根据设备名称映射source_id
                            'device_name': row.get('device_name', 'unknown')
                        }
                        
                        # 确保timestamp不为空
                        if pd.isna(temp_record['timestamp']):
                            print(f"行 {idx} 时间戳为空，跳过此行")
                            continue
                        
                        # 确保timestamp是datetime类型
                        if not isinstance(temp_record['timestamp'], pd.Timestamp):
                            try:
                                temp_record['timestamp'] = pd.to_datetime(temp_record['timestamp'])
                            except:
                                print(f"行 {idx} 时间戳格式错误，跳过此行")
                                continue
                        
                        # 转换pandas时间戳为Python datetime
                        temp_record['timestamp'] = temp_record['timestamp'].to_pydatetime()
                        
                        # 获取数值数据，处理NaN值
                        numeric_columns = ['acc_x', 'acc_y', 'acc_z', 'gyro_x', 'gyro_y', 'gyro_z', 'mag_x', 'mag_y', 'mag_z']
                        for col in numeric_columns:
                            if col in df.columns:
                                value = row.get(col)
                                if pd.notna(value):
                                    temp_record[col] = float(value)
                                else:
                                    temp_record[col] = None
                        
                        temp_records.append(temp_record)
                        success_count += 1
                        
                    except Exception as e:
                        print(f"处理行 {idx} 失败: {str(e)}")
                        continue
                
                # 批量插入数据
                if temp_records:
                    print(f"准备插入 {len(temp_records)} 条记录到临时表...")
                    
                    # 构建批量插入查询
                    all_keys = set()
                    for record in temp_records:
                        all_keys.update(record.keys())
                    
                    cols = ', '.join(sorted(all_keys))
                    placeholders = ', '.join(f":{k}" for k in sorted(all_keys))
                    
                    query = text(f"INSERT INTO imu_data_temp ({cols}) VALUES ({placeholders})")
                    
                    # 批量执行插入
                    for record in temp_records:
                        # 确保所有字段都存在
                        complete_record = {k: record.get(k) for k in sorted(all_keys)}
                        conn.execute(query, complete_record)
                    
                    print(f"成功插入 {success_count} 条记录到临时表")
                
            except Exception as e:
                print(f"批量插入数据失败: {str(e)}")
                raise
            
            # 3. 将临时表数据迁移到主表
            print(f"临时表导入完成，成功导入 {success_count} 行数据")
            print("开始将数据从临时表迁移到imu_data主表...")
            
            try:
                # 检查imu_data表是否存在
                table_exists = conn.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE  table_schema = 'public'
                        AND    table_name   = 'imu_data'
                    )
                """)).scalar()
                
                if not table_exists:
                    print("错误：数据库中不存在imu_data表")
                    return False
                
                # 获取imu_data表的列信息
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'imu_data'
                """))
                imu_data_columns = [row[0] for row in result.fetchall()]
                
                # 构建INSERT INTO SELECT语句
                insert_cols = []
                select_clauses = []
                
                # 必需的外键字段
                if 'user_id' in imu_data_columns:
                    insert_cols.append('user_id')
                    select_clauses.append(f"'{user_id}'")
                if 'device_id' in imu_data_columns:
                    insert_cols.append('device_id')
                    select_clauses.append(f"'{device_id}'")
                if 'session_id' in imu_data_columns:
                    insert_cols.append('session_id')
                    select_clauses.append(f"'{session_id}'")
                
                # 从临时表映射的字段
                column_mapping = {
                    'id': 'id',
                    'timestamp': 'timestamp',
                    'source_id': 'source_id',
                    'acc_x': 'acc_x',
                    'acc_y': 'acc_y',
                    'acc_z': 'acc_z',
                    'gyro_x': 'gyro_x',
                    'gyro_y': 'gyro_y',
                    'gyro_z': 'gyro_z',
                    'mag_x': 'mag_x',
                    'mag_y': 'mag_y',
                    'mag_z': 'mag_z'
                }
                
                for temp_col, main_col in column_mapping.items():
                    if main_col in imu_data_columns:
                        insert_cols.append(main_col)
                        select_clauses.append(f'temp.{temp_col}')
                
                # 构建查询
                if insert_cols:
                    cols_str = ', '.join(insert_cols)
                    selects_str = ', '.join(select_clauses)
                    
                    migration_query = text(f"""
                        INSERT INTO imu_data ({cols_str})
                        SELECT {selects_str}
                        FROM imu_data_temp temp
                    """)
                    
                    # 执行迁移
                    migration_result = conn.execute(migration_query)
                    
                    imported_count = migration_result.rowcount
                    print(f"成功将 {imported_count} 行数据迁移到imu_data表")
                else:
                    print("错误：找不到可迁移的列")
                    
            except SQLAlchemyError as e:
                print(f"数据迁移失败: {str(e)}")
                raise
            
            # 4. 清理临时表（会话结束时自动清理）
            print("清理临时表...")
            conn.execute(text("DROP TABLE IF EXISTS imu_data_temp"))
            
            # 5. 验证导入结果
            try:
                verify_result = conn.execute(text("""
                    SELECT COUNT(*) FROM imu_data 
                    WHERE session_id = :session_id
                """), {'session_id': session_id})
                
                final_count = verify_result.scalar()
                print(f"\n导入完成！")
                print(f"总处理行: {total_rows}")
                print(f"成功导入临时表: {success_count}")
                print(f"成功迁移到imu_data表: {final_count}")
                
                return True
                
            except Exception as e:
                print(f"验证导入结果失败: {e}")
                return False
                
    except Exception as e:
        print(f"导入过程发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数，用于直接运行脚本"""
    # 支持命令行参数指定CSV文件路径
    if len(sys.argv) > 1:
        csv_file_path = sys.argv[1]
    else:
        # 默认CSV文件路径 - 使用原始字符串处理包含特殊字符的路径
        base_path = "../dataset/jason/imu"
        default_filename = "20251030183355--雪兔道滑了两段，中间上魔毯的时候也全程开着传感器。第一段是大角度的立刃转弯，中间摔了一次，第一趟的最后有10个滚刃。第二趟大湾的大角度刻滑，没摔，最后滚刃.txt"
        csv_file_path = os.path.join(base_path, default_filename)
        print(f"未指定CSV文件路径，使用默认路径: {csv_file_path}")
    
    import_imu_data(csv_file_path)

if __name__ == "__main__":
    main()