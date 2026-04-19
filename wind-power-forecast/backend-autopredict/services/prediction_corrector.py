# services/prediction_corrector.py
"""Post-processing corrections for wind power predictions.

Applies weather-condition-based adjustments (clamp-to-zero or dynamic decay)
and capacity clamping to raw prediction arrays.  Every correction is recorded
for auditability and the input array is never mutated.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

from services.extreme_weather_detector import WeatherCondition

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Reason strings (Chinese, matching domain terminology)
# ---------------------------------------------------------------------------

_REASON_MAP: dict[str, str] = {
    "high_wind": "超大风停机",
    "typhoon": "台风停机",
    "calm_wind": "无风停机",
    "cold_wave": "寒潮衰减",
    "icing": "结冰衰减",
}

# Tolerance for deciding whether a correction produced a meaningful change.
_CHANGE_TOLERANCE: float = 0.01


# ---------------------------------------------------------------------------
# PredictionCorrector
# ---------------------------------------------------------------------------

class PredictionCorrector:
    """Apply post-processing corrections to predictions based on weather.

    Parameters
    ----------
    config:
        Optional configuration dict.  Reserved for future use (e.g. custom
        tolerance, decay coefficients).  Currently accepted but ignored.
    """

    def __init__(self, config: dict | None = None) -> None:
        self._config: dict[str, Any] = dict(config) if config else {}

    # -- public API ---------------------------------------------------------

    def correct(
        self,
        predictions: np.ndarray,
        conditions: list[WeatherCondition],
        capacity: float,
    ) -> tuple[np.ndarray, list[dict]]:
        """Return (corrected_predictions, correction_records).

        The input *predictions* array is **never** modified; a new array is
        returned instead.

        Parameters
        ----------
        predictions:
            1-D numpy array of raw predicted power values.
        conditions:
            One :class:`WeatherCondition` per prediction element, in order.
        capacity:
            Maximum allowed power output (upper clamp bound).

        Returns
        -------
        tuple[np.ndarray, list[dict]]
            *corrected_predictions* is a new 1-D array of the same length.
            *correction_records* is a list of dicts, one per meaningful
            correction (``|before - after| > 0.01``).

        Raises
        ------
        ValueError
            If ``len(predictions) != len(conditions)``.
        """
        if len(predictions) != len(conditions):
            raise ValueError(
                f"Length mismatch: {len(predictions)} predictions vs "
                f"{len(conditions)} conditions"
            )

        corrected = predictions.copy()
        records: list[dict] = []

        for idx, (pred_val, cond) in enumerate(
            zip(corrected, conditions)
        ):
            val = float(pred_val)
            new_val = self._apply_condition(val, cond)

            # Capacity clamp: ensure 0 <= new_val <= capacity
            clamped = max(0.0, min(capacity, new_val))

            corrected[idx] = clamped

            # Record weather-driven correction if meaningful
            if abs(val - new_val) > _CHANGE_TOLERANCE:
                records.append({
                    "index": idx,
                    "type": cond.condition_type,
                    "before": val,
                    "after": new_val,
                    "reason": _REASON_MAP.get(cond.condition_type, cond.condition_type),
                })

            # Record capacity clamp separately if it caused a further change
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
            len(records),
            len(predictions),
        )
        return corrected, records

    def get_correction_summary(self, correction_records: list[dict]) -> dict:
        """Aggregate correction records into a summary.

        Parameters
        ----------
        correction_records:
            List of dicts as returned by :meth:`correct`.

        Returns
        -------
        dict
            ``{"total_corrections": int, "by_type": {str: int}}``
        """
        by_type: dict[str, int] = {}
        for record in correction_records:
            ctype = record.get("type", "unknown")
            by_type[ctype] = by_type.get(ctype, 0) + 1

        return {
            "total_corrections": len(correction_records),
            "by_type": by_type,
        }

    # -- private helpers ----------------------------------------------------

    @staticmethod
    def _apply_condition(value: float, condition: WeatherCondition) -> float:
        """Apply the weather-specific correction to a single value.

        Returns the adjusted value (before capacity clamping).
        """
        hint = condition.correction_hint
        ctype = condition.condition_type

        if hint == "clamp_zero":
            logger.debug(
                "Clamping to zero: idx type=%s value=%.2f", ctype, value
            )
            return 0.0

        if hint == "apply_decay":
            decay = PredictionCorrector._compute_decay(ctype, condition.details)
            result = value * decay
            logger.debug(
                "Applying decay: type=%s decay=%.4f value=%.2f -> %.2f",
                ctype,
                decay,
                value,
                result,
            )
            return result

        # hint == "none" or unknown => no change
        return value

    @staticmethod
    def _compute_decay(condition_type: str, details: dict) -> float:
        """Compute the decay factor for a given condition and its details.

        Formulas:
        - cold_wave: max(0.3, 0.7 - (abs(temp) - 5) * 0.05)
        - icing:     max(0.3, 0.6 - (tcwv - 10) * 0.02)
        """
        if condition_type == "cold_wave":
            temp = details.get("temp_2t_avg", 0.0)
            decay = 0.7 - (abs(temp) - 5) * 0.05
            return max(0.3, decay)

        if condition_type == "icing":
            tcwv = details.get("tcwv_avg", 0.0)
            decay = 0.6 - (tcwv - 10) * 0.02
            return max(0.3, decay)

        # Fallback: no decay
        logger.warning("Unknown decay condition type: %s", condition_type)
        return 1.0
