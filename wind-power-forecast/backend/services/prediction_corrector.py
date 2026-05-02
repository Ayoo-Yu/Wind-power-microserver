"""Post-processing corrections for wind power predictions."""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

from services.extreme_weather_detector import WeatherCondition

logger = logging.getLogger(__name__)

_REASON_MAP: dict[str, str] = {
    "high_wind": "超大风停机",
    "typhoon": "台风停机",
    "calm_wind": "无风停机",
    "cold_wave": "寒潮衰减",
    "icing": "结冰衰减",
}

_CHANGE_TOLERANCE: float = 0.01


class PredictionCorrector:
    def __init__(self, config: dict | None = None) -> None:
        self._config: dict[str, Any] = dict(config) if config else {}

    def correct(
        self,
        predictions: np.ndarray,
        conditions: list[WeatherCondition],
        capacity: float,
    ) -> tuple[np.ndarray, list[dict]]:
        if len(predictions) != len(conditions):
            raise ValueError(
                f"Length mismatch: {len(predictions)} predictions vs "
                f"{len(conditions)} conditions"
            )

        corrected = predictions.copy()
        records: list[dict] = []

        for idx, (pred_val, cond) in enumerate(zip(corrected, conditions)):
            val = float(pred_val)
            new_val = self._apply_condition(val, cond)
            clamped = max(0.0, min(capacity, new_val))
            corrected[idx] = clamped

            if abs(val - new_val) > _CHANGE_TOLERANCE:
                records.append({
                    "index": idx,
                    "type": cond.condition_type,
                    "before": val,
                    "after": new_val,
                    "reason": _REASON_MAP.get(cond.condition_type, cond.condition_type),
                })

            if abs(new_val - clamped) > _CHANGE_TOLERANCE:
                records.append({
                    "index": idx,
                    "type": "capacity_clamp",
                    "before": new_val,
                    "after": clamped,
                    "reason": "超出装机容量",
                })

        logger.debug(
            "Correction complete: %d corrections out of %d predictions",
            len(records), len(predictions),
        )
        return corrected, records

    def get_correction_summary(self, correction_records: list[dict]) -> dict:
        by_type: dict[str, int] = {}
        for record in correction_records:
            ctype = record.get("type", "unknown")
            by_type[ctype] = by_type.get(ctype, 0) + 1
        return {
            "total_corrections": len(correction_records),
            "by_type": by_type,
        }

    @staticmethod
    def _apply_condition(value: float, condition: WeatherCondition) -> float:
        hint = condition.correction_hint
        ctype = condition.condition_type

        if hint == "clamp_zero":
            return 0.0
        if hint == "apply_decay":
            decay = PredictionCorrector._compute_decay(ctype, condition.details)
            return value * decay
        return value

    @staticmethod
    def _compute_decay(condition_type: str, details: dict) -> float:
        if condition_type == "cold_wave":
            temp = details.get("temp_2t_avg", 0.0)
            decay = 0.7 - (abs(temp) - 5) * 0.05
            return max(0.3, decay)
        if condition_type == "icing":
            tcwv = details.get("tcwv_avg", 0.0)
            decay = 0.6 - (tcwv - 10) * 0.02
            return max(0.3, decay)
        return 1.0
