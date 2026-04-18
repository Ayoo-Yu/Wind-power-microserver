# wind-power-forecast/backend-autopredict/db_models/model_version.py
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from .base import Base


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, index=True)
    farm_code = Column(String(50), nullable=False)
    task_type = Column(String(20), nullable=False)  # supershort / short / medium
    algorithm = Column(String(50), nullable=False)   # xgboost / lightgbm_gbdt / lightgbm_dart / lightgbm_goss
    hyperparams = Column(JSONB)
    val_rmse = Column(Float)
    val_mae = Column(Float)
    val_accuracy = Column(Float)  # 1 - rmse/capacity
    is_active = Column(Boolean, default=True)
    s3_path = Column(String(500))
    local_path = Column(String(500))
    scaler_path = Column(String(500))
    feature_cols = Column(JSONB)
    training_samples = Column(Integer)
    trained_at = Column(DateTime, default=datetime.now)
    activated_at = Column(DateTime)
    deactivated_at = Column(DateTime)

    __table_args__ = (
        Index("idx_mv_farm_type", "farm_code", "task_type"),
        Index("idx_mv_active", "farm_code", "task_type", "is_active"),
    )
