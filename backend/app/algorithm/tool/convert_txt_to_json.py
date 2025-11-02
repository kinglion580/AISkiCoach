import json
import os
import datetime
import time

# 输入文件路径
input_file = 'backend/app/algorithm/other/20250927152940.txt'
# 输出JSON文件路径
output_file = 'backend/app/algorithm/other/calibration_data_new.json'

# 检查输入文件是否存在
if not os.path.exists(input_file):
    print(f"错误：找不到输入文件 {input_file}")
    exit(1)

# 初始化数据列表
data_list = []
device_id = None
first_timestamp = None

def convert_to_timestamp(time_str):
    """将时间字符串转换为毫秒级时间戳"""
    try:
        # 尝试解析格式如 "2025-9-27 15:29:40:317"
        dt = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S:%f")
        return int(dt.timestamp() * 1000)  # 转换为毫秒
    except ValueError:
        try:
            # 尝试其他可能的格式
            dt = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            return int(dt.timestamp() * 1000)
        except ValueError:
            print(f"警告：无法解析时间格式: {time_str}")
            return int(time.time() * 1000)  # 使用当前时间作为默认值

print(f"开始读取文件：{input_file}")

# 读取文件内容
with open(input_file, 'r', encoding='utf-8') as f:
    # 跳过第一行列名
    headers = f.readline().strip().split('\t')
    print(f"找到 {len(headers)} 个列名")
    
    # 读取数据行
    line_count = 0
    for line in f:
        line_count += 1
        values = line.strip().split('\t')
        
        # 确保有足够的数据
        if len(values) >= 9:  # 至少需要时间、设备ID和6个数据字段
            # 提取时间戳
            time_str = values[0]
            timestamp = convert_to_timestamp(time_str)
            
            # 记录第一个时间戳
            if first_timestamp is None:
                first_timestamp = timestamp
            
            # 提取设备ID
            current_device_id = values[1]
            if device_id is None:
                device_id = current_device_id
            
            # 提取传感器数据
            # 根据用户提供的meta信息，加速度和角速度数据在第3-8列
            ax = float(values[2])
            ay = float(values[3])
            az = float(values[4])
            gx = float(values[5])
            gy = float(values[6])
            gz = float(values[7])
            
            # 创建数据记录 [timestamp, ax, ay, az, gx, gy, gz]
            data_record = [timestamp, ax, ay, az, gx, gy, gz]
            data_list.append(data_record)
        
        # 打印进度
        if line_count % 1000 == 0:
            print(f"已处理 {line_count} 行数据")

print(f"文件读取完成，共处理 {line_count} 行数据")
print(f"成功解析 {len(data_list)} 条数据记录")

# 计算采样率（假设数据是连续的）
sample_rate = 100  # 默认值
# if len(data_list) > 1:
#     time_diff = data_list[1][0] - data_list[0][0]  # 第二条记录与第一条记录的时间差
#     if time_diff > 0:
#         sample_rate = int(1000 / time_diff)  # 转换为Hz

# 构造最终的JSON格式
final_json = {
    "meta": {
        "device_id": device_id if device_id else "unknown",
        "sensor_type": "6-axis",
        "sample_rate": sample_rate,
        "data_fields": ["timestamp", "acc_x", "acc_y", "acc_z", "gyro_x", "gyro_y", "gyro_z"],
        "total_count": len(data_list)
        # 注意：CRC32计算是可选的，这里暂时省略
    },
    "data": data_list
}

# 将数据写入JSON文件
print(f"开始写入JSON文件：{output_file}")
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(final_json, f, ensure_ascii=False, indent=2)

print(f"JSON文件写入完成！")
print(f"数据已保存到：{output_file}")
print(f"JSON文件包含 {len(data_list)} 条数据记录")
print(f"最终JSON结构：")
print(f"- meta: 包含设备ID、传感器类型、采样率等元信息")
print(f"- data: 包含 {len(data_list)} 条记录的数组")
print(f"每条记录格式: [timestamp, ax, ay, az, gx, gy, gz]")
print(f"设备ID: {device_id}")
print(f"采样率: {sample_rate} Hz")