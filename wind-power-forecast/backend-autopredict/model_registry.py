# wind-power-forecast/backend-autopredict/model_registry.py
import os
import sys
import logging
from datetime import datetime

# 确保 backend-autopredict 根目录在 sys.path 中
_BACKEND_ROOT = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from db_session import db_session
from db_models import ModelVersion

logger = logging.getLogger(__name__)

# 各预测类型的激活阈值（val_accuracy 最低要求）
ACTIVATION_THRESHOLDS = {
    "supershort": 0.80,
    "short": 0.75,
    "medium": 0.70,
}


class ModelRegistry:
    """模型注册器：管理模型版本的注册、查询和停用。"""

    def register(
        self,
        farm_code: str,
        task_type: str,
        algorithm: str,
        model_path: str,
        hyperparams: dict | None = None,
        val_rmse: float | None = None,
        val_mae: float | None = None,
        val_accuracy: float | None = None,
        feature_cols: list | None = None,
        training_samples: int | None = None,
        s3_path: str | None = None,
        scaler_path: str | None = None,
    ) -> dict:
        """注册新模型版本。如果验证指标优于阈值则自动激活。"""
        is_active = self._should_activate(task_type, val_accuracy)
        now = datetime.now()

        version = ModelVersion(
            farm_code=farm_code,
            task_type=task_type,
            algorithm=algorithm,
            hyperparams=hyperparams,
            val_rmse=val_rmse,
            val_mae=val_mae,
            val_accuracy=val_accuracy,
            is_active=is_active,
            s3_path=s3_path,
            local_path=model_path,
            scaler_path=scaler_path,
            feature_cols=feature_cols,
            training_samples=training_samples,
            trained_at=now,
            activated_at=now if is_active else None,
        )

        with db_session() as session:
            # 检查是否比当前线上最差模型还差
            if is_active:
                is_active = self._is_better_than_worst(session, farm_code, task_type, val_accuracy)
                version.is_active = is_active
                version.activated_at = now if is_active else None

            session.add(version)
            session.flush()
            version_id = version.id

            if is_active:
                self._deactivate_old_versions(session, farm_code, task_type, keep=5)

        logger.info(
            "Registered model version %d: %s/%s/%s accuracy=%.4f active=%s",
            version_id, farm_code, task_type, algorithm, val_accuracy or 0, is_active,
        )
        return {"id": version_id, "is_active": is_active}

    def get_active_models(self, farm_code: str, task_type: str, limit: int = 5):
        """获取指定场站+类型的 active 模型列表，按 trained_at 降序。"""
        with db_session() as session:
            rows = (
                session.query(ModelVersion)
                .filter_by(farm_code=farm_code, task_type=task_type, is_active=True)
                .order_by(ModelVersion.trained_at.desc())
                .limit(limit)
                .all()
            )
            # 触发懒加载，在 session 关闭前提取属性
            result = []
            for r in rows:
                result.append({
                    "id": r.id,
                    "algorithm": r.algorithm,
                    "val_rmse": r.val_rmse,
                    "val_mae": r.val_mae,
                    "val_accuracy": r.val_accuracy,
                    "local_path": r.local_path,
                    "s3_path": r.s3_path,
                    "scaler_path": r.scaler_path,
                    "hyperparams": r.hyperparams,
                    "feature_cols": r.feature_cols,
                    "trained_at": r.trained_at,
                })
            return result

    def deactivate(self, model_id: int):
        """停用一个模型版本。"""
        with db_session() as session:
            version = session.query(ModelVersion).get(model_id)
            if not version:
                logger.warning("Model version %d not found for deactivation", model_id)
                return
            if not version.is_active:
                logger.info("Model version %d already inactive", model_id)
                return
            version.is_active = False
            version.deactivated_at = datetime.now()

    def _should_activate(self, task_type: str, val_accuracy: float | None) -> bool:
        """判断模型是否达到激活阈值。"""
        if val_accuracy is None:
            return False
        threshold = ACTIVATION_THRESHOLDS.get(task_type, 0.75)
        return val_accuracy >= threshold

    def _is_better_than_worst(
        self, session, farm_code: str, task_type: str, val_accuracy: float | None
    ) -> bool:
        """检查是否比当前线上最差模型更好。如果线上无模型则返回 True。"""
        if val_accuracy is None:
            return False
        worst = (
            session.query(ModelVersion)
            .filter_by(farm_code=farm_code, task_type=task_type, is_active=True)
            .order_by(ModelVersion.val_accuracy.asc())
            .first()
        )
        if worst is None:
            return True
        return val_accuracy >= worst.val_accuracy

    def _deactivate_old_versions(self, session, farm_code: str, task_type: str, keep: int = 5):
        """保留最近 N 个 active 版本，停用更早的。"""
        active_versions = (
            session.query(ModelVersion)
            .filter_by(farm_code=farm_code, task_type=task_type, is_active=True)
            .order_by(ModelVersion.trained_at.desc())
            .all()
        )
        now = datetime.now()
        for v in active_versions[keep:]:
            v.is_active = False
            v.deactivated_at = now

    def _compute_weights(self, models: list) -> list[float]:
        """基于验证集 RMSE 计算权重：weight_i = (1/rmse_i) / sum(1/rmse_j)。"""
        if not models:
            return []
        if len(models) == 1:
            return [1.0]

        inv_rmses = []
        for m in models:
            # Support both ORM objects (attribute) and dicts (key)
            rmse = None
            if isinstance(m, dict):
                rmse = m.get("val_rmse")
            elif hasattr(m, "val_rmse"):
                rmse = m.val_rmse
            if not rmse:
                rmse = 0.0
            if rmse <= 0:
                inv_rmses.append(1e6)
            else:
                inv_rmses.append(1.0 / rmse)

        total = sum(inv_rmses)
        if total <= 0:
            return [1.0 / len(models)] * len(models)

        return [inv / total for inv in inv_rmses]
