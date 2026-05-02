"""Threshold-based extreme weather detection for wind power forecasting."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLDS: dict[str, float] = {
    "high_wind_speed": 25.0,
    "typhoon_speed": 32.0,
    "calm_wind_speed": 3.0,
    "cold_wave_temp": -5.0,
    "cold_wave_drop_24h": 8.0,
    "icing_temp_low": -5.0,
    "icing_temp_high": 2.0,
    "icing_tcwv": 15.0,
}

_FIELD_DEFAULTS: dict[str, float] = {
    "ws100_avg": 10.0,
    "temp_2t_avg": 20.0,
    "tcwv_avg": 0.0,
    "temp_24h_drop": 0.0,
}


@dataclass
class WeatherCondition:
    condition_type: str
    severity: str
    details: dict = field(default_factory=dict)
    correction_hint: str = "none"


class ExtremeWeatherDetector:
    def __init__(self, thresholds: dict | None = None) -> None:
        self._thresholds: dict[str, float] = dict(DEFAULT_THRESHOLDS)
        if thresholds:
            self._thresholds.update(thresholds)

    @property
    def thresholds(self) -> dict[str, float]:
        return self._thresholds

    def detect(self, ecmwf_row: dict) -> WeatherCondition:
        ws = self._safe_float(ecmwf_row, "ws100_avg")
        temp = self._safe_float(ecmwf_row, "temp_2t_avg")
        tcwv = self._safe_float(ecmwf_row, "tcwv_avg")
        drop = self._safe_float(ecmwf_row, "temp_24h_drop")

        t = self._thresholds

        if ws >= t["typhoon_speed"]:
            return WeatherCondition(
                condition_type="typhoon", severity="danger",
                details={"ws100_avg": ws}, correction_hint="clamp_zero",
            )
        if ws >= t["high_wind_speed"]:
            return WeatherCondition(
                condition_type="high_wind", severity="warning",
                details={"ws100_avg": ws}, correction_hint="clamp_zero",
            )
        if temp <= t["cold_wave_temp"] and drop > t["cold_wave_drop_24h"]:
            return WeatherCondition(
                condition_type="cold_wave", severity="warning",
                details={"temp_2t_avg": temp, "temp_24h_drop": drop},
                correction_hint="apply_decay",
            )
        if t["icing_temp_low"] <= temp <= t["icing_temp_high"] and tcwv > t["icing_tcwv"]:
            return WeatherCondition(
                condition_type="icing", severity="warning",
                details={"temp_2t_avg": temp, "tcwv_avg": tcwv},
                correction_hint="apply_decay",
            )
        if ws < t["calm_wind_speed"]:
            return WeatherCondition(
                condition_type="calm_wind", severity="info",
                details={"ws100_avg": ws}, correction_hint="clamp_zero",
            )
        return WeatherCondition(
            condition_type="normal", severity="info",
            details={"ws100_avg": ws, "temp_2t_avg": temp, "tcwv_avg": tcwv, "temp_24h_drop": drop},
            correction_hint="none",
        )

    def detect_batch(self, ecmwf_df: pd.DataFrame) -> list[WeatherCondition]:
        if ecmwf_df.empty:
            return []
        return [self.detect(row.to_dict()) for _, row in ecmwf_df.iterrows()]

    def get_active_conditions(self, conditions: list[WeatherCondition]) -> list[WeatherCondition]:
        return [c for c in conditions if c.condition_type != "normal"]

    @staticmethod
    def _safe_float(row: dict, key: str) -> float:
        value = row.get(key)
        if value is None:
            return _FIELD_DEFAULTS.get(key, 0.0)
        try:
            return float(value)
        except (TypeError, ValueError):
            return _FIELD_DEFAULTS.get(key, 0.0)
