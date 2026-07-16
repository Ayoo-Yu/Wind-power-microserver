"""预测运行的不可变输出账本。"""

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)

from .base import Base


class ForecastOutputPoint(Base):
    """保存一次预测运行实际产出的单个目标时刻结果。"""

    __tablename__ = "forecast_output_points"

    id = Column(Integer, primary_key=True)
    prediction_run_id = Column(
        Integer,
        ForeignKey("prediction_runs.id"),
        nullable=False,
        index=True,
    )
    input_snapshot_id = Column(
        Integer,
        ForeignKey("prediction_input_snapshots.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    model_version_id = Column(
        Integer,
        ForeignKey("model_versions.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    farm_code = Column(String(50), nullable=False)
    forecast_type = Column(String(20), nullable=False)
    issued_at = Column(DateTime, nullable=False)
    target_time = Column(DateTime, nullable=False)
    horizon_index = Column(Integer, nullable=False)
    horizon_minutes = Column(Integer, nullable=False)
    predicted_power = Column(Float, nullable=False)
    raw_predicted_power = Column(Float, nullable=True)
    lower_power = Column(Float, nullable=True)
    upper_power = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now, index=True)

    __table_args__ = (
        UniqueConstraint(
            "prediction_run_id",
            "target_time",
            "horizon_index",
            name="uq_forecast_output_points_run_target_horizon",
        ),
        Index(
            "ix_forecast_output_points_farm_type_target",
            "farm_code",
            "forecast_type",
            "target_time",
        ),
        Index(
            "ix_forecast_output_points_farm_type_issued",
            "farm_code",
            "forecast_type",
            "issued_at",
        ),
    )
