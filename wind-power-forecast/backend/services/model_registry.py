from __future__ import annotations

import os
import hashlib
import logging
from pathlib import Path
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


def _sha256_file(path: str | None) -> str | None:
    if not path:
        return None
    target = Path(path)
    if not target.is_file():
        return None
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _auto_approval_enabled() -> bool:
    deployment_mode = os.environ.get("DEPLOYMENT_MODE", "development").lower()
    default = "true" if deployment_mode in {"development", "test"} else "false"
    return os.environ.get("MODEL_AUTO_APPROVAL_ENABLED", default).lower() == "true"


class ModelRegistry:
    """模型注册器：管理模型版本的注册、审批、回滚和停用。"""

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
        dataset_path: str | None = None,
        dataset_version: str | None = None,
        feature_contract_version: str | None = None,
        artifact_sha256: str | None = None,
    ) -> dict:
        eligible = self._should_activate(task_type, val_accuracy)
        auto_approved = eligible and _auto_approval_enabled()
        is_active = auto_approved
        now = _utc_now()
        artifact_sha256 = artifact_sha256 or _sha256_file(model_path)
        dataset_version = dataset_version or _sha256_file(dataset_path)
        if feature_contract_version is None and feature_cols:
            try:
                from services.forecast_contract import infer_feature_contract_version
                feature_contract_version = infer_feature_contract_version(feature_cols)
            except Exception:
                feature_contract_version = "unknown"

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
                feature_contract_version=feature_contract_version,
                dataset_version=dataset_version,
                artifact_sha256=artifact_sha256,
                lifecycle_status="approved" if auto_approved else "candidate",
                approved_by="automatic-policy" if auto_approved else None,
                approved_at=now if auto_approved else None,
                training_samples=training_samples,
                trained_at=now,
                activated_at=now if is_active else None,
            )

            session.add(version)
            session.flush()
            version_id = version.id

            if is_active:
                self._deactivate_old_versions(session, farm_code, task_type, keep=5)
                is_active = bool(version.is_active)

        logger.info(
            "Registered model version %d: %s/%s/%s accuracy=%.4f active=%s",
            version_id, farm_code, task_type, algorithm, val_accuracy or 0, is_active,
        )
        return {
            "id": version_id,
            "is_active": is_active,
            "lifecycle_status": "approved" if auto_approved else "candidate",
            "artifact_sha256": artifact_sha256,
            "dataset_version": dataset_version,
        }

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
                    "feature_contract_version": r.feature_contract_version,
                    "dataset_version": r.dataset_version,
                    "artifact_sha256": r.artifact_sha256,
                    "lifecycle_status": r.lifecycle_status,
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

    def approve(self, model_id: int, actor: str) -> dict:
        """审批候选模型并在达到质量门槛后加入可用模型集合。"""
        with db_session() as session:
            version = session.query(ModelVersion).filter(ModelVersion.id == model_id).with_for_update().first()
            if version is None:
                raise ValueError(f"模型版本 {model_id} 不存在")
            if version.lifecycle_status not in {"candidate", "approved"}:
                raise ValueError("当前模型状态不允许审批，请重新训练并注册候选版本")
            if not self._should_activate(version.task_type, version.val_accuracy):
                raise ValueError("模型验证精度未达到当前任务的审批门槛")
            current_digest = _sha256_file(version.local_path)
            if current_digest is None:
                raise ValueError("模型制品文件不存在，无法审批")
            if version.artifact_sha256 and version.artifact_sha256 != current_digest:
                raise ValueError("模型制品摘要与注册记录不一致")
            if not version.dataset_version:
                raise ValueError("模型缺少训练数据版本，无法审批")

            now = _utc_now()
            version.artifact_sha256 = current_digest
            version.lifecycle_status = "approved"
            version.approved_by = str(actor)
            version.approved_at = now
            version.rejection_reason = None
            version.is_active = True
            version.activated_at = now
            version.deactivated_at = None
            self._deactivate_old_versions(
                session, version.farm_code, version.task_type, keep=5
            )
            return {
                "id": version.id,
                "status": version.lifecycle_status,
                "active": bool(version.is_active),
            }

    def reject(self, model_id: int, actor: str, reason: str) -> dict:
        with db_session() as session:
            version = session.query(ModelVersion).filter(ModelVersion.id == model_id).with_for_update().first()
            if version is None:
                raise ValueError(f"模型版本 {model_id} 不存在")
            version.lifecycle_status = "rejected"
            version.rejection_reason = f"{actor}: {reason}"[:2000]
            version.is_active = False
            version.deactivated_at = _utc_now()
            return {"id": version.id, "status": "rejected", "active": False}

    def rollback_to(self, model_id: int, actor: str) -> dict:
        """将同场站同任务的运行模型切换到指定已审批版本。"""
        with db_session() as session:
            version = session.query(ModelVersion).filter(ModelVersion.id == model_id).with_for_update().first()
            if version is None:
                raise ValueError(f"模型版本 {model_id} 不存在")
            if version.lifecycle_status != "approved":
                raise ValueError("只允许回滚到已审批模型")
            current_digest = _sha256_file(version.local_path)
            if current_digest is None:
                raise ValueError("目标模型制品缺失")
            if version.artifact_sha256 and current_digest != version.artifact_sha256:
                raise ValueError("目标模型制品缺失或摘要校验失败")
            version.artifact_sha256 = current_digest
            now = _utc_now()
            active_versions = session.query(ModelVersion).filter(
                ModelVersion.farm_code == version.farm_code,
                ModelVersion.task_type == version.task_type,
                ModelVersion.is_active.is_(True),
            ).with_for_update().all()
            for item in active_versions:
                item.is_active = False
                item.deactivated_at = now
            version.is_active = True
            version.activated_at = now
            version.deactivated_at = None
            return {"id": version.id, "status": "approved", "active": True}

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
            .all()
        )
        active_versions.sort(
            key=lambda item: (
                item.val_accuracy if item.val_accuracy is not None else float("-inf"),
                item.trained_at or datetime.min,
                item.id or 0,
            ),
            reverse=True,
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
