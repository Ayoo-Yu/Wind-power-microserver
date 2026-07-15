"""退役旧链路、演示结构和重复索引。

版本号: 20260715_02
前置版本: 20260715_01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260715_02"
down_revision: Union[str, None] = "20260715_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RETIRED_TABLES = (
    "readings",
    "conditions",
    "turbines",
    "training_history",
    "user_roles",
    "prediction_records",
    "training_records",
    "auto_prediction_tasks",
)

PRIMARY_KEY_INDEX_TABLES = (
    "actual_power",
    "alarm_notification_policies",
    "alarm_records",
    "alarm_rules",
    "available_capacity_data",
    "available_power_data",
    "daily_metrics",
    "data_quality_markers",
    "datasets",
    "farm_profile_configs",
    "installed_capacity_data",
    "login_history",
    "manual_intervention_versions",
    "mid_power",
    "models",
    "operation_audit_logs",
    "prediction_runs",
    "prediction_tasks",
    "report_config_meta",
    "report_configs",
    "report_logs",
    "report_outbox",
    "report_quality_statistics",
    "roles",
    "scada_connections",
    "scada_ingest_records",
    "shortl_power",
    "supershortl_power",
    "system_settings",
    "theoretical_power_data",
    "turbine_power_data",
    "user_profile_meta",
    "users",
    "weather_data",
    "wind_farms",
    "wind_speed_data",
)

FARM_CODE_DUPLICATE_INDEXES = {
    "actual_power": "ix_actual_power_farm_code_farm_part",
    "mid_power": "ix_mid_power_farm_code_farm_part",
    "shortl_power": "ix_shortl_power_farm_code_farm_part",
    "supershortl_power": "ix_supershortl_power_farm_code_farm_part",
}


def _existing_tables(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names(schema="public"))


def _assert_retired_tables_empty(bind) -> None:
    existing = _existing_tables(bind)
    quote_identifier = bind.dialect.identifier_preparer.quote
    populated = []
    for table_name in RETIRED_TABLES:
        if table_name not in existing:
            continue
        quoted_table = quote_identifier(table_name)
        has_data = bool(
            bind.execute(
                sa.text(f"SELECT EXISTS (SELECT 1 FROM {quoted_table} LIMIT 1)")
            ).scalar()
        )
        if has_data:
            populated.append(table_name)
    if populated:
        names = "、".join(populated)
        raise RuntimeError(f"待退役表仍有数据，请先归档后重试: {names}")


def _drop_redundant_indexes(bind) -> None:
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names(schema="public"))
    for table_name in PRIMARY_KEY_INDEX_TABLES:
        if table_name not in existing:
            continue
        primary_key = inspector.get_pk_constraint(table_name, schema="public")
        if primary_key.get("constrained_columns") != ["id"]:
            continue
        indexes = {
            item["name"]: item
            for item in inspector.get_indexes(table_name, schema="public")
        }
        index_name = f"ix_{table_name}_id"
        index = indexes.get(index_name)
        if index and index.get("column_names") == ["id"] and not index.get("unique"):
            op.drop_index(index_name, table_name=table_name)

    for table_name, redundant_name in FARM_CODE_DUPLICATE_INDEXES.items():
        if table_name not in existing:
            continue
        indexes = {
            item["name"]: item
            for item in sa.inspect(bind).get_indexes(table_name, schema="public")
        }
        canonical = indexes.get(f"ix_{table_name}_farm_code")
        redundant = indexes.get(redundant_name)
        if (
            canonical
            and redundant
            and canonical.get("column_names") == ["farm_code"]
            and redundant.get("column_names") == ["farm_code"]
            and not redundant.get("unique")
        ):
            op.drop_index(redundant_name, table_name=table_name)


def upgrade() -> None:
    bind = op.get_bind()
    _assert_retired_tables_empty(bind)
    existing = _existing_tables(bind)
    for table_name in RETIRED_TABLES:
        if table_name in existing:
            op.drop_table(table_name)
    _drop_redundant_indexes(bind)


def _restore_retired_tables() -> None:
    op.create_table(
        "training_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("farm_code", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("dataset_path", sa.String(500)),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("duration", sa.Float()),
        sa.Column("log_path", sa.String(512)),
    )
    op.create_index("ix_training_records_farm_code", "training_records", ["farm_code"])

    op.create_table(
        "prediction_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("farm_code", sa.String(50), nullable=False),
        sa.Column("model_id", sa.String(255), sa.ForeignKey("datasets.file_id")),
        sa.Column("input_data_id", sa.String(255), sa.ForeignKey("datasets.file_id")),
        sa.Column("scaler_id", sa.String(255), sa.ForeignKey("datasets.file_id")),
        sa.Column("prediction_time", sa.DateTime()),
        sa.Column("output_path", sa.String(512)),
        sa.Column("prediction_type", sa.String(20)),
        sa.Column("status", sa.String(20)),
    )
    op.create_index("ix_prediction_records_farm_code", "prediction_records", ["farm_code"])

    op.create_table(
        "auto_prediction_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_type", sa.String(20)),
        sa.Column("farm_code", sa.String(50), nullable=False),
        sa.Column("schedule_time", sa.String(5)),
        sa.Column("last_run", sa.DateTime()),
        sa.Column("next_run", sa.DateTime()),
        sa.Column("output_dir", sa.String(512)),
        sa.Column("is_active", sa.Boolean()),
    )
    op.create_index("ix_auto_prediction_tasks_farm_code", "auto_prediction_tasks", ["farm_code"])

    op.create_table(
        "training_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dataset_name", sa.String(255), nullable=False),
        sa.Column("model_type", sa.String(50), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("metrics", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("prediction_file", sa.String(255)),
        sa.Column("report_file", sa.String(255)),
        sa.Column("file_id", sa.String(255), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("status", sa.String(20), server_default=sa.text("'completed'")),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_training_history_file_id", "training_history", ["file_id"])
    op.create_index("ix_training_history_user_id", "training_history", ["user_id"])

    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("permissions", sa.JSON()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )

    op.create_table(
        "conditions",
        sa.Column("condition_id", sa.Integer(), primary_key=True),
        sa.Column("farm_name", sa.String(255), nullable=False),
        sa.Column("wind_speed", sa.Float(), nullable=False),
        sa.Column("wind_direction", sa.Float(), nullable=False),
        sa.Column("is_interpolated", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "farm_name", "wind_speed", "wind_direction",
            name="uq_condition_farm_wind",
        ),
    )
    op.create_table(
        "turbines",
        sa.Column("turbine_id", sa.Integer(), primary_key=True),
        sa.Column("farm_name", sa.String(255), nullable=False),
        sa.Column("turbine_number", sa.String(255), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("hub_height", sa.Float()),
        sa.Column("rotor_diameter", sa.Float()),
        sa.Column("turbine_model", sa.String(255)),
        sa.UniqueConstraint("farm_name", "turbine_number", name="uq_turbine_farm_number"),
    )
    op.create_table(
        "readings",
        sa.Column("reading_id", sa.Integer(), primary_key=True),
        sa.Column("condition_id", sa.Integer(), sa.ForeignKey("conditions.condition_id")),
        sa.Column("turbine_id", sa.Integer(), sa.ForeignKey("turbines.turbine_id")),
        sa.Column("turbine_wind_speed", sa.Float(), nullable=False),
        sa.Column("power_output", sa.Float()),
        sa.UniqueConstraint("condition_id", "turbine_id", name="uq_reading_condition_turbine"),
    )


def _restore_redundant_indexes(bind) -> None:
    existing = _existing_tables(bind)
    for table_name in PRIMARY_KEY_INDEX_TABLES:
        if table_name in existing:
            op.create_index(f"ix_{table_name}_id", table_name, ["id"])
    for table_name, index_name in FARM_CODE_DUPLICATE_INDEXES.items():
        if table_name in existing:
            op.create_index(index_name, table_name, ["farm_code"])


def downgrade() -> None:
    bind = op.get_bind()
    _restore_redundant_indexes(bind)
    _restore_retired_tables()
