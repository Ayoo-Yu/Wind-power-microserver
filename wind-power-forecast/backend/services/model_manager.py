"""Save and load trained prediction models to/from filesystem.

Layout:
  {base_dir}/{farm_code}/{forecast_type}/
    lgb_model.pkl
    xgb_model.pkl
    cb_model.pkl
    feature_columns.json
    meta.json
"""
from __future__ import annotations

import json
import logging
import os
import pickle
from typing import Dict, List, Optional

from services.forecast_contract import (
    infer_feature_contract_version,
    validate_model_bundle,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "forecast_models",
)


class ModelManager:
    def __init__(self, base_dir: str | None = None):
        self.base_dir = base_dir or DEFAULT_BASE_DIR

    def _resolve_component(self, parent: str, name: str) -> str:
        exact = os.path.join(parent, name)
        if os.path.exists(exact):
            return exact
        try:
            lookup = {entry.lower(): entry for entry in os.listdir(parent)}
        except OSError:
            return exact
        matched = lookup.get(name.lower())
        return os.path.join(parent, matched) if matched else exact

    def _dir(self, farm_code: str, forecast_type: str) -> str:
        farm_dir = self._resolve_component(self.base_dir, farm_code)
        return self._resolve_component(farm_dir, forecast_type)

    def save(
        self,
        farm_code: str,
        forecast_type: str,
        models: Dict[str, object],
        feature_columns: List[str],
        meta: dict,
    ) -> None:
        normalized_features = validate_model_bundle(models, feature_columns)
        normalized_meta = dict(meta)
        normalized_meta.setdefault(
            "feature_contract_version",
            infer_feature_contract_version(normalized_features),
        )
        normalized_meta["feature_count"] = len(normalized_features)

        d = self._dir(farm_code, forecast_type)
        os.makedirs(d, exist_ok=True)

        model_files = {
            "lgb": "lgb_model.pkl",
            "xgb": "xgb_model.pkl",
            "cb": "cb_model.pkl",
        }
        for key, filename in model_files.items():
            if key in models:
                with open(os.path.join(d, filename), "wb") as f:
                    pickle.dump(models[key], f)

        with open(os.path.join(d, "feature_columns.json"), "w", encoding="utf-8") as f:
            json.dump(normalized_features, f, ensure_ascii=False, indent=2)

        with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(normalized_meta, f, ensure_ascii=False, indent=2, default=str)

        logger.info("Saved models for %s/%s to %s", farm_code, forecast_type, d)

    def load(self, farm_code: str, forecast_type: str) -> Optional[Dict]:
        d = self._dir(farm_code, forecast_type)
        if not os.path.isdir(d):
            return None

        result: Dict = {}
        model_files = {
            "lgb": "lgb_model.pkl",
            "xgb": "xgb_model.pkl",
            "cb": "cb_model.pkl",
        }
        for key, filename in model_files.items():
            path = os.path.join(d, filename)
            if os.path.exists(path):
                with open(path, "rb") as f:
                    result[key] = pickle.load(f)

        fc_path = os.path.join(d, "feature_columns.json")
        if os.path.exists(fc_path):
            with open(fc_path, "r", encoding="utf-8") as f:
                result["feature_columns"] = json.load(f)

        meta_path = os.path.join(d, "meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                result["meta"] = json.load(f)

        if not any(k in result for k in ("lgb", "xgb", "cb")):
            return None

        feature_columns = result.get("feature_columns")
        validate_model_bundle(result, feature_columns)
        meta = result.setdefault("meta", {})
        meta.setdefault(
            "feature_contract_version",
            infer_feature_contract_version(feature_columns),
        )
        meta.setdefault("feature_count", len(feature_columns))

        return result
