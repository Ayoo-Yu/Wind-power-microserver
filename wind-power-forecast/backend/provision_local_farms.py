#!/usr/bin/env python3
"""为隔离的本地 SCADA 开发环境准备场站目录。

该脚本只创建缺失的场站和静态档案，不生成实测功率、预测结果或数据源健康状态。
"""

from __future__ import annotations

import json

from sqlalchemy import inspect

from database_config import SessionLocal, engine
from db_models.farm_profile import FarmProfileConfig
from db_models.report_config import WindFarm


FARMS = (
    {
        "farm_code": "CF",
        "farm_name": "会泽仓房风电场",
        "capacity": 48.0,
        "location": "云南省曲靖市会泽县",
        "profile": {
            "province": "云南",
            "longitude": 103.3282,
            "latitude": 26.0734,
            "altitude": 2100,
            "turbine_count": 24,
            "hub_height": 110,
            "commissioning_date": "2024-01-01",
        },
    },
    {
        "farm_code": "BNJ",
        "farm_name": "会泽白泥井风电场",
        "capacity": 32.0,
        "location": "云南省曲靖市会泽县",
        "profile": {
            "province": "云南",
            "longitude": 103.3293,
            "latitude": 25.8660,
            "altitude": 2200,
            "turbine_count": 16,
            "hub_height": 110,
            "commissioning_date": "2024-01-01",
        },
    },
    {
        "farm_code": "SDS",
        "farm_name": "弥勒石洞山风电场",
        "capacity": 193.5,
        "location": "云南省红河州弥勒市",
        "profile": {
            "province": "云南",
            "longitude": 103.2137,
            "latitude": 24.1141,
            "altitude": 1900,
            "turbine_count": 105,
            "hub_height": 110,
            "commissioning_date": "2024-01-01",
        },
    },
    {
        "farm_code": "DPLZ",
        "farm_name": "马龙陡坡梁子风电场",
        "capacity": 47.5,
        "location": "云南省曲靖市马龙区",
        "profile": {
            "province": "云南",
            "longitude": 103.4053,
            "latitude": 25.2933,
            "altitude": 2150,
            "turbine_count": 19,
            "hub_height": 110,
            "commissioning_date": "2024-01-01",
        },
    },
    {
        "farm_code": "ZYX",
        "farm_name": "竹园西风电场",
        "capacity": 453.5,
        "location": "云南省红河州弥勒市",
        "profile": {
            "province": "云南",
            "longitude": 103.2613,
            "latitude": 24.0153,
            "altitude": 1874,
            "turbine_count": 72,
            "hub_height": 110,
            "commissioning_date": "2024-01-01",
        },
    },
)


def ensure_tables() -> None:
    """确认场站目录依赖的数据库表已经由迁移创建。"""
    required_tables = {"wind_farms", "farm_profile_configs"}
    existing_tables = set(inspect(engine).get_table_names())
    missing_tables = sorted(required_tables - existing_tables)
    if missing_tables:
        raise RuntimeError("数据库结构未准备完成，缺少表: " + ", ".join(missing_tables))


def provision_farms(session) -> tuple[int, int]:
    """只补充缺失目录，保留开发者已有的场站配置。"""
    created_farms = 0
    created_profiles = 0
    for item in FARMS:
        farm_code = item["farm_code"]
        farm = (
            session.query(WindFarm)
            .filter(WindFarm.farm_code == farm_code)
            .first()
        )
        if farm is None:
            session.add(
                WindFarm(
                    farm_code=farm_code,
                    farm_name=item["farm_name"],
                    capacity=item["capacity"],
                    location=item["location"],
                    is_active=True,
                )
            )
            created_farms += 1

        profile = (
            session.query(FarmProfileConfig)
            .filter(FarmProfileConfig.farm_code == farm_code)
            .first()
        )
        if profile is None:
            session.add(
                FarmProfileConfig(
                    farm_code=farm_code,
                    payload=json.dumps(item["profile"], ensure_ascii=False),
                )
            )
            created_profiles += 1

    session.commit()
    return created_farms, created_profiles


def main() -> None:
    """执行本地 SCADA 场站目录准备。"""
    ensure_tables()
    with SessionLocal() as session:
        created_farms, created_profiles = provision_farms(session)
    print(
        "[OK] 本地 SCADA 场站目录已就绪，"
        f"新增场站 {created_farms} 个，新增档案 {created_profiles} 个。"
    )


if __name__ == "__main__":
    main()
