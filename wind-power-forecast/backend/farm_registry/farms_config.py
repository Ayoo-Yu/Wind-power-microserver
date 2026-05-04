"""Wind farm configuration registry.

Config-driven: add new farms here without changing any other code.
"""
from __future__ import annotations

from typing import Dict, List

FARMS: Dict[str, dict] = {
    "dplz": {
        "farm_code": "dplz",
        "name": "doupoliangzi",
        "capacity_mw": 47.5,
        "short_table": "train_pre_short_dplz",
        "mid_table": "train_pre_middle_dplz",
        "calibrate_enabled": True,
    },
    "sds": {
        "farm_code": "sds",
        "name": "shidongshan",
        "capacity_mw": 193.5,
        "short_table": "train_pre_short_sds",
        "mid_table": "train_pre_middle_sds",
        "calibrate_enabled": True,
    },
    "zyx": {
        "farm_code": "zyx",
        "name": "zhuyuanxi",
        "capacity_mw": 453.5,
        "short_table": "train_pre_short_zyx",
        "mid_table": "train_pre_middle_zyx",
        "calibrate_enabled": False,
    },
    "cf": {
        "farm_code": "cf",
        "name": "cangfang",
        "capacity_mw": 48.0,
        "short_table": "train_pre_short_cf",
        "mid_table": "train_pre_middle_cf",
        "calibrate_enabled": True,
    },
    "bnj": {
        "farm_code": "bnj",
        "name": "bainijing",
        "capacity_mw": 32.0,
        "short_table": "train_pre_short_bnj",
        "mid_table": "train_pre_middle_bnj",
        "calibrate_enabled": True,
    },
}


def get_all_farms() -> List[dict]:
    return list(FARMS.values())


def get_farm(farm_code: str) -> dict:
    if farm_code not in FARMS:
        raise KeyError(f"Unknown farm code: {farm_code}")
    return FARMS[farm_code]


def get_farm_codes() -> List[str]:
    return list(FARMS.keys())
