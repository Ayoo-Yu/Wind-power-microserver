import schedule
import time
import random
import requests
import json
from datetime import datetime, timedelta

# --- 配置 ---
# 你的 Flask API 的 URL，确保 Flask 应用正在运行并且此 URL 可访问
API_URL = "http://127.0.0.1:5000/actual_power/"
# API_URL = "http://your_flask_app_domain_or_ip:port/actual_power/" # 如果部署在别处

# 新增配置：插入空值的概率 (0.0 到 1.0 之间)
NULL_INSERTION_PROBABILITY = 0.20 # 20% 的概率插入空值

# --- 核心功能 ---
def insert_actual_power_data():
    """
    生成随机数据或 None并通过 API 插入到数据库中。
    脚本在 HH:05, HH:20, HH:35, HH:50 执行时，计算并发送前一个 15 分钟整点的时间戳。
    例如，在 HH:05 执行时，发送 HH:00 的数据。
    大约有 NULL_INSERTION_PROBABILITY 的概率会插入 None (JSON null) 作为 wp_true 的值。
    """
    try:
        # 1. 决定是插入随机数还是 None
        wp_true_final_value = None
        log_value_str = "null" # 用于日志记录

        if random.random() < NULL_INSERTION_PROBABILITY:
            # 满足概率，插入 None (JSON null)
            wp_true_final_value = None
            log_value_str = "null"
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Intending to insert NULL for wp_true based on probability.")
        else:
            # 不满足概率，生成随机数
            wp_true_random_value = random.uniform(0, 453.5)
            wp_true_final_value = round(wp_true_random_value, 4) # 保留几位小数
            log_value_str = f"{wp_true_final_value:.4f}"

        # 2. 生成应该插入的**前一个 15 分钟整点**时间戳 (ISO 8601 格式)
        now = datetime.now()
        interval_minute = now.minute - (now.minute % 15)
        timestamp_obj = now.replace(minute=interval_minute, second=0, microsecond=0)
        timestamp_str = timestamp_obj.isoformat()

        payload = {
            "Timestamp": timestamp_str,
            "wp_true": wp_true_final_value # 可能是数字，也可能是 None
        }

        # 打印更清晰的日志信息
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Executing task. Attempting to insert data for timestamp: {timestamp_str} with value: {log_value_str}")

        response = requests.post(API_URL, json=payload, timeout=10) # 设置10秒超时

        if response.status_code == 201:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Successfully inserted data for timestamp: {timestamp_str}. Response: {response.json()}")
        elif response.status_code == 400:
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
print("Scheduler started.")
print(f"Insertion task will execute at HH:05, HH:20, HH:35, HH:50.")
print(f"Each execution will insert data for the PREVIOUS 15-minute interval (HH:00, HH:15, HH:30, HH:45).")
print(f"There is a {NULL_INSERTION_PROBABILITY*100:.0f}% chance of inserting a null value for 'wp_true'.") # 新增日志
print(f"API Endpoint: {API_URL}")

schedule.every().hour.at(":05").do(insert_actual_power_data)
schedule.every().hour.at(":20").do(insert_actual_power_data)
schedule.every().hour.at(":35").do(insert_actual_power_data)
schedule.every().hour.at(":50").do(insert_actual_power_data)

# --- 主循环 ---
if __name__ == "__main__":
    try:
        # print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Performing an initial test insertion...")
        # insert_actual_power_data()
        # print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Initial test insertion complete.")

        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scheduler stopped by user.")
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] An critical error occurred in the scheduler loop: {e}")