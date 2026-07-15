"""增加商业化数据血缘、输入快照和模型审批字段。

版本号: 20260715_03
前置版本: 20260715_02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260715_03"
down_revision: Union[str, None] = "20260715_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ingestion_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.String(128), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column("farm_code", sa.String(50), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("event_time", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("quality_status", sa.String(20), nullable=False),
        sa.Column("record_count", sa.Integer()),
        sa.Column("accepted_count", sa.Integer(), nullable=False),
        sa.Column("rejected_count", sa.Integer(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("payload_filename", sa.String(240), nullable=False),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("error_message", sa.Text()),
        sa.UniqueConstraint("message_id", name="uq_ingestion_batches_message_id"),
    )
    op.create_index("ix_ingestion_batches_source_type", "ingestion_batches", ["source_type"])
    op.create_index("ix_ingestion_batches_farm_code", "ingestion_batches", ["farm_code"])
    op.create_index("ix_ingestion_batches_event_time", "ingestion_batches", ["event_time"])
    op.create_index("ix_ingestion_batches_received_at", "ingestion_batches", ["received_at"])
    op.create_index("ix_ingestion_batches_status", "ingestion_batches", ["status"])
    op.create_index("ix_ingestion_batches_quality_status", "ingestion_batches", ["quality_status"])
    op.create_index(
        "ix_ingestion_batches_farm_type_event",
        "ingestion_batches",
        ["farm_code", "source_type", "event_time"],
    )

    op.create_table(
        "source_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("observation_key", sa.String(64), nullable=False),
        sa.Column("batch_id", sa.Integer()),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column("farm_code", sa.String(50), nullable=False),
        sa.Column("metric", sa.String(64), nullable=False),
        sa.Column("event_time", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("value", sa.Float()),
        sa.Column("unit", sa.String(24), nullable=False),
        sa.Column("quality", sa.String(20), nullable=False),
        sa.Column("sequence", sa.String(64)),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("payload_sha256", sa.String(64)),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("observation_key", name="uq_source_observations_key"),
    )
    op.create_index("ix_source_observations_batch_id", "source_observations", ["batch_id"])
    op.create_index("ix_source_observations_source_type", "source_observations", ["source_type"])
    op.create_index("ix_source_observations_farm_code", "source_observations", ["farm_code"])
    op.create_index("ix_source_observations_metric", "source_observations", ["metric"])
    op.create_index("ix_source_observations_event_time", "source_observations", ["event_time"])
    op.create_index("ix_source_observations_received_at", "source_observations", ["received_at"])
    op.create_index("ix_source_observations_quality", "source_observations", ["quality"])
    op.create_index(
        "ix_source_observations_farm_metric_event",
        "source_observations",
        ["farm_code", "metric", "event_time"],
    )
    op.create_index(
        "ix_source_observations_source_received",
        "source_observations",
        ["source_type", "source_id", "received_at"],
    )

    op.create_table(
        "prediction_input_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prediction_run_id", sa.Integer(), nullable=False),
        sa.Column("farm_code", sa.String(50), nullable=False),
        sa.Column("task_type", sa.String(20), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("contract_version", sa.String(32), nullable=False),
        sa.Column("dataset_version", sa.String(64), nullable=False),
        sa.Column("model_version_id", sa.Integer()),
        sa.Column("data_start", sa.DateTime()),
        sa.Column("data_end", sa.DateTime()),
        sa.Column("scada_observation_count", sa.Integer(), nullable=False),
        sa.Column("nwp_record_count", sa.Integer(), nullable=False),
        sa.Column("missing_rate", sa.Float(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("quality_summary", sa.JSON(), nullable=False),
        sa.Column("input_manifest", sa.JSON(), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.UniqueConstraint("prediction_run_id", name="uq_prediction_input_snapshots_run"),
    )
    op.create_index("ix_prediction_input_snapshots_farm_code", "prediction_input_snapshots", ["farm_code"])
    op.create_index("ix_prediction_input_snapshots_task_type", "prediction_input_snapshots", ["task_type"])
    op.create_index("ix_prediction_input_snapshots_captured_at", "prediction_input_snapshots", ["captured_at"])
    op.create_index("ix_prediction_input_snapshots_dataset_version", "prediction_input_snapshots", ["dataset_version"])
    op.create_index("ix_prediction_input_snapshots_model_version_id", "prediction_input_snapshots", ["model_version_id"])
    op.create_index("ix_prediction_input_snapshots_status", "prediction_input_snapshots", ["status"])

    op.add_column(
        "scada_connections",
        sa.Column(
            "point_catalog_version",
            sa.String(32),
            nullable=False,
            server_default="scada-point-v1",
        ),
    )
    op.add_column(
        "scada_ingest_records",
        sa.Column(
            "metric",
            sa.String(64),
            nullable=False,
            server_default="active_power_mw",
        ),
    )
    op.add_column("scada_ingest_records", sa.Column("value", sa.Float()))
    op.add_column("scada_ingest_records", sa.Column("unit", sa.String(24)))
    op.add_column("scada_ingest_records", sa.Column("source_id", sa.String(128)))
    op.add_column("scada_ingest_records", sa.Column("observation_id", sa.Integer()))
    op.execute("UPDATE scada_ingest_records SET value = power_mw, unit = 'MW' WHERE value IS NULL")
    op.create_index("ix_scada_ingest_records_metric", "scada_ingest_records", ["metric"])
    op.create_index("ix_scada_ingest_records_observation_id", "scada_ingest_records", ["observation_id"])

    op.add_column("model_versions", sa.Column("feature_contract_version", sa.String(50)))
    op.add_column("model_versions", sa.Column("dataset_version", sa.String(64)))
    op.add_column("model_versions", sa.Column("artifact_sha256", sa.String(64)))
    op.add_column(
        "model_versions",
        sa.Column(
            "lifecycle_status",
            sa.String(20),
            nullable=False,
            server_default="candidate",
        ),
    )
    op.add_column("model_versions", sa.Column("approved_by", sa.String(100)))
    op.add_column("model_versions", sa.Column("approved_at", sa.DateTime()))
    op.add_column("model_versions", sa.Column("rejection_reason", sa.Text()))
    op.execute(
        "UPDATE model_versions SET lifecycle_status = 'approved', "
        "approved_by = 'migration', approved_at = COALESCE(activated_at, trained_at) "
        "WHERE is_active = TRUE"
    )


def downgrade() -> None:
    op.drop_column("model_versions", "rejection_reason")
    op.drop_column("model_versions", "approved_at")
    op.drop_column("model_versions", "approved_by")
    op.drop_column("model_versions", "lifecycle_status")
    op.drop_column("model_versions", "artifact_sha256")
    op.drop_column("model_versions", "dataset_version")
    op.drop_column("model_versions", "feature_contract_version")

    op.drop_index("ix_scada_ingest_records_observation_id", table_name="scada_ingest_records")
    op.drop_index("ix_scada_ingest_records_metric", table_name="scada_ingest_records")
    op.drop_column("scada_ingest_records", "observation_id")
    op.drop_column("scada_ingest_records", "source_id")
    op.drop_column("scada_ingest_records", "unit")
    op.drop_column("scada_ingest_records", "value")
    op.drop_column("scada_ingest_records", "metric")
    op.drop_column("scada_connections", "point_catalog_version")

    op.drop_table("prediction_input_snapshots")
    op.drop_table("source_observations")
    op.drop_table("ingestion_batches")
