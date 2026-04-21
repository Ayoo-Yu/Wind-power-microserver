#!/usr/bin/env python3
"""
种子脚本：创建5个真实风电场 + 回填48小时历史功率数据
用法: python seed_farms.py

风电场:
  - 会泽仓房      24台   48.0MW  (混装机组, 历史最大出力45.8MW)
  - 会泽白泥井    16台   34.0MW  (混装机组, 历史最大出力31.5MW)
  - 弥勒石洞山   105台  193.5MW  (48×2.0 + 24×2.0 + 33×1.5MW)
  - 马龙陡坡梁子  19台   50.0MW  (混装机组, 历史最大出力47.3MW)
  - 竹园西       72台  453.5MW  (55×6.7 + 17×5.0MW)
"""

import os
import sys
import math
import random
import json
from datetime import datetime, timedelta

# 确保在 backend 目录运行
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database_config import engine, SessionLocal
from db_models.report_config import WindFarm
from db_models.farm_profile import FarmProfileConfig
from db_models.power import ActualPower, SupershortlPower, ShortlPower
from sqlalchemy import inspect

# ── 5个真实风电场配置 ──
FARMS = [
    {
        "farm_code": "CF",
        "farm_name": "会泽仓房风电场",
        "capacity": 48.0,
        "location": "云南省曲靖市会泽县",
        "longitude": 103.3282,
        "latitude": 26.0734,
        "altitude": 2100,
        "turbine_count": 24,
        "hub_height": 110,
        "commissioning_date": "2024-01-01",
    },
    {
        "farm_code": "BNJ",
        "farm_name": "会泽白泥井风电场",
        "capacity": 34.0,
        "location": "云南省曲靖市会泽县",
        "longitude": 103.3293,
        "latitude": 25.8660,
        "altitude": 2200,
        "turbine_count": 16,
        "hub_height": 110,
        "commissioning_date": "2024-01-01",
    },
    {
        "farm_code": "SDS",
        "farm_name": "弥勒石洞山风电场",
        "capacity": 193.5,
        "location": "云南省红河州弥勒市",
        "longitude": 103.2137,
        "latitude": 24.1141,
        "altitude": 1900,
        "turbine_count": 105,
        "hub_height": 110,
        "commissioning_date": "2024-01-01",
    },
    {
        "farm_code": "DPLZ",
        "farm_name": "马龙陡坡梁子风电场",
        "capacity": 50.0,
        "location": "云南省曲靖市马龙区",
        "longitude": 103.4053,
        "latitude": 25.2933,
        "altitude": 2150,
        "turbine_count": 19,
        "hub_height": 110,
        "commissioning_date": "2024-01-01",
    },
    {
        "farm_code": "ZYX",
        "farm_name": "竹园西风电场",
        "capacity": 453.5,
        "location": "云南省红河州弥勒市",
        "longitude": 103.2613,
        "latitude": 24.0153,
        "altitude": 1874,
        "turbine_count": 72,
        "hub_height": 110,
        "commissioning_date": "2024-01-01",
    },
]


def ensure_tables():
    """确保所有表存在"""
    from db_models.base import Base
    Base.metadata.create_all(engine)
    print("[OK] 数据库表检查完成")


def seed_farms(db):
    """创建5个真实风电场"""
    # 先清理旧的虚拟场站
    virtual_codes = ["FARM_01", "FARM_02", "FARM_03", "FARM_04", "FARM_05"]
    for vcode in virtual_codes:
        old_farm = db.query(WindFarm).filter(WindFarm.farm_code == vcode).first()
        if old_farm:
            # 清理关联的功率数据，避免孤儿记录
            db.query(ActualPower).filter(ActualPower.farm_code == vcode).delete()
            db.query(SupershortlPower).filter(SupershortlPower.farm_code == vcode).delete()
            db.query(ShortlPower).filter(ShortlPower.farm_code == vcode).delete()
            db.query(FarmProfileConfig).filter(FarmProfileConfig.farm_code == vcode).delete()
            db.delete(old_farm)
            print(f"  [CLEAN] 删除旧场站及关联数据: {vcode}")
    db.commit()

    for farm_cfg in FARMS:
        existing_farm = db.query(WindFarm).filter(
            WindFarm.farm_code == farm_cfg["farm_code"]
        ).first()

        if existing_farm:
            # 更新已有场站信息
            existing_farm.farm_name = farm_cfg["farm_name"]
            existing_farm.capacity = farm_cfg["capacity"]
            existing_farm.location = farm_cfg["location"]
            existing_farm.is_active = True
            print(f"  [UPDATE] {farm_cfg['farm_code']} - {farm_cfg['farm_name']} ({farm_cfg['capacity']}MW)")
        else:
            farm = WindFarm(
                farm_code=farm_cfg["farm_code"],
                farm_name=farm_cfg["farm_name"],
                capacity=farm_cfg["capacity"],
                location=farm_cfg["location"],
                is_active=True,
            )
            db.add(farm)
            print(f"  [OK] 创建场站: {farm_cfg['farm_code']} - {farm_cfg['farm_name']} ({farm_cfg['capacity']}MW)")

        # 创建或更新 profile config
        existing_profile = db.query(FarmProfileConfig).filter(
            FarmProfileConfig.farm_code == farm_cfg["farm_code"]
        ).first()

        payload = json.dumps({
            "province": "云南",
            "longitude": farm_cfg["longitude"],
            "latitude": farm_cfg["latitude"],
            "altitude": farm_cfg["altitude"],
            "turbine_count": farm_cfg["turbine_count"],
            "hub_height": farm_cfg["hub_height"],
            "commissioning_date": farm_cfg["commissioning_date"],
            "scada_status": "online",
            "nwp_status": "online",
        })

        if existing_profile:
            existing_profile.payload = payload
        else:
            profile = FarmProfileConfig(
                farm_code=farm_cfg["farm_code"],
                payload=payload,
            )
            db.add(profile)

    db.commit()
    print(f"[OK] 场站创建/更新完成")
    return True


def generate_power_curve(capacity, farm_index, hour):
    """为每个场站生成独特的功率曲线"""
    # 不同场站有不同的日周期相位和振幅
    phase_offset = farm_index * 1.2  # 每个场站错开1.2小时
    amplitude = 0.25 + farm_index * 0.05  # 0.25 ~ 0.45

    diurnal = 0.5 + amplitude * math.sin((hour - 4 + phase_offset) * math.pi / 12.0)

    # 季节因子
    day_of_year = datetime.now().timetuple().tm_yday
    seasonal = 0.5 + 0.2 * math.sin(day_of_year * math.pi / 182.5)

    # 随机波动（用固定种子保证可重现）
    rng = random.Random(farm_index * 1000 + int(hour * 100))
    gust = rng.gauss(0, 0.04)

    factor = max(0.0, min(1.0, diurnal * seasonal + gust))

    # 3% 无风概率
    if rng.random() < 0.03:
        factor = rng.uniform(0.0, 0.05)

    return round(factor * capacity, 2)


def seed_power_data(db, hours=48):
    """回填历史功率数据"""
    now = datetime.now().replace(second=0, microsecond=0)
    start = now - timedelta(hours=hours)

    # 对齐到15分钟间隔
    start = start.replace(minute=(start.minute // 15) * 15)

    for idx, farm_cfg in enumerate(FARMS):
        code = farm_cfg["farm_code"]
        capacity = farm_cfg["capacity"]

        # 检查是否已有数据
        existing_count = db.query(ActualPower).filter(
            ActualPower.farm_code == code,
            ActualPower.timestamp >= start,
        ).count()

        if existing_count > hours * 2:  # 已有足够数据
            print(f"  [SKIP] {code} 已有 {existing_count} 条功率数据")
            continue

        actual_records = []
        supershort_records = []
        short_records = []

        current = start
        while current <= now:
            hour = current.hour + current.minute / 60.0
            power = generate_power_curve(capacity, idx, hour)

            # actual_power
            actual_records.append({
                "timestamp": current,
                "farm_code": code,
                "wp_true": power,
            })

            # supershortl_power (16个预测值)
            rng = random.Random(idx * 9999 + int(current.timestamp()))
            preds = {}
            for k in range(2, 18):
                noise = rng.gauss(0, capacity * 0.03)
                preds[f"wp_pred{k}"] = max(0, round(power + noise, 2))
            preds["timestamp"] = current
            preds["farm_code"] = code
            supershort_records.append(preds)

            # shortl_power
            short_noise = rng.gauss(0, capacity * 0.05)
            short_records.append({
                "timestamp": current,
                "farm_code": code,
                "wp_pred": max(0, round(power + short_noise, 2)),
                "pre_at": current,
                "pre_num": 96,
            })

            current += timedelta(minutes=15)

        # 批量写入
        if actual_records:
            db.bulk_insert_mappings(ActualPower, actual_records)
        if supershort_records:
            db.bulk_insert_mappings(SupershortlPower, supershort_records)
        if short_records:
            db.bulk_insert_mappings(ShortlPower, short_records)

        print(f"  [OK] {code}: {len(actual_records)} 条功率 + {len(supershort_records)} 条超短期 + {len(short_records)} 条短期")

    db.commit()
    print("[OK] 历史数据回填完成")


def main():
    print("=" * 50)
    print("风电预测系统 — 种子数据初始化")
    print("真实风电场: 仓房/白泥井/石洞山/陡坡梁子/竹园西")
    print("=" * 50)

    ensure_tables()

    db = SessionLocal()
    try:
        seed_farms(db)
        seed_power_data(db, hours=48)
    except Exception as e:
        print(f"[ERROR] 种子数据初始化失败: {e}")
        db.rollback()
        raise
    finally:
        db.close()

    print("=" * 50)
    print("初始化完成！")
    print("=" * 50)


if __name__ == "__main__":
    main()
