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

# 数据库连接配置 - 使用阿里云数据库
POSTGRES_SERVER = os.getenv('POSTGRES_SERVER', 'pgm-wz973xmtl1oms94lso.pg.rds.aliyuncs.com')
POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'heygodata')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'heygo')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'HEYGOheygo2025')

# 构建数据库连接字符串
database_url = f'postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}'
engine = create_engine(database_url)

# 固定的用户、设备、会话ID
FIXED_USER_ID = "10000000-0000-0000-0000-000000000001"
FIXED_DEVICE_ID = "10000000-0000-0000-0000-000000000002"  
FIXED_SESSION_ID = "db9add3e-5ddd-4821-89f7-9078230550db"

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
                # 插入用户记录
                user_conn.execute(text("""
                    INSERT INTO users (id, created_at, updated_at, phone, nickname, level, total_skiing_days, total_skiing_hours, total_skiing_sessions, average_speed, is_active)
                    VALUES (:id, NOW(), NOW(), :phone, :nickname, :level, :total_skiing_days, :total_skiing_hours, :total_skiing_sessions, :average_speed, true)
                    ON CONFLICT (id) DO NOTHING
                """), {
                    'id': user_id,
                    'phone': f'138{datetime.now().strftime("%Y%m%d%H%M%S")}',
                    'nickname': '临时导入用户',
                    'level': 'Dexter',
                    'total_skiing_days': 0,
                    'total_skiing_hours': 0.0,
                    'total_skiing_sessions': 0,
                    'average_speed': 0.0
                })
                print(f"创建或使用用户记录: {user_id}")
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
                # 插入设备记录
                device_conn.execute(text("""
                    INSERT INTO devices (id, created_at, updated_at, device_id, device_name, device_type, connection_status)
                    VALUES (:id, NOW(), NOW(), :device_id, :device_name, :device_type, :connection_status)
                    ON CONFLICT (id) DO NOTHING
                """), {
                    'id': device_id,
                    'device_id': f'IMU{datetime.now().strftime("%Y%m%d%H%M%S")}',
                    'device_name': 'IMU导入设备',
                    'device_type': 'HeyGo A1',
                    'connection_status': 'disconnected'
                })
                print(f"创建或使用设备记录: {device_id}")
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
                # 插入会话记录
                session_conn.execute(text("""
                    INSERT INTO skiing_sessions (id, created_at, updated_at, session_name, session_status, user_id, start_time, end_time)
                    VALUES (:id, NOW(), NOW(), :session_name, :session_status, :user_id, NOW(), NOW())
                    ON CONFLICT (id) DO NOTHING
                """), {
                    'id': session_id,
                    'session_name': f'IMU导入会话_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
                    'session_status': 'active',
                    'user_id': user_id
                })
                print(f"创建或使用会话记录: {session_id}")
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

def import_imu_data(csv_file_path, session_id=None, device_id=None, user_id=None, batch_size=1000):
    """从CSV/TXT文件导入IMU数据到数据库，使用新的数据处理器和临时表方法
    
    Args:
        csv_file_path: CSV文件路径
        session_id: 滑雪会话ID（可选）
        device_id: 设备ID（可选）
        user_id: 用户ID（可选）
        batch_size: 批量插入大小，默认10000行
    """
    # 验证文件
    csv_path = Path(csv_file_path)
    if not csv_path.exists():
        print(f"错误：文件不存在: {csv_file_path}")
        return False
    
    print(f"开始导入IMU数据: {csv_file_path}")
    
    # 初始化数据处理器
    processor = IMUDataProcessor()
    
    try:
        # 使用新的数据处理器读取文件 - 优化内存使用
        print("使用高性能数据处理器读取文件...")
        
        # 检测文件类型并选择适当的读取方法
        file_extension = Path(csv_file_path).suffix.lower()
        
        if file_extension == '.txt' or file_extension == '.csv':
            # 使用WT IMU数据处理器 - 优化版本
            df = processor._read_wt_imu(csv_file_path)
        else:
            print(f"不支持的文件格式: {file_extension}")
            return False
        
        if df is None or len(df) == 0:
            print("读取的数据为空")
            return False
        
        # 筛选出指定设备的数据 - 使用内存优化的方式
        target_device = "WTB1"
        if 'device_name' in df.columns:
            # 使用query方法替代布尔索引，减少内存占用
            df = df.query(f"device_name == '{target_device}'", inplace=False)
            filtered_rows = len(df)
            if filtered_rows == 0:
                print(f"未找到设备名称为 '{target_device}' 的数据")
                return False
            print(f"筛选后保留 {filtered_rows} 行设备 '{target_device}' 的数据")
        else:
            print("警告：数据中未找到device_name列，无法进行设备筛选")
            return False
        
        # 重置索引，但不创建副本，节省内存
        df.reset_index(drop=True, inplace=True)
        total_rows = len(df)
        print(f"成功读取 {total_rows} 行数据")
        
        # 如果数据量很大，使用分批处理
        if total_rows > batch_size:
            print(f"数据量较大({total_rows}行)，将分{batch_size}行/批次处理")
            batches = (total_rows + batch_size - 1) // batch_size
        else:
            batches = 1
        
        # 使用事务性连接 - 确保自动管理事务
        with engine.begin() as conn:
            
            # 使用固定的会话ID，如果没有指定则使用默认值
            if session_id is None:
                session_id = FIXED_SESSION_ID
                print(f"使用固定滑雪会话: {session_id}")
            
            # 确保必需的用户和设备记录存在
            user_id, device_id = ensure_required_records(conn, session_id, device_id, user_id)
            
            # 1. 创建临时表 - 使用UNLOGGED表提高性能
            print("创建高性能临时表...")
            try:
                # 先删除临时表（如果存在）
                conn.execute(text("DROP TABLE IF EXISTS imu_data_temp"))
                
                # 创建普通临时表 - 提高兼容性
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
                
                # 为临时表创建索引以提高后续查询性能
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_imu_temp_timestamp ON imu_data_temp(timestamp)
                """))
                print("成功创建高性能UNLOGGED临时表")
            except Exception as e:
                print(f"创建临时表失败: {e}")
                raise
            
            # 2. 准备数据导入到临时表（支持分批处理）
            print("准备批量插入数据...")
            total_success_count = 0
            
            # 预获取所有需要的列信息
            numeric_columns = ['acc_x', 'acc_y', 'acc_z', 'gyro_x', 'gyro_y', 'gyro_z', 'mag_x', 'mag_y', 'mag_z']
            available_numeric_cols = [col for col in numeric_columns if col in df.columns]
            
            try:
                # 分批处理大数据集
                for batch_num in range(batches):
                    start_idx = batch_num * batch_size
                    end_idx = min((batch_num + 1) * batch_size, total_rows)
                    
                    if batches > 1:
                        print(f"处理第 {batch_num + 1}/{batches} 批次（行 {start_idx + 1}-{end_idx}）...")
                    
                    # 获取当前批次的数据
                    batch_df = df.iloc[start_idx:end_idx]
                    temp_records = []
                    batch_success_count = 0
                    
                    # 批量处理当前批次的数据 - 使用矢量化操作
                    try:
                        # 预筛选有效时间戳的行
                        valid_timestamp_mask = pd.notna(batch_df['timestamp'])
                        valid_batch = batch_df[valid_timestamp_mask].copy()
                        
                        if len(valid_batch) == 0:
                            print(f"批次 {batch_num + 1}: 无有效时间戳数据，跳过")
                            continue
                        
                        # 批量转换时间戳
                        if valid_batch['timestamp'].dtype != 'datetime64[ns]':
                            try:
                                valid_batch['timestamp'] = pd.to_datetime(valid_batch['timestamp'], errors='coerce')
                                # 再次筛选转换成功的行
                                valid_batch = valid_batch[pd.notna(valid_batch['timestamp'])]
                            except:
                                print(f"批次 {batch_num + 1}: 时间戳转换失败，跳过")
                                continue
                        
                        # 批量创建记录 - 使用pandas原生操作，避免Python循环
                        try:
                            # 预生成所有UUID
                            uuids = [uuid.uuid4() for _ in range(len(valid_batch))]
                            
                            # 使用pandas的to_dict方法直接转换为字典列表，避免逐行循环
                            temp_records = []
                            
                            # 批量获取设备ID映射
                            device_names = valid_batch['device_name'].fillna('unknown').tolist()
                            source_ids = [get_source_id(name) for name in device_names]
                            
                            # 批量处理时间戳
                            timestamps = valid_batch['timestamp'].dt.to_pydatetime().tolist()
                            
                            # 使用列表推导式批量创建记录，比for循环快很多
                            base_records = [
                                {
                                    'id': uuids[i],
                                    'timestamp': timestamps[i],
                                    'source_id': source_ids[i],
                                    'device_name': device_names[i]
                                }
                                for i in range(len(valid_batch))
                            ]
                            
                            # 批量处理数值列 - 使用pandas的矢量化操作，避免Python循环
                            for col in available_numeric_cols:
                                # 使用pandas的to_dict直接转换，避免逐行处理
                                if col in valid_batch.columns:
                                    # 将NaN转换为None，使用pandas的where操作
                                    col_series = valid_batch[col].where(pd.notna(valid_batch[col]), None)
                                    col_values = col_series.tolist()
                                    
                                    # 批量更新字典列表
                                    for i, value in enumerate(col_values):
                                        base_records[i][col] = float(value) if value is not None else None
                            
                            temp_records = base_records
                            batch_success_count = len(temp_records)
                            
                        except Exception as e:
                            print(f"批次 {batch_num + 1} 批量处理失败: {str(e)}")
                            # 回退到逐行处理
                            for idx, row in batch_df.iterrows():
                                try:
                                    temp_record = {
                                        'id': uuid.uuid4(),
                                        'timestamp': row.get('timestamp'),
                                        'source_id': get_source_id(row.get('device_name', 'unknown')),
                                        'device_name': row.get('device_name', 'unknown')
                                    }
                                    
                                    if pd.isna(temp_record['timestamp']):
                                        continue
                                    
                                    if not isinstance(temp_record['timestamp'], pd.Timestamp):
                                        try:
                                            temp_record['timestamp'] = pd.to_datetime(temp_record['timestamp'])
                                        except:
                                            continue
                                    
                                    temp_record['timestamp'] = temp_record['timestamp'].to_pydatetime()
                                    
                                    for col in available_numeric_cols:
                                        value = row.get(col)
                                        if pd.notna(value):
                                            temp_record[col] = float(value)
                                        else:
                                            temp_record[col] = None
                                    
                                    temp_records.append(temp_record)
                                    batch_success_count += 1
                                    
                                except Exception:
                                    continue
                    except Exception as e:
                        print(f"批次 {batch_num + 1} 处理失败: {str(e)}")
                        continue
                    
                    # 批量插入当前批次的数据 - 使用COPY语句提高性能
                    if temp_records:
                        # 使用COPY FROM STDIN替代executemany，大幅提升插入速度
                        import io
                        import csv
                        
                        # 构建CSV格式的数据
                        csv_buffer = io.StringIO()
                        csv_writer = csv.writer(csv_buffer)
                        
                        # 获取字段名 - 只执行一次
                        all_keys = sorted(temp_records[0].keys())
                        
                        # 写入数据行
                        for record in temp_records:
                            row = [record.get(key, None) for key in all_keys]
                            csv_writer.writerow(row)
                        
                        # 重置缓冲区位置
                        csv_buffer.seek(0)
                        
                        try:
                            # 使用COPY FROM STDIN进行高速批量插入
                            conn.connection.cursor().copy_from(
                                csv_buffer,
                                'imu_data_temp',
                                columns=all_keys,
                                sep=',',
                                null=''
                            )
                            
                            total_success_count += batch_success_count
                            print(f"批次 {batch_num + 1}: 成功高速批量插入 {len(temp_records)} 条记录到临时表")
                            
                        except Exception as copy_error:
                            # COPY失败时回退到传统批量插入
                            print(f"COPY插入失败，回退到传统批量插入: {copy_error}")
                            cols = ', '.join(all_keys)
                            placeholders = ', '.join(f":{k}" for k in all_keys)
                            query = text(f"INSERT INTO imu_data_temp ({cols}) VALUES ({placeholders})")
                            conn.execute(query, temp_records)
                            total_success_count += batch_success_count
                            print(f"批次 {batch_num + 1}: 成功批量插入 {len(temp_records)} 条记录到临时表")
                        
                        # 清理内存
                        del temp_records, csv_buffer
                        
                        # 清理内存
                        del temp_records, csv_buffer
                        
                print(f"总共成功处理 {total_success_count}/{total_rows} 行数据")
                
            except Exception as e:
                print(f"批量插入数据失败: {str(e)}")
                raise
            
            # 3. 将临时表数据迁移到主表
            print(f"临时表导入完成，成功导入 {total_success_count} 行数据")
            print("开始将数据从临时表迁移到imu_data主表...")
            
            try:
                # 预获取imu_data表结构信息 - 避免重复查询
                if not hasattr(import_imu_data, '_imu_columns_cache'):
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
                    import_imu_data._imu_columns_cache = [row[0] for row in result.fetchall()]
                
                imu_data_columns = import_imu_data._imu_columns_cache
                
                # 优化：批量迁移数据到主表
                # 预构建列映射，避免重复判断
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
                
                # 构建优化的批量迁移查询 - 使用UNLOGGED表和并行处理
                if insert_cols:
                    cols_str = ', '.join(insert_cols)
                    selects_str = ', '.join(select_clauses)
                    
                    # 使用UNLOGGED临时表和并行优化
                    migration_query = text(f"""
                        -- 设置会话级别的优化参数
                        SET LOCAL work_mem = '256MB';
                        SET LOCAL maintenance_work_mem = '512MB';
                        
                        -- 使用并行插入优化
                        INSERT INTO imu_data ({cols_str})
                        SELECT {selects_str}
                        FROM imu_data_temp temp
                        ORDER BY temp.timestamp
                    """)
                    
                    # 执行批量迁移
                    migration_result = conn.execute(migration_query)
                    
                    imported_count = migration_result.rowcount
                    print(f"成功批量迁移 {imported_count} 行数据到imu_data表")
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
                print(f"成功导入临时表: {total_success_count}")
                print(f"成功迁移到imu_data表: {final_count}")
                
                # 清理缓存
                if hasattr(import_imu_data, '_imu_columns_cache'):
                    delattr(import_imu_data, '_imu_columns_cache')
                
                return True
                
            except Exception as e:
                print(f"验证导入结果失败: {e}")
                # 清理缓存
                if hasattr(import_imu_data, '_imu_columns_cache'):
                    delattr(import_imu_data, '_imu_columns_cache')
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
        base_path = r"C:\Users\CJ\Documents\trae_projects\AISkiCoach\backend\app\algorithm\dataset\jason\imu"
        base_path = r"C:\Users\CJ\Documents\trae_projects\HEYGO-SKI\dataset\20251030\jason\imu"
        default_filename = "20251030183355--雪兔道滑了两段，中间上魔毯的时候也全程开着传感器。第一段是大角度的立刃转弯，中间摔了一次，第一趟的最后有10个滚刃。第二趟大湾的大角度刻滑，没摔，最后滚刃.txt"
        csv_file_path = os.path.join(base_path, default_filename)
        print(f"未指定CSV文件路径，使用默认路径: {csv_file_path}")
    
    import_imu_data(csv_file_path)

if __name__ == "__main__":
    main()