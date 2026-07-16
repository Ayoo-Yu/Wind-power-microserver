"""增加预测输出账本和南网日评估追溯字段。

版本号: 20260716_01
前置版本: 20260715_03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260716_01"
down_revision: Union[str, None] = "20260715_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "forecast_output_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "prediction_run_id",
            sa.Integer(),
            sa.ForeignKey("prediction_runs.id"),
            nullable=False,
        ),
        sa.Column("input_snapshot_id", sa.Integer()),
        sa.Column("model_version_id", sa.Integer()),
        sa.Column("farm_code", sa.String(50), nullable=False),
        sa.Column("forecast_type", sa.String(20), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("target_time", sa.DateTime(), nullable=False),
        sa.Column("horizon_index", sa.Integer(), nullable=False),
        sa.Column("horizon_minutes", sa.Integer(), nullable=False),
        sa.Column("predicted_power", sa.Float(), nullable=False),
        sa.Column("raw_predicted_power", sa.Float()),
        sa.Column("lower_power", sa.Float()),
        sa.Column("upper_power", sa.Float()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "prediction_run_id",
            "target_time",
            "horizon_index",
            name="uq_forecast_output_points_run_target_horizon",
        ),
    )
    op.create_index(
        "ix_forecast_output_points_prediction_run_id",
        "forecast_output_points",
        ["prediction_run_id"],
    )
    op.create_index(
        "ix_forecast_output_points_input_snapshot_id",
        "forecast_output_points",
        ["input_snapshot_id"],
    )
    op.create_index(
        "ix_forecast_output_points_model_version_id",
        "forecast_output_points",
        ["model_version_id"],
    )
    op.create_index("ix_forecast_output_points_created_at", "forecast_output_points", ["created_at"])
    op.create_index(
        "ix_forecast_output_points_farm_type_target",
        "forecast_output_points",
        ["farm_code", "forecast_type", "target_time"],
    )
    op.create_index(
        "ix_forecast_output_points_farm_type_issued",
        "forecast_output_points",
        ["farm_code", "forecast_type", "issued_at"],
    )

    op.add_column(
        "daily_metrics",
        sa.Column(
            "policy_version",
            sa.String(64),
            nullable=False,
            server_default="legacy",
        ),
    )
    op.add_column("daily_metrics", sa.Column("threshold_percent", sa.Float()))
    op.add_column("daily_metrics", sa.Column("expected_count", sa.Integer()))
    op.add_column(
        "daily_metrics",
        sa.Column("excluded_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("daily_metrics", sa.Column("completeness", sa.Float()))
    op.add_column(
        "daily_metrics",
        sa.Column("status", sa.String(20), nullable=False, server_default="legacy"),
    )
    op.add_column("daily_metrics", sa.Column("details_json", sa.JSON()))
    op.add_column("daily_metrics", sa.Column("computed_at", sa.DateTime()))
    op.create_index(
        "ix_daily_metrics_farm_type_date_policy",
        "daily_metrics",
        ["farm_code", "metric_type", "date", "policy_version"],
    )


def downgrade() -> None:
    op.drop_index("ix_daily_metrics_farm_type_date_policy", table_name="daily_metrics")
    op.drop_column("daily_metrics", "computed_at")
    op.drop_column("daily_metrics", "details_json")
    op.drop_column("daily_metrics", "status")
    op.drop_column("daily_metrics", "completeness")
    op.drop_column("daily_metrics", "excluded_count")
    op.drop_column("daily_metrics", "expected_count")
    op.drop_column("daily_metrics", "threshold_percent")
    op.drop_column("daily_metrics", "policy_version")

    op.drop_index("ix_forecast_output_points_farm_type_issued", table_name="forecast_output_points")
    op.drop_index("ix_forecast_output_points_farm_type_target", table_name="forecast_output_points")
    op.drop_index("ix_forecast_output_points_created_at", table_name="forecast_output_points")
    op.drop_index("ix_forecast_output_points_model_version_id", table_name="forecast_output_points")
    op.drop_index("ix_forecast_output_points_input_snapshot_id", table_name="forecast_output_points")
    op.drop_index("ix_forecast_output_points_prediction_run_id", table_name="forecast_output_points")
    op.drop_table("forecast_output_points")
