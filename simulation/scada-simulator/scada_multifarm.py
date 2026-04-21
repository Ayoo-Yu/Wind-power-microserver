#!/usr/bin/env python3
"""
多场站 SCADA 功率模拟器
每隔指定间隔，为每个场站生成模拟功率数据并 POST 到后端 API。
不依赖 C104 协议，纯 HTTP 方式，简化部署。

环境变量:
  FARM_CODES       - 逗号分隔的场站代码 (默认: CF,BNJ,SDS,DPLZ,ZYX)
  FARM_CAPACITIES  - 逗号分隔的装机容量MW (默认: 48.0,34.0,193.5,50.0,453.5)
  BACKEND_URL      - 后端 actual_power API 地址 (默认: http://host.docker.internal:5000)
  UPDATE_INTERVAL  - 更新间隔秒数 (默认: 60)
"""

import os
import math
import json
import time
import random
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8), name='Asia/Shanghai')

FARM_CODES = [s.strip() for s in os.environ.get('FARM_CODES', 'CF,BNJ,SDS,DPLZ,ZYX').split(',') if s.strip()]
FARM_CAPACITIES = [float(s.strip()) for s in os.environ.get('FARM_CAPACITIES', '48.0,34.0,193.5,50.0,453.5').split(',') if s.strip()]
BACKEND_URL = os.environ.get('BACKEND_URL', 'http://host.docker.internal:5000').rstrip('/')
UPDATE_INTERVAL = int(os.environ.get('UPDATE_INTERVAL', '60'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('MultiFarm-SCADA')


def generate_power(capacity, farm_index, hour_of_day, day_of_year):
    """为指定场站生成模拟功率值"""
    phase_offset = farm_index * 1.2
    amplitude = 0.25 + farm_index * 0.05

    diurnal = 0.5 + amplitude * math.sin((hour_of_day - 4 + phase_offset) * math.pi / 12.0)
    seasonal = 0.5 + 0.2 * math.sin(day_of_year * math.pi / 182.5)
    gust = random.gauss(0, 0.04)

    factor = max(0.0, min(1.0, diurnal * seasonal + gust))

    if random.random() < 0.03:
        factor = random.uniform(0.0, 0.05)

    return round(factor * capacity, 2)


def post_power(farm_code, timestamp_str, power):
    """POST 单条功率数据到后端"""
    url = f'{BACKEND_URL}/actual_power/'
    payload = json.dumps({
        'Timestamp': timestamp_str,
        'farm_code': farm_code,
        'wp_true': power,
    }).encode('utf-8')

    req = urllib.request.Request(
        url,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode('utf-8'))
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return e.code, body
    except Exception as e:
        return 0, str(e)


def main():
    # 对齐 capacities 数量与 farm_codes
    while len(FARM_CAPACITIES) < len(FARM_CODES):
        FARM_CAPACITIES.append(FARM_CAPACITIES[-1] if FARM_CAPACITIES else 100)

    logger.info('=' * 50)
    logger.info('多场站 SCADA 功率模拟器')
    logger.info(f'场站数: {len(FARM_CODES)}')
    logger.info(f'后端:   {BACKEND_URL}')
    logger.info(f'间隔:   {UPDATE_INTERVAL}s')
    logger.info('=' * 50)

    for i, (code, cap) in enumerate(zip(FARM_CODES, FARM_CAPACITIES)):
        logger.info(f'  [{code}] 容量={cap}MW')

    cycle = 0
    while True:
        cycle += 1
        now = datetime.now(BEIJING_TZ)
        timestamp_str = now.strftime('%Y-%m-%dT%H:%M:%S')
        hour = now.hour + now.minute / 60.0
        day_of_year = now.timetuple().tm_yday

        success = 0
        fail = 0

        for i, (code, cap) in enumerate(zip(FARM_CODES, FARM_CAPACITIES)):
            power = generate_power(cap, i, hour, day_of_year)
            status, body = post_power(code, timestamp_str, power)

            if 200 <= status < 300:
                success += 1
                action = body.get('action', '?') if isinstance(body, dict) else '?'
                logger.info(f'  [{code}] {power:7.2f} MW  status={status} action={action}')
            else:
                fail += 1
                logger.warning(f'  [{code}] POST failed: status={status} body={body[:120]}')

        logger.info(f'--- Cycle {cycle}: {success} ok / {fail} fail ---')

        time.sleep(UPDATE_INTERVAL)


if __name__ == '__main__':
    main()
