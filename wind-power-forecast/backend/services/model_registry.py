import os
import logging
from datetime import datetime
from datetime import timezone

from db_session import db_session
from db_models import ModelVersion

logger = logging.getLogger(__name__)

# 各预测类型的激活阈值（val_accuracy 最低要求）
ACTIVATION_THRESHOLDS = {
    "supershort": 0.80,
    "short": 0.75,
    "medium": 0.70,
}


def _utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
        scaler_path: str | None = None,
    ) -> dict:
        is_active = self._should_activate(task_type, val_accuracy)
        now = _utc_now()

        with db_session() as session:
            if is_active:
                active_count = (
                    session.query(ModelVersion)
                    .filter_by(
                        farm_code=farm_code,
                        task_type=task_type,
                        is_active=True,
                    )
                    .with_for_update()
                    .count()
                )
                if active_count >= 5:
                    is_active = self._is_better_than_worst(
                        session, farm_code, task_type, val_accuracy,
                    )

            version = ModelVersion(
                farm_code=farm_code,
                task_type=task_type,
                algorithm=algorithm,
                hyperparams=hyperparams,
                val_rmse=val_rmse,
                val_mae=val_mae,
                val_accuracy=val_accuracy,
                is_active=is_active,
                local_path=model_path,
                scaler_path=scaler_path,
                feature_cols=feature_cols,
                training_samples=training_samples,
                trained_at=now,
                activated_at=now if is_active else None,
            )

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
        with db_session() as session:
            rows = (
                session.query(ModelVersion)
                .filter_by(farm_code=farm_code, task_type=task_type, is_active=True)
                .order_by(ModelVersion.trained_at.desc())
                .limit(limit)
                .all()
            )
            result = []
            for r in rows:
                result.append({
                    "id": r.id,
                    "algorithm": r.algorithm,
                    "val_rmse": r.val_rmse,
                    "val_mae": r.val_mae,
                    "val_accuracy": r.val_accuracy,
                    "local_path": r.local_path,
                    "scaler_path": r.scaler_path,
                    "hyperparams": r.hyperparams,
                    "feature_cols": r.feature_cols,
                    "trained_at": r.trained_at,
                })
            return result

    def deactivate(self, model_id: int):
        with db_session() as session:
            version = session.query(ModelVersion).get(model_id)
            if not version:
                logger.warning("Model version %d not found for deactivation", model_id)
                return
            if not version.is_active:
                logger.info("Model version %d already inactive", model_id)
                return
            version.is_active = False
            version.deactivated_at = _utc_now()

    def _should_activate(self, task_type: str, val_accuracy: float | None) -> bool:
        if val_accuracy is None:
            return False
        threshold = ACTIVATION_THRESHOLDS.get(task_type, 0.75)
        return val_accuracy >= threshold

    def _is_better_than_worst(
        self, session, farm_code: str, task_type: str, val_accuracy: float | None
    ) -> bool:
        if val_accuracy is None:
            return False
        worst = (
            session.query(ModelVersion)
            .filter_by(farm_code=farm_code, task_type=task_type, is_active=True)
            .with_for_update()
            .order_by(ModelVersion.val_accuracy.asc())
            .first()
        )
        if worst is None:
            return True
        return val_accuracy >= worst.val_accuracy

    def _deactivate_old_versions(self, session, farm_code: str, task_type: str, keep: int = 5):
        active_versions = (
            session.query(ModelVersion)
            .filter_by(farm_code=farm_code, task_type=task_type, is_active=True)
            .with_for_update()
            .order_by(ModelVersion.trained_at.desc())
            .all()
        )
        now = _utc_now()
        for v in active_versions[keep:]:
            v.is_active = False
            v.deactivated_at = now

    def _compute_weights(self, models: list) -> list[float]:
        if not models:
            return []
        if len(models) == 1:
            return [1.0]

        inv_rmses = []
        for m in models:
            rmse = None
            if isinstance(m, dict):
                rmse = m.get("val_rmse")
            elif hasattr(m, "val_rmse"):
                rmse = m.val_rmse
            if rmse is None:
                rmse = 0.0
            if rmse <= 0:
                inv_rmses.append(1e6)
            else:
                inv_rmses.append(1.0 / rmse)

        total = sum(inv_rmses)
        if total <= 0:
            return [1.0 / len(models)] * len(models)

        return [inv / total for inv in inv_rmses]
