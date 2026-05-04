"""Save/load rolling affine calibration parameters and apply them.

Layout:
  {base_dir}/{farm_code}/{forecast_type}/params.json
  Content: {"alpha": float, "beta": float, "last_updated": "ISO timestamp"}
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_BASE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "forecast_models",
    "calibration",
)


class CalibrationManager:
    def __init__(self, base_dir: str | None = None):
        self.base_dir = base_dir or DEFAULT_BASE_DIR

    def _path(self, farm_code: str, forecast_type: str) -> str:
        return os.path.join(self.base_dir, farm_code, forecast_type, "params.json")

    def save(self, farm_code: str, forecast_type: str, alpha: float, beta: float) -> None:
        p = self._path(farm_code, forecast_type)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        data = {
            "alpha": alpha,
            "beta": beta,
            "last_updated": datetime.now().isoformat(),
        }
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("Saved calibration for %s/%s: alpha=%.4f beta=%.2f", farm_code, forecast_type, alpha, beta)

    def load(self, farm_code: str, forecast_type: str) -> Optional[dict]:
        p = self._path(farm_code, forecast_type)
        if not os.path.exists(p):
            return None
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    def apply(self, farm_code: str, forecast_type: str, raw_pred: np.ndarray, cap: float) -> np.ndarray:
        params = self.load(farm_code, forecast_type)
        if params is None:
            return raw_pred
        calibrated = params["alpha"] * raw_pred + params["beta"]
        return np.clip(calibrated, 0, cap)
