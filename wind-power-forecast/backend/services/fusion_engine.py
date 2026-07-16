from __future__ import annotations

import os
import logging

import joblib
import numpy as np

from services.model_registry import ModelRegistry

logger = logging.getLogger(__name__)


class FusionEngine:
    """融合引擎：查询 active 模型，加权融合预测结果。"""

    def __init__(self):
        self.registry = ModelRegistry()

    def predict(self, farm_code: str, task_type: str, features_df, model_loader=None):
        models = self.registry.get_active_models(farm_code, task_type)

        if not models:
            logger.warning("No active models for %s/%s", farm_code, task_type)
            return None

        if len(models) == 1:
            logger.info("Single active model for %s/%s, using directly", farm_code, task_type)
            return self._single_predict(models[0], features_df, model_loader)

        weights = self.registry._compute_weights(models)
        logger.info(
            "Fusing %d models for %s/%s, weights: %s",
            len(models), farm_code, task_type,
            [f"{w:.3f}" for w in weights],
        )

        predictions = []
        valid_weights = []
        for model_info, weight in zip(models, weights):
            pred = self._single_predict(model_info, features_df, model_loader)
            if pred is not None:
                predictions.append(pred)
                valid_weights.append(weight)

        if not predictions:
            logger.error("All models failed to predict for %s/%s", farm_code, task_type)
            return None

        weight_sum = sum(valid_weights)
        if weight_sum <= 0:
            valid_weights = [1.0 / len(valid_weights)] * len(valid_weights)
        else:
            valid_weights = [w / weight_sum for w in valid_weights]

        return self._weighted_combine(predictions, valid_weights)

    def _single_predict(self, model_info: dict, features_df, model_loader=None):
        model = self._load_model(model_info) if model_loader is None else model_loader(model_info)
        if model is None:
            logger.error("Failed to load model: %s", model_info.get("local_path"))
            return None

        try:
            if hasattr(model, "predict"):
                return np.asarray(model.predict(features_df))
            else:
                logger.error("Model has no predict() method")
                return None
        except Exception as e:
            logger.error("Model prediction failed: %s", e, exc_info=True)
            return None

    def _load_model(self, model_info: dict):
        local_path = model_info.get("local_path")
        if local_path and os.path.exists(local_path):
            try:
                return joblib.load(local_path)
            except Exception as e:
                logger.error("Failed to load model from %s: %s", local_path, e)

        return None

    def _weighted_combine(self, predictions: list, weights: list) -> np.ndarray | None:
        if not predictions or not weights:
            return None
        result = np.zeros_like(predictions[0], dtype=float)
        for pred, weight in zip(predictions, weights):
            result += weight * pred
        return result
