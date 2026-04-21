#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IEC 60870-5-104 SCADA 模拟服务器

自动化生成真实风功率数据（0-200MW），含日周期变化和随机波动。
使用 c104 库的 Server 类，与客户端使用同一库，确保协议兼容。
"""

import c104
import time
import math
import random
import logging
import os
from datetime import datetime, timezone, timedelta

# 北京时间
BEIJING_TZ = timezone(timedelta(hours=8), name='Asia/Shanghai')

# 配置
SERVER_PORT = int(os.environ.get('SIMULATOR_PORT', '2404'))
POWER_MIN = float(os.environ.get('POWER_MIN', '0'))
POWER_MAX = float(os.environ.get('POWER_MAX', '200'))
UPDATE_INTERVAL = int(os.environ.get('UPDATE_INTERVAL_SECONDS', '10'))
COMMON_ADDRESS = 1

# 全局最新功率值
latest_power = 0.0

# 日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("SCADA-Simulator")


def generate_wind_power():
    """生成真实风功率值"""
    beijing_now = datetime.now(BEIJING_TZ)
    hour = beijing_now.hour + beijing_now.minute / 60.0

    # 日周期：14:00峰值，04:00低谷
    diurnal = 0.5 + 0.3 * math.sin((hour - 4) * math.pi / 12.0)

    # 季节变化
    day_of_year = beijing_now.timetuple().tm_yday
    seasonal = 0.5 + 0.2 * math.sin(day_of_year * math.pi / 182.5)

    # 随机阵风
    gust = random.gauss(0, 0.05)

    factor = max(0.0, min(1.0, diurnal * seasonal + gust))

    # 2%无风概率
    if random.random() < 0.02:
        factor = random.uniform(0.0, 0.05)

    power = POWER_MIN + factor * (POWER_MAX - POWER_MIN)
    return round(power, 2)


def on_before_read(point: c104.Point) -> None:
    """客户端发起总查询(GI)时回调——更新点值"""
    global latest_power
    latest_power = generate_wind_power()
    point.value = latest_power
    logger.info(f"GI READ IOA={point.io_address}: {latest_power} MW")


def on_connect(server: c104.Server, ip: str) -> bool:
    """连接事件回调"""
    logger.info(f"Client connected from {ip}")
    return True


def main():
    global latest_power

    logger.info("=" * 50)
    logger.info("IEC 60870-5-104 SCADA Simulator")
    logger.info(f"Port: {SERVER_PORT}")
    logger.info(f"Power range: {POWER_MIN} - {POWER_MAX} MW")
    logger.info(f"Update interval: {UPDATE_INTERVAL}s")
    logger.info("=" * 50)

    # 创建服务器
    server = c104.Server(ip="0.0.0.0", port=SERVER_PORT)

    # 添加站点
    station = server.add_station(common_address=COMMON_ADDRESS)

    # 添加功率测量点（匹配客户端配置）
    point_16385 = station.add_point(io_address=16385, type=c104.Type.M_ME_NC_1)
    point_16385.on_before_read(on_before_read)

    point_1009 = station.add_point(io_address=1009, type=c104.Type.M_ME_NC_1)
    point_1009.on_before_read(on_before_read)

    # 连接回调
    server.on_connect(on_connect)

    # 启动服务器
    server.start()
    logger.info("Server started. Waiting for client connections...")

    try:
        while True:
            latest_power = generate_wind_power()
            beijing_now = datetime.now(BEIJING_TZ)
            logger.info(
                f"Power: {latest_power} MW | "
                f"Time: {beijing_now.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            time.sleep(UPDATE_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        server.stop()
        logger.info("Simulator stopped.")


if __name__ == "__main__":
    main()
