#!/usr/bin/env python3
import os
from sqlalchemy import create_engine, text
from datetime import datetime

# 获取数据库连接
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:changethis@localhost:5432/app')
engine = create_engine(DATABASE_URL)

print("=== 开始查询数据库中的IMU和气压计数据 ===")
print(f"数据库连接: {DATABASE_URL}")
print(f"查询时间: {datetime.now()}")
print()

try:
    with engine.connect() as conn:
        # === 查询IMU数据表 ===
        print("=== IMU数据表查询 ===")
        
        # 检查IMU数据表总记录数
        result = conn.execute(text('SELECT COUNT(*) as count FROM imu_data'))
        total_imu_count = result.fetchone()[0]
        print(f"IMU数据表总记录数: {total_imu_count}")
        
        if total_imu_count > 0:
            # 查看最近几条记录的结构和内容
            result = conn.execute(text('SELECT * FROM imu_data ORDER BY timestamp DESC LIMIT 3'))
            imu_headers = result.keys()
            print(f"IMU表列名: {list(imu_headers)}")
            
            imu_data = result.fetchall()
            print("最近3条IMU记录:")
            for i, row in enumerate(imu_data):
                print(f"{i+1}. {dict(zip(imu_headers, row))}")
        
        # 检查指定会话ID的IMU数据
        session_id = '10000000-0000-0000-0000-000000000003'
        result = conn.execute(text('SELECT COUNT(*) FROM imu_data WHERE session_id = :session_id'), {'session_id': session_id})
        session_imu_count = result.fetchone()[0]
        print(f"\n指定会话ID {session_id} 的IMU记录数: {session_imu_count}")
        
        if session_imu_count > 0:
            result = conn.execute(text('SELECT * FROM imu_data WHERE session_id = :session_id ORDER BY timestamp LIMIT 5'), {'session_id': session_id})
            session_imu_data = result.fetchall()
            print(f"该会话前5条IMU数据:")
            for i, row in enumerate(session_imu_data):
                print(f"  {i+1}. ID: {row[0]}, 时间: {row[1]}, 会话ID: {row[7]}")
        
        print("\n" + "="*60)

        # === 查询气压计数据表 ===
        print("=== 气压计数据表查询 ===")
        
        # 检查气压计数据表总记录数
        result = conn.execute(text('SELECT COUNT(*) as count FROM barometer_data'))
        total_baro_count = result.fetchone()[0]
        print(f"气压计数据表总记录数: {total_baro_count}")
        
        if total_baro_count > 0:
            # 查看最近几条记录的结构和内容
            result = conn.execute(text('SELECT * FROM barometer_data ORDER BY timestamp DESC LIMIT 3'))
            baro_headers = result.keys()
            print(f"气压计表列名: {list(baro_headers)}")
            
            baro_data = result.fetchall()
            print("最近3条气压计记录:")
            for i, row in enumerate(baro_data):
                print(f"{i+1}. {dict(zip(baro_headers, row))}")
        
        # 检查指定会话ID的气压计数据
        result = conn.execute(text('SELECT COUNT(*) FROM barometer_data WHERE session_id = :session_id'), {'session_id': session_id})
        session_baro_count = result.fetchone()[0]
        print(f"\n指定会话ID {session_id} 的气压计记录数: {session_baro_count}")
        
        if session_baro_count > 0:
            result = conn.execute(text('SELECT * FROM barometer_data WHERE session_id = :session_id ORDER BY timestamp LIMIT 5'), {'session_id': session_id})
            session_baro_data = result.fetchall()
            print(f"该会话前5条气压计数据:")
            for i, row in enumerate(session_baro_data):
                print(f"  {i+1}. ID: {row[0]}, 时间: {row[1]}, 气压: {row[3]}, 温度: {row[4]}, 会话ID: {row[7]}")

        print("\n" + "="*60)
        print("=== 数据查询完成 ===")
        
        # 汇总信息
        print(f"\n数据汇总:")
        print(f"- IMU数据总记录: {total_imu_count}")
        print(f"- 气压计数据总记录: {total_baro_count}")
        print(f"- 会话 {session_id} 的IMU记录: {session_imu_count}")
        print(f"- 会话 {session_id} 的气压计记录: {session_baro_count}")

except Exception as e:
    print(f"查询数据时出错: {e}")
    import traceback
    traceback.print_exc()