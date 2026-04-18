# wind-power-forecast/backend-autopredict/fusion_engine.py
import os
import sys
import logging

import joblib
import numpy as np

# 确保 backend-autopredict 根目录在 sys.path 中
_BACKEND_ROOT = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from model_registry import ModelRegistry

logger = logging.getLogger(__name__)


class FusionEngine:
    """融合引擎：查询 active 模型，加权融合预测结果。"""

    def __init__(self):
        self.registry = ModelRegistry()

    def predict(self, farm_code: str, task_type: str, features_df, model_loader=None):
        """融合预测主入口。

        Args:
            farm_code: 风场编码
            task_type: 预测类型 (supershort/short/medium)
            features_df: 特征 DataFrame
            model_loader: 可选的自定义模型加载函数（用于测试注入）

        Returns:
            np.ndarray: 融合后的预测数组，无可用模型时返回 None
        """
        models = self.registry.get_active_models(farm_code, task_type)

        if not models:
            logger.warning("No active models for %s/%s", farm_code, task_type)
            return None

        if len(models) == 1:
            logger.info("Single active model for %s/%s, using directly", farm_code, task_type)
            return self._single_predict(models[0], features_df, model_loader)

        # 多模型加权融合
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

        # 重新归一化权重（可能有模型加载失败）
        weight_sum = sum(valid_weights)
        if weight_sum <= 0:
            valid_weights = [1.0 / len(valid_weights)] * len(valid_weights)
        else:
            valid_weights = [w / weight_sum for w in valid_weights]

        return self._weighted_combine(predictions, valid_weights)

    def _single_predict(self, model_info: dict, features_df, model_loader=None):
        """单模型推理。"""
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
        """从本地路径或 MinIO 加载模型文件。"""
        local_path = model_info.get("local_path")
        if local_path and os.path.exists(local_path):
            try:
                return joblib.load(local_path)
            except Exception as e:
                logger.error("Failed to load model from %s: %s", local_path, e)

        s3_path = model_info.get("s3_path")
        if s3_path:
            try:
                from database_config import init_minio_client
                from config import MINIO_CONFIG
                client = init_minio_client()
                bucket = MINIO_CONFIG["buckets"].get("models", "wind-models")
                data = client.get_object(bucket, s3_path)
                import io
                return joblib.load(io.BytesIO(data.read()))
            except Exception as e:
                logger.error("Failed to load model from S3 %s: %s", s3_path, e)

        return None

    def _weighted_combine(self, predictions: list, weights: list) -> np.ndarray | None:
        """对多个预测结果加权求和。"""
        if not predictions or not weights:
            return None
        result = np.zeros_like(predictions[0], dtype=float)
        for pred, weight in zip(predictions, weights):
            result += weight * pred
        return result
