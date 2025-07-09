import schedule
import time
import random
import requests
import json
from datetime import datetime, timedelta

# --- 配置 ---
# 你的 Flask API 的 URL，确保 Flask 应用正在运行并且此 URL 可访问
# 如果 Flask 应用和这个脚本在同一台机器上运行，并且 Flask 使用默认端口 5000，通常是这个
API_URL = "http://127.0.0.1:5000/actual_power/"
# API_URL = "http://your_flask_app_domain_or_ip:port/actual_power/" # 如果部署在别处

# --- 核心功能 ---
def insert_actual_power_data():
    """
    生成随机数据并通过 API 插入到数据库中。
    脚本在 HH:05, HH:20, HH:35, HH:50 执行时，计算并发送前一个 15 分钟整点的时间戳。
    例如，在 HH:05 执行时，发送 HH:00 的数据。
    """
    try:
        # 1. 生成随机数
        wp_true_value = random.uniform(0, 453.5)

        # 2. 生成应该插入的**前一个 15 分钟整点**时间戳 (ISO 8601 格式)
        #    脚本在 HH:05, HH:20, HH:35, HH:50 执行。
        #    我们需要计算出最近的 HH:00, HH:15, HH:30, HH:45 时间点。
        now = datetime.now()

        # 计算最近一个过去的 15 分钟整点对应的分钟数
        # 例如：
        # 如果现在是 HH:05 (now.minute=5): 5 - (5 % 15) = 5 - 5 = 0。目标分钟是 00。
        # 如果现在是 HH:20 (now.minute=20): 20 - (20 % 15) = 20 - 5 = 15。目标分钟是 15。
        # 如果现在是 HH:35 (now.minute=35): 35 - (35 % 15) = 35 - 5 = 30。目标分钟是 30。
        # 如果现在是 HH:50 (now.minute=50): 50 - (50 % 15) = 50 - 5 = 45。目标分钟是 45。
        # 如果因为某种原因脚本在 HH:03 执行 (now.minute=3): 3 - (3 % 15) = 3 - 3 = 0。目标分钟是 00。
        # 如果因为某种原因脚本在 HH:18 执行 (now.minute=18): 18 - (18 % 15) = 18 - 3 = 15。目标分钟是 15。
        # 这种计算方法可以确保总能得到最近的 HH:00, HH:15, HH:30, HH:45 中的一个。
        interval_minute = now.minute - (now.minute % 15)

        # 构造精确的时间戳，秒和微秒设为0
        timestamp_obj = now.replace(minute=interval_minute, second=0, microsecond=0)

        # 如果计算出的时间戳是未来时间（理论上不应该发生，但作为保险）
        # 或者时间戳比当前时间早太多（说明系统时间可能有问题），可以加检查
        # 这里我们假设系统时间正常且 schedule 触发的时间误差在合理范围内

        timestamp_str = timestamp_obj.isoformat()

        payload = {
            "Timestamp": timestamp_str,
            "wp_true": round(wp_true_value, 4)  # 保留几位小数，根据需要调整
        }

        # 打印更清晰的日志信息，说明正在尝试插入哪个时间戳的数据
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Executing task. Attempting to insert data for timestamp: {timestamp_str} with value: {payload['wp_true']:.4f}")

        response = requests.post(API_URL, json=payload, timeout=10) # 设置10秒超时

        if response.status_code == 201:
            # 打印插入成功的时间戳，再次验证是否是预期的 HH:00, :15, :30, :45
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Successfully inserted data for timestamp: {timestamp_str}. Response: {response.json()}")
        elif response.status_code == 400:
            # 检查是否是时间戳已存在的错误
            error_data = response.json()
            if "error" in error_data and "已存在" in error_data["error"]:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Data for timestamp {timestamp_str} already exists. Skipping.")
            else:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error inserting data (400) for timestamp {timestamp_str}: {response.text}")
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error inserting data for timestamp {timestamp_str}: {response.status_code} - {response.text}")

    except requests.exceptions.ConnectionError:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error: Could not connect to API at {API_URL}. Is the Flask app running?")
    except requests.exceptions.Timeout:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error: Request to API timed out.")
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] An unexpected error occurred: {str(e)}")

# --- 调度任务 ---
# "每十五分钟整过5分钟" 意味着在 :05, :20, :35, :50 分时执行
print("Scheduler started.")
# 这里的说明很重要，明确了执行时间和数据时间戳的区别
print(f"Insertion task will execute at HH:05, HH:20, HH:35, HH:50.")
print(f"Each execution will insert data for the PREVIOUS 15-minute interval (HH:00, HH:15, HH:30, HH:45).")
print(f"API Endpoint: {API_URL}")

# 设置调度，在指定的分钟数的第0秒触发
schedule.every().hour.at(":05").do(insert_actual_power_data)
schedule.every().hour.at(":20").do(insert_actual_power_data)
schedule.every().hour.at(":35").do(insert_actual_power_data)
schedule.every().hour.at(":50").do(insert_actual_power_data)

# --- 主循环 ---
if __name__ == "__main__":
    try:
        # 可选：立即执行一次用于测试或填充最近的数据点
        # 注意：如果当前时间不是正好在 :05, :20, :35, :50 附近，
        # 立即执行会插入当前时间所在的 15 分钟整点的数据。
        # print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Performing an initial test insertion...")
        # insert_actual_power_data()
        # print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Initial test insertion complete.")

        while True:
            schedule.run_pending()
            time.sleep(1)  # 每秒检查一次是否有任务需要运行
    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scheduler stopped by user.")
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] An critical error occurred in the scheduler loop: {e}")