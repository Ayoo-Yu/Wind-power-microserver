#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IEC 60870-5-104 多场站 SCADA 模拟服务器

为每个风电场创建独立的 station (CASDU)，每个场站一个功率 IOA。
按各自装机容量生成真实感功率数据。

环境变量:
  SIMULATOR_PORT         - 监听端口 (默认 2404)
  UPDATE_INTERVAL_SECONDS - 数据刷新间隔秒数 (默认 10)

场站配置硬编码 (与系统5个真实风电场一致):
  CASDU 1  -> CF   仓房     48.0 MW   IOA 16385
  CASDU 2  -> BNJ  白泥井   32.0 MW   IOA 16385
  CASDU 3  -> SDS  石洞山  193.5 MW   IOA 16385
  CASDU 4  -> DPLZ 陡坡梁子 47.5 MW   IOA 16385
  CASDU 5  -> ZYX  竹园西  453.5 MW   IOA 16385

每个场站功率 IOA 统一用 16385 (模拟真实环境: 各场站在各自 CASDU 地址下上报功率)。
"""

import c104
import time
import math
import random
import logging
import os
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8), name='Asia/Shanghai')

SERVER_PORT = int(os.environ.get('SIMULATOR_PORT', '2404'))
UPDATE_INTERVAL = int(os.environ.get('UPDATE_INTERVAL_SECONDS', '10'))

# 5个真实风电场配置
# 真实环境: 同一个 CASDU, 不同 IOA 区分各场站功率
COMMON_ADDRESS = 1

FARMS = [
    {"ioa": 16385, "farm_code": "CF",   "name": "仓房",     "capacity": 48.0,   "farm_index": 0},
    {"ioa": 16386, "farm_code": "BNJ",  "name": "白泥井",   "capacity": 32.0,   "farm_index": 1},
    {"ioa": 16387, "farm_code": "SDS",  "name": "石洞山",   "capacity": 193.5,  "farm_index": 2},
    {"ioa": 16388, "farm_code": "DPLZ", "name": "陡坡梁子", "capacity": 47.5,   "farm_index": 3},
    {"ioa": 16389, "farm_code": "ZYX",  "name": "竹园西",   "capacity": 453.5,  "farm_index": 4},
]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("SCADA-Simulator")

# 每个 farm 的最新功率值
latest_powers = {f["farm_code"]: 0.0 for f in FARMS}


def generate_power(capacity: float, farm_index: int) -> float:
    """为指定场站生成真实风功率值"""
    beijing_now = datetime.now(BEIJING_TZ)
    hour = beijing_now.hour + beijing_now.minute / 60.0
    day_of_year = beijing_now.timetuple().tm_yday

    phase_offset = farm_index * 1.2
    amplitude = 0.25 + farm_index * 0.05
    diurnal = 0.5 + amplitude * math.sin((hour - 4 + phase_offset) * math.pi / 12.0)
    seasonal = 0.5 + 0.2 * math.sin(day_of_year * math.pi / 182.5)
    gust = random.gauss(0, 0.04)
    factor = max(0.0, min(1.0, diurnal * seasonal + gust))

    if random.random() < 0.03:
        factor = random.uniform(0.0, 0.05)

    return round(factor * capacity, 2)


def make_on_before_read(farm_code: str):
    """为每个场站创建独立的 on_before_read 回调"""
    def on_before_read(point: c104.Point) -> None:
        power = latest_powers.get(farm_code, 0.0)
        point.value = power
        logger.info(f"GI READ CASDU point IOA={point.io_address}: {power} MW  [{farm_code}]")
    return on_before_read


def on_connect(server: c104.Server, ip: str) -> bool:
    logger.info(f"Client connected from {ip}")
    return True


def main():
    logger.info("=" * 60)
    logger.info("IEC 60870-5-104 多场站 SCADA Simulator")
    logger.info(f"Port: {SERVER_PORT}")
    logger.info(f"Update interval: {UPDATE_INTERVAL}s")
    logger.info(f"Farms: {len(FARMS)}")
    for f in FARMS:
        logger.info(f"  CASDU {COMMON_ADDRESS}  IOA {f['ioa']}  {f['farm_code']:5s}  {f['name']:<8s}  {f['capacity']:>6.1f} MW")
    logger.info("=" * 60)

    server = c104.Server(ip="0.0.0.0", port=SERVER_PORT)

    station = server.add_station(common_address=COMMON_ADDRESS)
    for farm in FARMS:
        point = station.add_point(io_address=farm["ioa"], type=c104.Type.M_ME_NC_1)
        point.on_before_read(make_on_before_read(farm["farm_code"]))
        logger.info(f"  Point IOA={farm['ioa']} [{farm['farm_code']}] ready")

    server.on_connect(on_connect)
    server.start()
    logger.info("Server started. Waiting for client connections...")

    try:
        while True:
            for farm in FARMS:
                power = generate_power(farm["capacity"], farm["farm_index"])
                latest_powers[farm["farm_code"]] = power

            beijing_now = datetime.now(BEIJING_TZ)
            parts = [f"{latest_powers[f['farm_code']]:>7.1f}" for f in FARMS]
            codes = [f["farm_code"] for f in FARMS]
            logger.info(
                f"Power: " + " | ".join(f"{c}={v}MW" for c, v in zip(codes, parts))
                + f" | {beijing_now.strftime('%H:%M:%S')}"
            )
            time.sleep(UPDATE_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        server.stop()
        logger.info("Simulator stopped.")


if __name__ == "__main__":
    main()
