"""生产数据接入批次、规范化观测和预测输入快照。"""

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)

from .base import Base


class IngestionBatch(Base):
    """记录一个跨区文件从接收到业务入库的完整处理结果。"""

    __tablename__ = "ingestion_batches"

    id = Column(Integer, primary_key=True)
    message_id = Column(String(128), nullable=False, unique=True)
    source_type = Column(String(20), nullable=False, index=True)
    source_id = Column(String(128), nullable=False)
    farm_code = Column(String(50), nullable=False, index=True)
    schema_version = Column(String(32), nullable=False)
    event_time = Column(DateTime, nullable=False, index=True)
    received_at = Column(DateTime, nullable=False, default=datetime.now, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="received", index=True)
    quality_status = Column(String(20), nullable=False, default="unknown", index=True)
    record_count = Column(Integer, nullable=True)
    accepted_count = Column(Integer, nullable=False, default=0)
    rejected_count = Column(Integer, nullable=False, default=0)
    payload_sha256 = Column(String(64), nullable=False)
    payload_filename = Column(String(240), nullable=False)
    metadata_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_ingestion_batches_farm_type_event",
            "farm_code",
            "source_type",
            "event_time",
        ),
    )


class SourceObservation(Base):
    """保存经过统一语义映射的 SCADA 等实时观测。"""

    __tablename__ = "source_observations"

    id = Column(Integer, primary_key=True)
    observation_key = Column(String(64), nullable=False)
    batch_id = Column(Integer, nullable=True, index=True)
    source_type = Column(String(20), nullable=False, index=True)
    source_id = Column(String(128), nullable=False)
    farm_code = Column(String(50), nullable=False, index=True)
    metric = Column(String(64), nullable=False, index=True)
    event_time = Column(DateTime, nullable=False, index=True)
    received_at = Column(DateTime, nullable=False, default=datetime.now, index=True)
    value = Column(Float, nullable=True)
    unit = Column(String(24), nullable=False)
    quality = Column(String(20), nullable=False, default="unknown", index=True)
    sequence = Column(String(64), nullable=True)
    schema_version = Column(String(32), nullable=False)
    payload_sha256 = Column(String(64), nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("observation_key", name="uq_source_observations_key"),
        Index(
            "ix_source_observations_farm_metric_event",
            "farm_code",
            "metric",
            "event_time",
        ),
        Index(
            "ix_source_observations_source_received",
            "source_type",
            "source_id",
            "received_at",
        ),
    )


class PredictionInputSnapshot(Base):
    """冻结一次预测实际使用的数据来源和模型版本。"""

    __tablename__ = "prediction_input_snapshots"

    id = Column(Integer, primary_key=True)
    prediction_run_id = Column(
        Integer,
        ForeignKey("prediction_runs.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    farm_code = Column(String(50), nullable=False, index=True)
    task_type = Column(String(20), nullable=False, index=True)
    captured_at = Column(DateTime, nullable=False, default=datetime.now, index=True)
    contract_version = Column(String(32), nullable=False)
    dataset_version = Column(String(64), nullable=False, index=True)
    model_version_id = Column(
        Integer,
        ForeignKey("model_versions.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    data_start = Column(DateTime, nullable=True)
    data_end = Column(DateTime, nullable=True)
    scada_observation_count = Column(Integer, nullable=False, default=0)
    nwp_record_count = Column(Integer, nullable=False, default=0)
    missing_rate = Column(Float, nullable=False, default=1.0)
    status = Column(String(20), nullable=False, default="unknown", index=True)
    quality_summary = Column(JSON, nullable=False)
    input_manifest = Column(JSON, nullable=False)
    manifest_sha256 = Column(String(64), nullable=False)
