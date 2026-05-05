"""Save and load 16 shift models for ultra-short-term forecasting.

Layout:
  {base_dir}/{farm_code}/supershort/
    shift_01/
      dart_model.pkl, xgb_model.pkl, cb_model.pkl
      feature_columns.json
    shift_02/
      ...
    shift_16/
      ...
    meta.json   -- {train_date, n_features, test_accuracy, grid_map, n_shifts}
"""
from __future__ import annotations

import json
import logging
import os
import pickle
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_BASE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "forecast_models",
)

N_SHIFTS = 16


class UltrashortModelManager:
    def __init__(self, base_dir: str | None = None):
        self.base_dir = base_dir or DEFAULT_BASE_DIR

    def _base(self, farm_code: str) -> str:
        return os.path.join(self.base_dir, farm_code, "supershort")

    def save_shift(
        self,
        farm_code: str,
        shift: int,
        models: Dict[str, object],
        feature_columns: List[str],
    ) -> None:
        d = os.path.join(self._base(farm_code), f"shift_{shift:02d}")
        os.makedirs(d, exist_ok=True)
        model_files = {"dart": "dart_model.pkl", "xgb": "xgb_model.pkl", "cb": "cb_model.pkl"}
        for key, filename in model_files.items():
            if key in models:
                with open(os.path.join(d, filename), "wb") as f:
                    pickle.dump(models[key], f)
        with open(os.path.join(d, "feature_columns.json"), "w", encoding="utf-8") as f:
            json.dump(feature_columns, f, ensure_ascii=False, indent=2)
        logger.info("Saved shift %d models for %s/supershort", shift, farm_code)

    def load_shift(self, farm_code: str, shift: int) -> Optional[Dict]:
        d = os.path.join(self._base(farm_code), f"shift_{shift:02d}")
        if not os.path.isdir(d):
            return None
        result: Dict = {}
        model_files = {"dart": "dart_model.pkl", "xgb": "xgb_model.pkl", "cb": "cb_model.pkl"}
        for key, filename in model_files.items():
            path = os.path.join(d, filename)
            if os.path.exists(path):
                with open(path, "rb") as f:
                    result[key] = pickle.load(f)
        fc_path = os.path.join(d, "feature_columns.json")
        if os.path.exists(fc_path):
            with open(fc_path, "r", encoding="utf-8") as f:
                result["feature_columns"] = json.load(f)
        if not any(k in result for k in ("dart", "xgb", "cb")):
            return None
        return result

    def save_meta(self, farm_code: str, meta: dict) -> None:
        d = self._base(farm_code)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2, default=str)

    def load_meta(self, farm_code: str) -> Optional[dict]:
        p = os.path.join(self._base(farm_code), "meta.json")
        if not os.path.exists(p):
            return None
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_all_shifts(self, farm_code: str) -> Dict[int, Dict]:
        result = {}
        for s in range(1, N_SHIFTS + 1):
            loaded = self.load_shift(farm_code, s)
            if loaded is not None:
                result[s] = loaded
        return result
