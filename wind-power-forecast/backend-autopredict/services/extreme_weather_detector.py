# services/extreme_weather_detector.py
"""Threshold-based extreme weather detection for wind power forecasting.

Analyzes ECMWF meteorological rows and returns a :class:`WeatherCondition`
indicating the most significant active weather phenomenon.  Detection follows
a strict priority order so that the most operationally relevant condition is
always reported first.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default thresholds
# ---------------------------------------------------------------------------

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

# Safe defaults used when a field is missing or None in the input row.
# Chosen so that missing data resolves to "normal" (no false positives).
_FIELD_DEFAULTS: dict[str, float] = {
    "ws100_avg": 10.0,
    "temp_2t_avg": 20.0,
    "tcwv_avg": 0.0,
    "temp_24h_drop": 0.0,
}


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class WeatherCondition:
    """Describes a detected weather condition."""

    condition_type: str
    severity: str
    details: dict = field(default_factory=dict)
    correction_hint: str = "none"


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class ExtremeWeatherDetector:
    """Detect extreme weather conditions from ECMWF data rows.

    Parameters
    ----------
    thresholds:
        Optional dict overriding one or more entries in
        :data:`DEFAULT_THRESHOLDS`.  Keys not provided fall back to defaults.
    """

    def __init__(self, thresholds: dict | None = None) -> None:
        # Copy defaults so per-instance mutations never affect the global.
        self._thresholds: dict[str, float] = dict(DEFAULT_THRESHOLDS)
        if thresholds:
            self._thresholds.update(thresholds)

    # -- properties ---------------------------------------------------------

    @property
    def thresholds(self) -> dict[str, float]:
        """Return a reference to the mutable thresholds dict."""
        return self._thresholds

    # -- public API ---------------------------------------------------------

    def detect(self, ecmwf_row: dict) -> WeatherCondition:
        """Detect the most significant weather condition in *ecmwf_row*.

        Parameters
        ----------
        ecmwf_row:
            A dict (typically one row from an ECMWF DataFrame) with fields
            like ``ws100_avg``, ``temp_2t_avg``, ``tcwv_avg``, and
            ``temp_24h_drop``.  Missing keys are replaced with safe defaults
            so the result is always ``normal`` for incomplete data.

        Returns
        -------
        WeatherCondition
            The highest-priority condition that matches.
        """
        ws = self._safe_float(ecmwf_row, "ws100_avg")
        temp = self._safe_float(ecmwf_row, "temp_2t_avg")
        tcwv = self._safe_float(ecmwf_row, "tcwv_avg")
        drop = self._safe_float(ecmwf_row, "temp_24h_drop")

        t = self._thresholds

        # Priority 1 – typhoon
        if ws >= t["typhoon_speed"]:
            logger.debug("Typhoon detected: ws100_avg=%.1f", ws)
            return WeatherCondition(
                condition_type="typhoon",
                severity="danger",
                details={"ws100_avg": ws},
                correction_hint="clamp_zero",
            )

        # Priority 2 – high wind
        if ws >= t["high_wind_speed"]:
            logger.debug("High wind detected: ws100_avg=%.1f", ws)
            return WeatherCondition(
                condition_type="high_wind",
                severity="warning",
                details={"ws100_avg": ws},
                correction_hint="clamp_zero",
            )

        # Priority 3 – cold wave
        if temp <= t["cold_wave_temp"] and drop > t["cold_wave_drop_24h"]:
            logger.debug(
                "Cold wave detected: temp=%.1f, drop=%.1f", temp, drop
            )
            return WeatherCondition(
                condition_type="cold_wave",
                severity="warning",
                details={"temp_2t_avg": temp, "temp_24h_drop": drop},
                correction_hint="apply_decay",
            )

        # Priority 4 – icing
        if (
            t["icing_temp_low"] <= temp <= t["icing_temp_high"]
            and tcwv > t["icing_tcwv"]
        ):
            logger.debug(
                "Icing risk detected: temp=%.1f, tcwv=%.1f", temp, tcwv
            )
            return WeatherCondition(
                condition_type="icing",
                severity="warning",
                details={"temp_2t_avg": temp, "tcwv_avg": tcwv},
                correction_hint="apply_decay",
            )

        # Priority 5 – calm wind
        if ws < t["calm_wind_speed"]:
            logger.debug("Calm wind detected: ws100_avg=%.1f", ws)
            return WeatherCondition(
                condition_type="calm_wind",
                severity="info",
                details={"ws100_avg": ws},
                correction_hint="clamp_zero",
            )

        # Default – normal
        return WeatherCondition(
            condition_type="normal",
            severity="info",
            details={
                "ws100_avg": ws,
                "temp_2t_avg": temp,
                "tcwv_avg": tcwv,
                "temp_24h_drop": drop,
            },
            correction_hint="none",
        )

    def detect_batch(self, ecmwf_df: pd.DataFrame) -> list[WeatherCondition]:
        """Detect conditions for every row in *ecmwf_df*.

        Parameters
        ----------
        ecmwf_df:
            A pandas DataFrame where each row is an ECMWF observation.

        Returns
        -------
        list[WeatherCondition]
            One :class:`WeatherCondition` per row, in the same order.
        """
        if ecmwf_df.empty:
            return []

        results: list[WeatherCondition] = []
        for _, row in ecmwf_df.iterrows():
            results.append(self.detect(row.to_dict()))
        return results

    def get_active_conditions(
        self, conditions: list[WeatherCondition]
    ) -> list[WeatherCondition]:
        """Return only non-normal conditions from *conditions*.

        Parameters
        ----------
        conditions:
            A list of :class:`WeatherCondition` instances.

        Returns
        -------
        list[WeatherCondition]
            A new list containing only conditions whose
            ``condition_type`` is not ``"normal"``.
        """
        return [c for c in conditions if c.condition_type != "normal"]

    # -- private helpers ----------------------------------------------------

    @staticmethod
    def _safe_float(row: dict, key: str) -> float:
        """Extract *key* from *row*, falling back to a safe default.

        Returns 0.0 (via ``_FIELD_DEFAULTS``) when the key is absent,
        ``None``, or not convertible to float.
        """
        value = row.get(key)
        if value is None:
            return _FIELD_DEFAULTS.get(key, 0.0)
        try:
            return float(value)
        except (TypeError, ValueError):
            return _FIELD_DEFAULTS.get(key, 0.0)
