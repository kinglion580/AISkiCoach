import csv
import os
import sys
from pathlib import Path
from datetime import datetime
import uuid
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
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'changethis')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'app')
    engine = create_engine(f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}')

def generate_random_uuid():
    """生成随机UUID"""
    return str(uuid.uuid4())

def ensure_required_records(conn, session_id):
    """确保必要的外键记录存在"""
    user_id = generate_random_uuid()
    device_id = generate_random_uuid()
    
    # 尝试创建用户记录（如果表存在）
    try:
        # 检查users表是否存在
        user_table_exists = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE  table_schema = 'public'
                AND    table_name   = 'users'
            )
        """)).scalar()
        
        if user_table_exists:
            # 插入用户记录
            conn.execute(text("""
                INSERT INTO users (id, created_at, updated_at, email, password_hash, name, is_active)
                VALUES (:id, NOW(), NOW(), :email, :password_hash, :name, true)
                ON CONFLICT (id) DO NOTHING
            """), {
                'id': user_id,
                'email': f'temp_user_{datetime.now().strftime("%Y%m%d%H%M%S")}@example.com',
                'password_hash': 'temp_password_hash',
                'name': '临时导入用户'
            })
            print(f"创建或使用用户记录: {user_id}")
    except Exception as e:
        print(f"创建用户记录失败: {e}")
    
    # 尝试创建设备记录（如果表存在）
    try:
        # 检查devices表是否存在
        device_table_exists = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE  table_schema = 'public'
                AND    table_name   = 'devices'
            )
        """)).scalar()
        
        if device_table_exists:
            # 插入设备记录
            conn.execute(text("""
                INSERT INTO devices (id, created_at, updated_at, name, device_type, user_id)
                VALUES (:id, NOW(), NOW(), :name, :device_type, :user_id)
                ON CONFLICT (id) DO NOTHING
            """), {
                'id': device_id,
                'name': 'IMU导入设备',
                'device_type': 'imu',
                'user_id': user_id
            })
            print(f"创建或使用设备记录: {device_id}")
    except Exception as e:
        print(f"创建设备记录失败: {e}")
    
    # 尝试创建滑雪会话记录（如果表存在）
    try:
        # 检查skiing_sessions表是否存在
        session_table_exists = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE  table_schema = 'public'
                AND    table_name   = 'skiing_sessions'
            )
        """)).scalar()
        
        if session_table_exists:
            # 插入会话记录
            conn.execute(text("""
                INSERT INTO skiing_sessions (id, created_at, updated_at, user_id, start_time, end_time)
                VALUES (:id, NOW(), NOW(), :user_id, NOW(), NOW())
                ON CONFLICT (id) DO NOTHING
            """), {
                'id': session_id,
                'user_id': user_id
            })
            print(f"创建或使用会话记录: {session_id}")
    except Exception as e:
        print(f"创建会话记录失败: {e}")
    
    return user_id, device_id

def import_imu_data(csv_file_path):
    """从CSV文件导入IMU数据到数据库，使用临时表方法避免外键约束问题"""
    print(f"开始导入IMU数据...")
    
    # 读取CSV文件
    csv_path = Path(csv_file_path)
    if not csv_path.exists():
        print(f"错误：找不到文件 {csv_file_path}")
        return
    
    # 创建统一的会话ID
    session_id = generate_random_uuid()
    print(f"使用统一会话ID: {session_id}")
    
    try:
        with engine.begin() as conn:
            # 确保必要的外键记录存在
            user_id, device_id = ensure_required_records(conn, session_id)
            
            # 1. 创建临时表
            print("创建临时表...")
            conn.execute(text("""
                DROP TABLE IF EXISTS imu_data_temp;
                CREATE TABLE imu_data_temp (
                    id VARCHAR(36) PRIMARY KEY,
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
            
            # 准备数据导入到临时表
            total_rows = 0
            success_count = 0
            errors = 0
            
            with open(csv_file_path, mode='r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                for row in reader:
                    total_rows += 1
                    
                    try:
                        # 准备临时表记录
                        temp_record = {
                            'id': generate_random_uuid(),
                            'timestamp': None,
                            'source_id': 1,  # 数据库表要求integer类型
                            'device_name': row.get('设备名称', 'unknown')
                        }
                        
                        # 修复时间戳解析格式 - 处理没有前导零的情况和毫秒格式
                        timestamp_str = row.get('timestamp', row.get('时间戳', ''))
                        try:
                            # 尝试解析带毫秒的格式
                            if ':' in timestamp_str.split('.')[-1] or len(timestamp_str.split(':')) > 3:
                                # 处理格式: '2025-7-3 17:44:17:747'
                                parts = timestamp_str.split(' ')
                                date_parts = parts[0].split('-')
                                time_parts = parts[1].split(':')
                                
                                # 添加前导零
                                year = int(date_parts[0])
                                month = int(date_parts[1])
                                day = int(date_parts[2])
                                hour = int(time_parts[0])
                                minute = int(time_parts[1])
                                second = int(time_parts[2])
                                microsecond = int(time_parts[3]) * 1000  # 毫秒转微秒
                                
                                temp_record['timestamp'] = datetime(year, month, day, hour, minute, second, microsecond)
                            elif '.' in timestamp_str:
                                temp_record['timestamp'] = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S.%f')
                            else:
                                temp_record['timestamp'] = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                        except Exception as e:
                            print(f"时间戳解析失败: {timestamp_str}, 错误: {e}")
                            # 使用当前时间作为备用
                            temp_record['timestamp'] = datetime.utcnow()
                        
                        # 尝试获取加速度数据（支持多种列名格式）
                        try:
                            if 'imu_acc_x' in row and row['imu_acc_x']:
                                temp_record["acc_x"] = float(row['imu_acc_x'])
                                temp_record["acc_y"] = float(row['imu_acc_y'])
                                temp_record["acc_z"] = float(row['imu_acc_z'])
                            elif '加速度_x' in row and row['加速度_x']:
                                temp_record["acc_x"] = float(row['加速度_x'])
                                temp_record["acc_y"] = float(row['加速度_y'])
                                temp_record["acc_z"] = float(row['加速度_z'])
                            else:
                                print(f"行 {total_rows} 缺少加速度数据")
                                continue  # 跳过这一行
                        except ValueError:
                            print(f"行 {total_rows} 加速度数据格式错误")
                            continue  # 跳过这一行
                        
                        # 尝试获取角速度数据（支持多种列名格式）
                        try:
                            if 'imu_gyro_x' in row and row['imu_gyro_x']:
                                temp_record["gyro_x"] = float(row['imu_gyro_x'])
                                temp_record["gyro_y"] = float(row['imu_gyro_y'])
                                temp_record["gyro_z"] = float(row['imu_gyro_z'])
                            elif '角速度_x' in row and row['角速度_x']:
                                temp_record["gyro_x"] = float(row['角速度_x'])
                                temp_record["gyro_y"] = float(row['角速度_y'])
                                temp_record["gyro_z"] = float(row['角速度_z'])
                            else:
                                print(f"行 {total_rows} 缺少角速度数据")
                                continue  # 跳过这一行
                        except ValueError:
                            print(f"行 {total_rows} 角速度数据格式错误")
                            continue  # 跳过这一行
                        
                        # 处理可能为空的磁力计数据
                        try:
                            if ('imu_mag_x' in row and row['imu_mag_x']) or ('磁力计_x' in row and row['磁力计_x']):
                                if 'imu_mag_x' in row and row['imu_mag_x']:
                                    temp_record["mag_x"] = float(row['imu_mag_x'])
                                    temp_record["mag_y"] = float(row['imu_mag_y'])
                                    temp_record["mag_z"] = float(row['imu_mag_z'])
                                else:
                                    temp_record["mag_x"] = float(row['磁力计_x'])
                                    temp_record["mag_y"] = float(row['磁力计_y'])
                                    temp_record["mag_z"] = float(row['磁力计_z'])
                        except ValueError:
                            print(f"行 {total_rows} 磁力计数据格式错误，忽略磁力计数据")
                        
                        # 插入临时表
                        cols = ', '.join(k for k, v in temp_record.items() if v is not None)
                        placeholders = ', '.join(f":{k}" for k, v in temp_record.items() if v is not None)
                        params = {k: v for k, v in temp_record.items() if v is not None}
                        
                        query = text(f"INSERT INTO imu_data_temp ({cols}) VALUES ({placeholders})")
                        conn.execute(query, params)
                        
                        success_count += 1
                        
                        # 打印进度
                        if total_rows % 1000 == 0:
                            print(f"已处理 {total_rows} 行数据")
                            
                    except Exception as e:
                        errors += 1
                        # 仅在遇到较多错误时打印
                        if errors <= 10 or errors % 100 == 0:
                            print(f"处理行 {total_rows} 失败: {str(e)[:100]}...")
                        continue
            
            # 2. 将临时表数据迁移到主表
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
                    return
                
                # 获取imu_data表的列信息
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'imu_data'
                """))
                imu_data_columns = [row[0] for row in result.fetchall()]
                
                # 构建INSERT INTO SELECT语句
                # 确保只插入存在的列
                insert_cols = []
                select_clauses = []
                query_params = {}
                
                # 必需的外键字段
                if 'user_id' in imu_data_columns:
                    insert_cols.append('user_id')
                    select_clauses.append(f"'{user_id}'::uuid")
                if 'device_id' in imu_data_columns:
                    insert_cols.append('device_id')
                    select_clauses.append(f"'{device_id}'::uuid")
                if 'session_id' in imu_data_columns:
                    insert_cols.append('session_id')
                    select_clauses.append(f"'{session_id}'::uuid")
                
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
            
            # 3. 清理临时表
            print("清理临时表...")
            conn.execute(text("DROP TABLE IF EXISTS imu_data_temp"))
            
            # 4. 验证导入结果
            verify_result = conn.execute(text("""
                SELECT COUNT(*) FROM imu_data 
                WHERE session_id = :session_id
            """), {'session_id': session_id})
            
            final_count = verify_result.scalar()
            print(f"\n导入完成！")
            print(f"总处理行: {total_rows}")
            print(f"成功导入临时表: {success_count}")
            print(f"成功迁移到imu_data表: {final_count}")
                
    except Exception as e:
        print(f"导入过程发生错误: {str(e)}")
        return

def main():
    """主函数，用于直接运行脚本"""
    # 支持命令行参数指定CSV文件路径
    if len(sys.argv) > 1:
        csv_file_path = sys.argv[1]
    else:
        # 默认CSV文件路径
        csv_file_path = "C:/Users/CJ/Documents/trae_projects/AISkiCoach/backend/app/algorithm/dataset/20250703174417-sturn.csv"
        print(f"未指定CSV文件路径，使用默认路径: {csv_file_path}")
    
    import_imu_data(csv_file_path)

if __name__ == "__main__":
    main()