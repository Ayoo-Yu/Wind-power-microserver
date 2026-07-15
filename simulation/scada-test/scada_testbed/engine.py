"""确定性风电场景引擎。"""

from __future__ import annotations

import json
import math
import random
import threading
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


UTC = timezone.utc


class ConfigurationError(ValueError):
    """测试点表或场景配置无效。"""


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ConfigurationError(f"配置文件必须是 JSON 对象: {path}")
    return data


def validate_catalog(catalog: dict[str, Any]) -> None:
    if catalog.get("schema_version") != "1.0.0":
        raise ConfigurationError("点表 schema_version 必须为 1.0.0")
    common_address = catalog.get("common_address")
    if not isinstance(common_address, int) or not 1 <= common_address <= 65534:
        raise ConfigurationError("common_address 必须位于 1 至 65534")
    farms = catalog.get("farms")
    if not isinstance(farms, list) or not farms:
        raise ConfigurationError("点表至少需要一个场站")

    farm_codes: set[str] = set()
    ioas: set[int] = set()
    required_metrics = {
        "active_power_mw",
        "wind_speed_mps",
        "theoretical_power_mw",
        "available_power_mw",
        "availability_pct",
    }
    for farm in farms:
        code = farm.get("farm_code")
        if not isinstance(code, str) or not code:
            raise ConfigurationError("farm_code 不能为空")
        if code in farm_codes:
            raise ConfigurationError(f"场站代码重复: {code}")
        farm_codes.add(code)
        capacity = farm.get("capacity_mw")
        if not isinstance(capacity, (int, float)) or capacity <= 0:
            raise ConfigurationError(f"{code} 的 capacity_mw 必须大于零")
        points = farm.get("points")
        if not isinstance(points, dict) or set(points) != required_metrics:
            raise ConfigurationError(f"{code} 的点表字段不完整")
        for metric, point in points.items():
            ioa = point.get("ioa")
            if not isinstance(ioa, int) or not 1 <= ioa <= 16777215:
                raise ConfigurationError(f"{code}.{metric} 的 IOA 无效")
            if ioa in ioas:
                raise ConfigurationError(f"IOA 重复: {ioa}")
            ioas.add(ioa)
            point_type = point.get("type")
            if not isinstance(point_type, str) or not point_type.startswith("M_ME_"):
                raise ConfigurationError(f"{code}.{metric} 的 Type ID 无效")


def validate_scenarios(config: dict[str, Any]) -> None:
    if config.get("schema_version") != "1.0.0":
        raise ConfigurationError("场景 schema_version 必须为 1.0.0")
    scenarios = config.get("scenarios")
    if not isinstance(scenarios, dict) or not scenarios:
        raise ConfigurationError("至少需要一个测试场景")
    default = config.get("default_scenario")
    if default not in scenarios:
        raise ConfigurationError("default_scenario 不存在")
    supported = {
        "normal",
        "ramp_up",
        "curtailment",
        "turbine_trip",
        "invalid_quality",
        "stale",
        "zero_output",
    }
    for name, scenario in scenarios.items():
        if not isinstance(scenario, dict) or scenario.get("kind") not in supported:
            raise ConfigurationError(f"不支持的场景: {name}")
        if not isinstance(scenario.get("seed"), int):
            raise ConfigurationError(f"{name} 缺少整数 seed")


def power_curve_fraction(wind_speed_mps: float) -> float:
    """使用简化三次功率曲线计算理论出力比例。"""

    cut_in = 3.0
    rated = 12.0
    cut_out = 25.0
    if wind_speed_mps < cut_in or wind_speed_mps >= cut_out:
        return 0.0
    if wind_speed_mps >= rated:
        return 1.0
    numerator = wind_speed_mps**3 - cut_in**3
    denominator = rated**3 - cut_in**3
    return max(0.0, min(1.0, numerator / denominator))


@dataclass(frozen=True)
class ScenarioFrame:
    scenario: str
    sequence: int
    source_time: str
    generated_at: str
    quality: str
    transmit: bool
    farms: dict[str, dict[str, float]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "sequence": self.sequence,
            "source_time": self.source_time,
            "generated_at": self.generated_at,
            "quality": self.quality,
            "transmit": self.transmit,
            "farms": deepcopy(self.farms),
        }


class ScenarioEngine:
    """线程安全、可复现的多场站场景生成器。"""

    def __init__(self, catalog: dict[str, Any], scenario_config: dict[str, Any]):
        validate_catalog(catalog)
        validate_scenarios(scenario_config)
        self.catalog = deepcopy(catalog)
        self.scenario_config = deepcopy(scenario_config)
        self._lock = threading.RLock()
        self._scenario = scenario_config["default_scenario"]
        self._sequence = 0
        self._last_frame: ScenarioFrame | None = None
        self._paused = False

    @property
    def scenario(self) -> str:
        with self._lock:
            return self._scenario

    def available_scenarios(self) -> dict[str, dict[str, Any]]:
        return deepcopy(self.scenario_config["scenarios"])

    def select(self, name: str) -> None:
        with self._lock:
            if name not in self.scenario_config["scenarios"]:
                raise ConfigurationError(f"未知场景: {name}")
            self._scenario = name
            self._sequence = 0
            self._last_frame = None
            self._paused = False

    def reset(self) -> None:
        self.select(self.scenario)

    def set_paused(self, paused: bool) -> None:
        with self._lock:
            self._paused = bool(paused)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "scenario": self._scenario,
                "sequence": self._sequence,
                "paused": self._paused,
                "frame": self._last_frame.to_dict() if self._last_frame else None,
            }

    def tick(self, now: datetime | None = None) -> ScenarioFrame:
        with self._lock:
            generated_at = now or datetime.now(UTC)
            if generated_at.utcoffset() is None:
                generated_at = generated_at.replace(tzinfo=UTC)
            if self._paused and self._last_frame:
                frame = ScenarioFrame(
                    **{**self._last_frame.__dict__, "transmit": False}
                )
                self._last_frame = frame
                return frame

            scenario = self.scenario_config["scenarios"][self._scenario]
            next_sequence = self._sequence + 1
            trigger_cycle = int(scenario.get("trigger_cycle", 0))
            if scenario["kind"] == "stale" and self._last_frame and next_sequence > trigger_cycle:
                frame = ScenarioFrame(
                    **{**self._last_frame.__dict__, "transmit": False}
                )
                self._last_frame = frame
                return frame

            source_time = generated_at + timedelta(
                seconds=int(scenario.get("source_time_offset_seconds", 0))
            )
            quality = "Invalid" if scenario["kind"] == "invalid_quality" else "Good"
            farms: dict[str, dict[str, float]] = {}
            for farm_index, farm in enumerate(self.catalog["farms"]):
                farms[farm["farm_code"]] = self._farm_values(
                    farm=farm,
                    farm_index=farm_index,
                    sequence=next_sequence,
                    scenario=scenario,
                )

            frame = ScenarioFrame(
                scenario=self._scenario,
                sequence=next_sequence,
                source_time=source_time.isoformat(timespec="milliseconds"),
                generated_at=generated_at.isoformat(timespec="milliseconds"),
                quality=quality,
                transmit=True,
                farms=farms,
            )
            self._sequence = next_sequence
            self._last_frame = frame
            return frame

    @staticmethod
    def _farm_values(
        *,
        farm: dict[str, Any],
        farm_index: int,
        sequence: int,
        scenario: dict[str, Any],
    ) -> dict[str, float]:
        capacity = float(farm["capacity_mw"])
        cycle_length = max(1, int(scenario.get("cycle_length", 60)))
        phase = farm_index * 0.7
        rng = random.Random(int(scenario["seed"]) + farm_index * 100003 + sequence * 7919)
        kind = scenario["kind"]

        if kind == "ramp_up":
            progress = min(1.0, max(0.0, (sequence - 1) / max(1, cycle_length - 1)))
            wind_speed = 3.0 + 10.0 * progress
        elif kind == "curtailment":
            wind_speed = 11.0 + 0.35 * math.sin(sequence / 5.0 + phase)
        elif kind == "zero_output":
            wind_speed = 2.0 + 0.1 * math.sin(sequence / 4.0 + phase)
        else:
            wind_speed = (
                8.0
                + 2.2 * math.sin((sequence % cycle_length) / 8.0 + phase)
                + rng.uniform(-0.25, 0.25)
            )

        availability_pct = 98.0 - farm_index * 0.6
        if (
            kind == "turbine_trip"
            and farm["farm_code"] == scenario.get("target_farm")
            and sequence >= int(scenario.get("trigger_cycle", 1))
        ):
            availability_pct = 0.0

        theoretical = capacity * power_curve_fraction(wind_speed)
        available = capacity * availability_pct / 100.0
        active = min(theoretical, available)
        if kind == "curtailment":
            active = min(active, capacity * float(scenario.get("curtailment_fraction", 0.4)))

        return {
            "active_power_mw": round(max(0.0, active), 3),
            "wind_speed_mps": round(max(0.0, wind_speed), 3),
            "theoretical_power_mw": round(max(0.0, theoretical), 3),
            "available_power_mw": round(max(0.0, available), 3),
            "availability_pct": round(max(0.0, min(100.0, availability_pct)), 3),
        }
