from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, Index, JSON
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timezone
from .base import Base


MODEL_JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True)
    farm_code = Column(String(50), nullable=False)
    task_type = Column(String(20), nullable=False)  # supershort / short / medium
    algorithm = Column(String(50), nullable=False)   # xgboost / lightgbm_gbdt / lightgbm_dart / lightgbm_goss
    hyperparams = Column(MODEL_JSON_TYPE)
    val_rmse = Column(Float)
    val_mae = Column(Float)
    val_accuracy = Column(Float)  # 1 - rmse/capacity
    is_active = Column(Boolean, default=False)
    local_path = Column(String(500))
    scaler_path = Column(String(500))
    feature_cols = Column(MODEL_JSON_TYPE)
    feature_contract_version = Column(String(50))
    dataset_version = Column(String(64))
    artifact_sha256 = Column(String(64))
    lifecycle_status = Column(String(20), nullable=False, default="candidate")
    approved_by = Column(String(100))
    approved_at = Column(DateTime)
    rejection_reason = Column(Text)
    training_samples = Column(Integer)
    trained_at = Column(DateTime, default=utc_now)
    activated_at = Column(DateTime)
    deactivated_at = Column(DateTime)

    __table_args__ = (
        Index("ix_model_versions_farm_type_trained", "farm_code", "task_type", "trained_at"),
        Index(
            "ix_model_versions_active_score",
            "farm_code",
            "task_type",
            "is_active",
            "val_accuracy",
            "trained_at",
            postgresql_where=(is_active == True),
        ),
    )
